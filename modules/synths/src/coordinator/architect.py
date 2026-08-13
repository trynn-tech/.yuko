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
    """Coordinates multi-step reasoning recipes using the core Working Memory Pipeline,
    LLM client generation, and 3-tier synchronization.
    """

    def __init__(
        self,
        executor,
        patcher,
        graph_linker,
        redis_store=None,
        embedder=None,
        memory_pipeline=None,
        llm_client=None,
        enable_searxng: bool = True,
        enable_upstream: bool = True,
    ):
        self.executor = executor
        self.patcher = patcher
        self.graph_linker = graph_linker
        self.redis_store = redis_store
        self.embedder = embedder
        self.memory_pipeline = memory_pipeline
        self.llm_client = llm_client
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
        """Executes a single step using the robust Working Memory Pipeline and LLM client."""
        logger.info("Executing Recipe Step %d on %s", step.step_id, step.target_file)
        
        file_path = Path(step.target_file)
        file_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        
        if not self.llm_client:
            logger.error("LLM client not available in ArchitectCoordinator.")
            return False

        system_prompt = (
            "CRITICAL: Output ONLY valid SEARCH and REPLACE blocks or code blocks. "
            "Never include conversational prose, preambles, or explanations."
        )
        user_prompt = f"Target File: {step.target_file}\nInstruction: {step.instruction}\n\nCurrent Content:\n{file_content}"

        failed_attempts = 0
        context_enrichment = ""

        # Phase 1: In-Place Execution Passes (Attempts 1 to 3)
        for attempt in range(1, 4):
            logger.info("In-Place Synthesis Attempt %d/3 for %s", attempt, step.target_file)
            
            current_prompt = user_prompt
            if context_enrichment:
                current_prompt += f"\n\n### ADDITIONAL CONTEXT:\n{context_enrichment}"

            try:
                raw_response = (
                    self.llm_client.generate(system_prompt, current_prompt)
                    if hasattr(self.llm_client, "generate")
                    else self.llm_client.generate_stream(system_prompt, current_prompt)
                )

                # Process through Working Memory Pipeline (parses, validates, 3-tier sync)
                if self.memory_pipeline:
                    frame = self.memory_pipeline.process_synthesis(
                        instruction=step.instruction,
                        raw_llm_response=raw_response,
                        llm_client=self.llm_client,
                        explicit_target=file_path,
                        original_code=file_content,
                    )
                else:
                    frame = None

                # Apply parsed blocks atomically via Executor
                blocks = self.patcher.parse_blocks(raw_response, fallback_filepath=step.target_file)
                applied_any = False
                for block in blocks:
                    target = block.filepath or step.target_file
                    r_block = block.replace_block if block.replace_block.strip() else block.search_anchor
                    success = self.executor.apply_anchor_edit(
                        filepath=target,
                        search_anchor=block.search_anchor,
                        replace_block=r_block,
                    )
                    if success:
                        applied_any = True

                if applied_any or (frame and frame.verification_passed):
                    step.completed = True
                    self._post_edit_sync(step.target_file)
                    return True

            except Exception as e:
                logger.warning("Attempt %d failed with error: %s", attempt, e)

            failed_attempts += 1

        # Phase 2: Divergent Execution Passes (Attempts 4 to 6)
        logger.warning("In-place passes exhausted. Transitioning to Divergence Pipeline...")

        if self.enable_searxng:
            searxng_info = self.divergence.enrich_via_searxng(f"{step.target_file} {step.instruction}")
            context_enrichment += f"\n[Web/Doc Discovery]:\n{searxng_info}"

        if self.enable_upstream:
            upstream_info = self.divergence.enrich_via_upstream_api(file_content, step.instruction, [f"Failed attempt {failed_attempts}"])
            context_enrichment += f"\n[LLM Strategy Recommendation]:\n{upstream_info}"

        redis_info = self.divergence.enrich_via_redis_memory(step.instruction)
        context_enrichment += f"\n[Historical Memory Insights]:\n{redis_info}"

        # Final unified divergence attempt
        try:
            current_prompt = user_prompt + f"\n\n### ADDITIONAL CONTEXT:\n{context_enrichment}"
            raw_response = self.llm_client.generate(system_prompt, current_prompt)
            blocks = self.patcher.parse_blocks(raw_response, fallback_filepath=step.target_file)
            applied_any = False
            for block in blocks:
                target = block.filepath or step.target_file
                r_block = block.replace_block if block.replace_block.strip() else block.search_anchor
                if self.executor.apply_anchor_edit(target, block.search_anchor, r_block):
                    applied_any = True

            if applied_any:
                step.completed = True
                self._post_edit_sync(step.target_file)
                return True
        except Exception as e:
            logger.error("Divergence pass execution failed: %s", e)

        logger.error("Step %d halted after all attempts.", step.step_id)
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
