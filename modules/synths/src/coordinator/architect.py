#!/usr/bin/env python3
# src/coordinator/architect.py
import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple
from pydantic import BaseModel
from .pachinko import PachinkoRouter, OperationalIntent, DispatchDecision
from .divergence import DivergenceHandler

logger = logging.getLogger(__name__)

class RecipeStep(BaseModel):
    step_id: int
    target_file: str
    instruction: str
    completed: bool = False
    frame: Optional[Any] = None  # Added to store synthesized ThoughtFrame


class ArchitectCoordinator:
    def __init__(
        self,
        executor: Any,
        patcher: Any,
        graph_linker: Any,
        redis_store: Any,
        embedder: Any,
        memory_pipeline: Any,
        llm_client: Any = None,
        enable_searxng: bool = True,
        enable_upstream: bool = True,
        router: Optional[PachinkoRouter] = None,
    ):
        self.executor = executor
        self.patcher = patcher
        self.graph_linker = graph_linker
        self.redis_store = redis_store
        self.embedder = embedder
        self.memory_pipeline = memory_pipeline
        self.llm_client = llm_client
        self.enable_searxng = enable_searxng
        self.enable_upstream = enable_upstream
        self.pachinko = router or PachinkoRouter()

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

    # note: Logic Builder
    def execute_step(self, step: RecipeStep) -> Tuple[bool, Optional[Any]]:
        """Executes a single recipe step, synchronizes memory, and returns (success, frame)."""
        logger.info("Executing Recipe Step %d on %s", step.step_id, step.target_file)
        
        workspace_files = [str(p) for p in Path(".").rglob("*") if p.is_file()]
        decision = self.pachinko.route_target(step.target_file, workspace_files)
        file_path = decision.target_path

        # Symbolic Functor Pre-check: Handle explicit import instructions deterministically
        instruction_lower = step.instruction.lower()
        if "import" in instruction_lower or "module" in instruction_lower:
            words = step.instruction.split()
            module_name = next(
                (
                    w.strip("'\"`")
                    for w in words
                    if "service" in w.lower()
                    or w.isalnum()
                    and w not in ["import", "module", "named", "the", "to", "for"]
                ),
                "base_service",
            )
            import_statement = (
                f"from {module_name} import BaseService"
                if "baseservice" in module_name.lower() or "base_service" in module_name.lower()
                else f"import {module_name}"
            )

            logger.info("Intercepted symbolic import intent for %s on %s", module_name, file_path)
            if self.executor.apply_symbolic_edit(str(file_path), "import", module_name, import_statement):
                step.completed = True
                self._post_edit_sync(str(file_path))
                return True, None

        if decision.intent == OperationalIntent.CREATE:
            system_prompt = "CRITICAL: Output complete file content within ``` code blocks."
        else:
            system_prompt = (
                "CRITICAL: Output ONLY valid SEARCH and REPLACE blocks. "
                "Never include preambles or conversational prose."
            )

        original_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        user_prompt = f"Target: {file_path}\nIntent: {decision.intent.name}\nInstruction: {step.instruction}\n\nContent:\n{original_content}"

        try:
            raw_response = (
                self.llm_client.generate(system_prompt, user_prompt)
                if hasattr(self.llm_client, "generate")
                else self.llm_client.generate_stream(system_prompt, user_prompt)
            )

            # Process 3-tier memory pipeline synthesis
            workspace_ctx = [str(p) for p in Path(".").rglob("*.py") if not p.name.startswith(".")]
            frame = None
            if self.memory_pipeline:
                frame = self.memory_pipeline.process_synthesis(
                    instruction=step.instruction,
                    raw_llm_response=raw_response,
                    workspace_context=workspace_ctx,
                    requested_path=str(file_path),
                    original_code=original_content,
                )
                step.frame = frame

            if decision.intent == OperationalIntent.CREATE:
                success = self.executor.write_file(file_path, raw_response)
            else:
                blocks = self.patcher.parse_blocks(raw_response, fallback_filepath=str(file_path))
                success = False
                for block in blocks:
                    target = block.filepath or str(file_path)
                    r_block = block.replace_block if block.replace_block.strip() else block.search_anchor

                    if self.executor.apply_anchor_edit(target, block.search_anchor, r_block):
                        success = True
                    else:
                        if self.executor.write_file(target, r_block):
                            success = True

            if success:
                step.completed = True
                self._post_edit_sync(str(file_path))
                return True, frame

        except Exception as e:
            logger.error("Step execution failed on %s: %s", step.target_file, e)

        return False, None

    def _post_edit_sync(self, filepath: str) -> None:
        """Re-indexes full AST and updates Neo4j with semantic concept tags upon successful edit."""
        if not self.graph_linker:
            return
        try:
            code = Path(filepath).read_text(encoding="utf-8")
            facts = self.patcher.extract_ast_facts(filepath, code)
            lang = self.patcher._detect_language(filepath)

            concept_tags = list(
                set(facts.get("imports", []) + facts.get("classes", []) + facts.get("functions", []))
            )

            self.graph_linker.sync_thought_frame_graph(
                {
                    "resolved_path": filepath,
                    "language": lang,
                    "ast_facts": facts,
                    "concept_tags": concept_tags,
                }
            )
            logger.info("Successfully re-indexed AST nodes and semantic concepts for %s in Neo4j", filepath)
        except Exception as e:
            logger.error("Post-edit graph sync failed for %s: %s", filepath, e)
