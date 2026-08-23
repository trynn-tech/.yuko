#!/usr/bin/env python3
# modules/synths/src/engine/working_memory.py

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

from engine.anchor_patch import AnchorPatcher, PatchBlock
from engine.analyzer import CodeAnalyzer

# Defer import to prevent circular dependency with pipeline.py / redis_store.py
if TYPE_CHECKING:
    from reasoning.pipeline import ReasoningOrchestrator

logger = logging.getLogger(__name__)


class ThoughtFrame(BaseModel):
    """Structured temporal execution frame capturing instructions, dual-process 
    reasoning plans, code diffs, AST topology facts, and verification states.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = Field(default_factory=time.time)
    instruction: str
    reasoning_plan: Dict[str, Any] = Field(default_factory=dict)
    raw_response: str = ""
    original_code: str = ""
    extracted_code: str = ""
    language: str = "text"
    ast_facts: Dict[str, Any] = Field(default_factory=dict)
    concept_tags: List[str] = Field(default_factory=list)
    semantic_summary: str = ""
    predicted_title: str = ""
    resolved_path: Optional[str] = None
    verification_passed: bool = False
    coverage_metrics: Dict[str, Any] = Field(default_factory=dict)

    def to_redis_payload(self) -> str:
        return self.model_dump_json(indent=2)


class WorkingMemoryPipeline:
    """Orchestrates working memory persistence, neuro-symbolic dual-process plan 
    formulation, and 3-tier synchronization (Redis, RediSearch vector store, Neo4j graph).
    """

    LANG_EXT_MAP = {
        "python": ".py",
        "nix": ".nix",
        "bash": ".sh",
        "sh": ".sh",
        "c": ".c",
        "cpp": ".cpp",
        "rust": ".rs",
        "json": ".json",
        "yaml": ".yaml",
        "toml": ".toml",
        "javascript": ".js",
        "typescript": ".ts",
        "markdown": ".md",
        "text": ".txt",
    }

    PREDICTION_SYSTEM_PROMPT = """You are an architectural metadata prediction engine.
