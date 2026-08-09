#!/usr/bin/env python3
# src/coordinator/architect.py

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from coordinator.divergence import DivergenceHandler

logger = logging.getLogger(__name__)


class RecipeStep(BaseModel):
    step_id: int
    target_file: str
    instruction: str
    completed: bool = False


class ArchitectCoordinator:
    """Coordinates task recipes using 3 in-place retries and 3 non-destructive divergence passes."""

    def __init__(
        self,
        executor,
        patcher,
        graph_linker,
        redis_store=None,
        embedder=None,
        enable_searxng: bool = True,
        enable_upstream: bool = True,
    ):
        self.executor = executor
        self.patcher = patcher
        self.graph_linker = graph_linker
        self.divergence = DivergenceHandler(redis_store=redis_store, embedder=embedder)
        self.enable_searxng = enable_searxng
        self.enable_upstream = enable_upstream

    def create_recipe(self, goal: str, target_files: List[str]) -> List[RecipeStep]:
        """Deconstructs a high-level goal into an ordered sequence of file steps."""
        steps = []
        for idx, file_path in enumerate(target_files, start=1):
            steps.append(
                RecipeStep(
                    step_id=idx,
                    target_file=file_path,
                    instruction=goal,
                )
            )
        return steps

    def execute_step(self, step: RecipeStep) -> bool:
        """Executes a single step with 3 in-place retries + 3 non-destructive divergence steps."""
        logger.info("Executing Recipe Step %d on %s", step.step_id, step.target_file)
        
        file_path = Path(step.target_file)
        file_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        failed_anchors = []
        context_enrichment = ""

        # Phase 1: In-Place Retries (Attempts 1 to 3)
        for attempt in range(1, 4):
            logger.info("In-Place Attempt %d/3 for %s", attempt, step.target_file)
            
            prompt = step.instruction
            if context_enrichment:
                prompt += f"\n\n### ADDITIONAL CONTEXT:\n{context_enrichment}"

            patch_applied = self.executor.run_edit_pass(
                filepath=step.target_file,
                instruction=prompt,
                content=file_content,
            )

            if patch_applied:
                step.completed = True
                self._post_edit_sync(step.target_file)
                return True

            failed_anchors.append(f"Attempt {attempt} failed to locate anchor.")

        # Phase 2: Divergent Execution Passes (Attempts 4 to 6)
        logger.warning("In-place passes exhausted. Transitioning to Divergence Pipeline...")

        # Divergence Pass 1: SearXNG Web / Spec Enrichment
        if self.enable_searxng:
            searxng_info = self.divergence.enrich_via_searxng(f"{step.target_file} {step.instruction}")
            context_enrichment += f"\n[Web/Doc Discovery]:\n{searxng_info}"
            if self.executor.run_edit_pass(step.target_file, f"{step.instruction}\n{context_enrichment}", file_content):
                step.completed = True
                self._post_edit_sync(step.target_file)
                return True

        # Divergence Pass 2: Upstream LLM Strategy Query
        if self.enable_upstream:
            upstream_info = self.divergence.enrich_via_upstream_api(file_content, step.instruction, failed_anchors)
            context_enrichment += f"\n[LLM Strategy Recommendation]:\n{upstream_info}"
            if self.executor.run_edit_pass(step.target_file, f"{step.instruction}\n{context_enrichment}", file_content):
                step.completed = True
                self._post_edit_sync(step.target_file)
                return True

        # Divergence Pass 3: Redis Working Memory KNN Query
        redis_info = self.divergence.enrich_via_redis_memory(step.instruction)
        context_enrichment += f"\n[Historical Memory Insights]:\n{redis_info}"
        if self.executor.run_edit_pass(step.target_file, f"{step.instruction}\n{context_enrichment}", file_content):
            step.completed = True
            self._post_edit_sync(step.target_file)
            return True

        logger.error("Step %d halted after 3 in-place and 3 divergent attempts.", step.step_id)
        return False

    def _post_edit_sync(self, filepath: str) -> None:
        """Re-indexes full AST and updates Neo4j upon successful edit."""
        if not self.graph_linker:
            return
        try:
            code = Path(filepath).read_text(encoding="utf-8")
            facts = self.patcher.extract_ast_facts(filepath, code)
            lang = self.patcher._detect_language(filepath)
            
            self.graph_linker.sync_thought_frame_graph({
                "resolved_path": filepath,
                "language": lang,
                "ast_facts": facts,
                "concept_tags": facts.get("imports", []),
            })
            logger.info("Successfully re-indexed AST nodes for %s in Neo4j", filepath)
        except Exception as e:
            logger.error("Post-edit graph sync failed for %s: %s", filepath, e)