Analyze the user instruction, extracted code snippet, and structural AST facts to predict a semantic title and high-level concept tags.
OUTPUT FORMAT RULES:
Return ONLY a valid, raw JSON object with NO markdown code fences:
{
  "predicted_title": "<idiomatic_filename_without_extension>",
  "semantic_summary": "<1-2 sentence core idea>",
  "concept_tags": ["tag1", "tag2", "tag3"]
}"""

    def __init__(
        self,
        patcher: Optional[AnchorPatcher] = None,
        analyzer: Optional[CodeAnalyzer] = None,
        store: Any = None,
        orchestrator: Optional['ReasoningOrchestrator'] = None,
    ):
        self.patcher = patcher or AnchorPatcher()
        self.analyzer = analyzer or CodeAnalyzer()
        self.store = store
        
        # Local import breaks the circular dependency chain
        if orchestrator is None:
            from reasoning.pipeline import ReasoningOrchestrator
            self.orchestrator = ReasoningOrchestrator()
        else:
            self.orchestrator = orchestrator

    def record_frame(
        self,
        instruction: str,
        raw_response: str,
        filepath: str,
        code: str = "",
        reasoning_plan: Any = None,
        original_code: str = "",
        updated_code: str = "",
        ast_facts: Optional[Dict[str, Any]] = None,
        coverage_metrics: Optional[Dict[str, Any]] = None,
    ) -> ThoughtFrame:
        """Records a structured dual-process reasoning, plan, and synthesis frame into memory and 3-tier stores."""
        structured_plan = self._formulate_dual_process_plan(reasoning_plan)

        ext = Path(filepath).suffix.lower() if filepath else ".txt"
        lang = self.patcher._detect_language(filepath)
        final_code = updated_code or code

        resolved_ast = ast_facts or self.patcher.extract_ast_facts(filepath, final_code)

        frame = ThoughtFrame(
            instruction=instruction,
            reasoning_plan=structured_plan,
            raw_response=raw_response,
            original_code=original_code,
            extracted_code=final_code,
            resolved_path=filepath,
            language=lang,
            ast_facts=resolved_ast,
            verification_passed=True,
            coverage_metrics=coverage_metrics or {},
        )

        self._persist_frame(frame)
        return frame

    def process_synthesis(
        self,
        instruction: str,
        raw_llm_response: str,
        llm_client: Any,
        explicit_target: Optional[Path] = None,
        original_code: str = "",
        reasoning_plan: Any = None,
        coverage_metrics: Optional[Dict[str, Any]] = None,
    ) -> ThoughtFrame:
        """Executes the complete Code ➔ Sanitize/Lint ➔ Analyze ➔ Predict Title ➔ Verify pipeline."""
        blocks: List[PatchBlock] = self.patcher.parse_blocks(raw_llm_response)
        if not blocks:
            code_content = raw_llm_response.strip()
            lang = (
                "python"
                if "def " in code_content or "import " in code_content
                else "text"
            )
        else:
            code_content = blocks[0].replace_block
            lang = blocks[0].language

        code_content = self._sanitize_code_content(code_content)
        ext = self.LANG_EXT_MAP.get(lang, f".{lang}")
        syntax_ok = self.patcher._validate_syntax(ext, code_content)
        ast_facts = self.patcher.extract_ast_facts(str(explicit_target) if explicit_target else "", code_content)

        structured_plan = self._formulate_dual_process_plan(reasoning_plan)

        frame = ThoughtFrame(
            instruction=instruction,
            reasoning_plan=structured_plan,
            raw_response=raw_llm_response,
            original_code=original_code,
            extracted_code=code_content,
            language=lang,
            ast_facts=ast_facts,
            verification_passed=syntax_ok,
            coverage_metrics=coverage_metrics or {},
        )

        prediction_payload = self._predict_semantic_metadata(llm_client, frame)
        frame.predicted_title = prediction_payload.get(
            "predicted_title", "synthesized_module"
        )
        frame.semantic_summary = prediction_payload.get(
            "semantic_summary", "Synthesized module."
        )
        frame.concept_tags = prediction_payload.get(
            "concept_tags", [lang, "synthesis"]
        )

        if explicit_target and not explicit_target.is_dir():
            frame.resolved_path = str(explicit_target)
        else:
            filename = f"{frame.predicted_title}{ext}"
            frame.resolved_path = str(
                explicit_target / filename if explicit_target else Path(filename)
            )

        self._persist_frame(frame)
        return frame

    def _formulate_dual_process_plan(self, reasoning_plan: Any) -> Dict[str, Any]:
        """Structures plans into neural generation traces and symbolic constraints."""
        if isinstance(reasoning_plan, str):
            constraints = [
                line.strip() for line in reasoning_plan.splitlines()
                if line.strip() and not line.strip().startswith("```")
            ]
            return {
                "neural_trace": reasoning_plan,
                "symbolic_constraints": constraints,
                "mode": "contemplation"
            }
        elif isinstance(reasoning_plan, dict):
            if "neural_trace" not in reasoning_plan:
                reasoning_plan["neural_trace"] = json.dumps(reasoning_plan)
            if "symbolic_constraints" not in reasoning_plan:
                reasoning_plan["symbolic_constraints"] = []
            if "mode" not in reasoning_plan:
                reasoning_plan["mode"] = "contemplation"
            return reasoning_plan
        return {"neural_trace": "", "symbolic_constraints": [], "mode": "standard"}

    def _persist_frame(self, frame: ThoughtFrame) -> None:
        """Pushes ThoughtFrame through the unified 3-tier ReasoningOrchestrator and Redis store."""
        if self.orchestrator:
            try:
                self.orchestrator.process_and_store(frame)
                print(f"[cyan]🌐 3-Tier Synchronized (Redis, Vector, Neo4j):[/cyan] session_id={frame.session_id}")
                return
            except Exception as e:
                logger.warning("Failed 3-tier orchestration sync, falling back to Redis: %s", e)

        if self.store and hasattr(self.store, "save_thought_frame"):
            try:
                self.store.save_thought_frame(frame)
                print(f"[cyan]🎫 Redis Ticket Stored:[/cyan] session_id={frame.session_id}")
            except Exception as e:
                logger.warning("Failed to store ThoughtFrame in Redis: %s", e)

    def _sanitize_code_content(self, code: str) -> str:
        lines = code.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        sanitized = "\n".join(lines).strip()
        return sanitized + "\n"

    def _predict_semantic_metadata(
        self, llm_client: Any, frame: ThoughtFrame
    ) -> Dict[str, Any]:
        code_preview = "\n".join(frame.extracted_code.splitlines()[:12])
        user_prompt = f"""USER INSTRUCTION:{frame.instruction}STRUCTURAL AST FACTS:{json.dumps(frame.ast_facts, indent=2)}CODE SNIPPET (PREVIEW):{code_preview}"""
        try:
            raw_pred = llm_client.generate_stream(
                system_prompt=self.PREDICTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            cleaned = raw_pred.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0].strip()
            return json.loads(cleaned)
        except Exception:
            funcs = frame.ast_facts.get("functions", [])
            fallback_title = (
                funcs[0].lower().replace("check_", "") if funcs else "module"
            )
            return {
                "predicted_title": fallback_title,
                "semantic_summary": "Synthesized code unit.",
                "concept_tags": [frame.language, "generated"],
            }
