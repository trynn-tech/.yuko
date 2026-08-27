# src/memory/working_memory.py

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid

from coordinator.pachinko import DispatchDecision, OperationalIntent, PachinkoRouter
from engine.analyzer import CodeAnalyzer
from engine.anchor_patch import AnchorPatcher
from .schemas import ThoughtFrame
from .thoughtframe_collection import ThoughtFrameFactory

if TYPE_CHECKING:
    from reasoning.pipeline import ReasoningOrchestrator

logger = logging.getLogger(__name__)


class WorkingMemoryPipeline:
    """Orchestrates intent routing, code parsing, AST extraction, semantic metadata prediction, and 3-tier persistence."""

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
        router: Optional[PachinkoRouter] = None,
        patcher: Optional[AnchorPatcher] = None,
        analyzer: Optional[CodeAnalyzer] = None,
        store: Any = None,
        redis_store: Any = None,
        orchestrator: Optional["ReasoningOrchestrator"] = None,
        llm_client: Any = None,
    ):
        self.router = router or PachinkoRouter()
        self.patcher = patcher or AnchorPatcher()
        self.analyzer = analyzer or CodeAnalyzer()
        self.store = redis_store or store
        self.llm_client = llm_client

        if orchestrator is None:
            try:
                from reasoning.pipeline import ReasoningOrchestrator

                # Pass injected store to orchestrator so mock stores in tests receive save_thought_frame calls
                self.orchestrator = ReasoningOrchestrator(
                    redis_store=self.store
                )
            except ImportError:
                self.orchestrator = None
        else:
            self.orchestrator = orchestrator

    def process_incoming_event(
        self,
        session_id: Optional[str] = None,
        prompt: str = "",
        raw_response: str = "",
        filepath: str = "src/main.py",
        code: str = "",
        workspace_context: Optional[List[str]] = None,
        llm_client: Any = None,
        **kwargs,
    ) -> ThoughtFrame:
        """Compatibility wrapper for pipeline event ingestion tested in test suites."""
        sid = session_id or str(uuid.uuid4())[:8]
        content = code or raw_response or prompt
        ctx = workspace_context or []

        frame = self.process_synthesis(
            instruction=prompt or "Process incoming event",
            raw_llm_response=content,
            workspace_context=ctx,
            requested_path=filepath,
            original_code=code,
            llm_client=llm_client or self.llm_client,
        )
        frame.session_id = sid

        # process_synthesis already invokes _persist_frame; re-persist if sid was updated
        self._persist_frame(frame)
        return frame

    def process_synthesis(
        self,
        instruction: str,
        raw_llm_response: str,
        workspace_context: List[str],
        requested_path: str,
        original_code: str = "",
        llm_client: Any = None,
    ) -> ThoughtFrame:
        session_id = str(uuid.uuid4())[:8]

        # 1. Direct intent evaluation using PachinkoRouter
        decision: DispatchDecision = self.router.route_target(
            requested_path, workspace_context
        )
        resolved_path = str(decision.target_path)

        # 2. Sanitize output and extract AST details via CodeAnalyzer
        code_content = self._sanitize_code_content(raw_llm_response)
        ast_facts = self.analyzer.extract_facts(
            code_content, filepath=resolved_path
        )

        # 3. Factory dispatch based on Pachinko OperationalIntent
        if decision.intent in (
            OperationalIntent.EDIT_EXACT,
            OperationalIntent.EDIT_FUZZY_APPEND,
            OperationalIntent.EDIT,
            OperationalIntent.PATCH,
        ):
            base_content = original_code
            if not base_content and decision.target_path.exists():
                try:
                    base_content = decision.target_path.read_text(
                        encoding="utf-8"
                    )
                except Exception as e:
                    logger.warning(
                        "Could not read original file %s: %s",
                        resolved_path,
                        e,
                    )
            frame = ThoughtFrameFactory.create_edit_frame(
                session_id=session_id,
                target_file=resolved_path,
                original_content=base_content,
                updated_content=code_content,
                raw_prompt=instruction,
                ast_facts=ast_facts,
            )
        else:
            frame = ThoughtFrameFactory.create_creation_frame(
                session_id=session_id,
                target_file=resolved_path,
                created_content=code_content,
                raw_prompt=instruction,
                ast_facts=ast_facts,
            )

        # 4. Synthesize Semantic Metadata (Summary, Tags, Title)
        client = llm_client or self.llm_client
        prediction_payload = self._predict_semantic_metadata(
            client=client,
            instruction=instruction,
            code=code_content,
            ast_facts=ast_facts,
            lang=getattr(frame, "language", "python"),
        )

        frame.predicted_title = prediction_payload.get(
            "predicted_title", Path(resolved_path).stem
        )
        frame.semantic_summary = prediction_payload.get(
            "semantic_summary", "Synthesized code unit."
        )
        frame.concept_tags = prediction_payload.get(
            "concept_tags", ["synthesis", getattr(frame, "language", "python")]
        )

        # 5. Persist Frame across 3-tier memory & stores
        self._persist_frame(frame)
        return frame

    def _sanitize_code_content(self, code: str) -> str:
        lines = code.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip() + "\n"

    def _predict_semantic_metadata(
        self,
        client: Any,
        instruction: str,
        code: str,
        ast_facts: Dict[str, Any],
        lang: str = "python",
    ) -> Dict[str, Any]:
        """Queries LLM or provides structural fallback for semantic summaries & concept tags."""
        funcs = ast_facts.get("functions", [])
        classes = ast_facts.get("classes", [])
        symbols = (
            funcs
            + classes
            + ast_facts.get("symbols", [])
            + ast_facts.get("symbols_modified", [])
        )
        fallback_tags = list(set([lang, "synthesis"] + symbols[:3]))
        fallback_title = (
            classes[0].lower()
            if classes
            else (funcs[0].lower() if funcs else "synthesized_module")
        )
        fallback = {
            "predicted_title": fallback_title,
            "semantic_summary": f"Synthesized {lang} module implementing {', '.join(symbols) if symbols else 'requested logic'}.",
            "concept_tags": fallback_tags,
        }

        if not client or not hasattr(client, "generate_stream"):
            return fallback

        code_preview = "\n".join(code.splitlines()[:12])
        user_prompt = f"USER INSTRUCTION:{instruction}\nSTRUCTURAL AST FACTS:{json.dumps(ast_facts, indent=2)}\nCODE SNIPPET (PREVIEW):\n{code_preview}"

        try:
            raw_pred = client.generate_stream(
                system_prompt=self.PREDICTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            cleaned = raw_pred.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0].strip()
            res = json.loads(cleaned)
            return {
                "predicted_title": res.get("predicted_title", fallback_title),
                "semantic_summary": res.get(
                    "semantic_summary", fallback["semantic_summary"]
                ),
                "concept_tags": res.get("concept_tags", fallback_tags),
            }
        except Exception as e:
            logger.warning("Failed metadata prediction LLM call: %s", e)
            return fallback

    def _persist_frame(self, frame: ThoughtFrame) -> None:
        """Pushes ThoughtFrame through 3-tier orchestrator (Redis, Vector, Neo4j) and fallback stores."""
        if self.orchestrator and hasattr(self.orchestrator, "process_and_store"):
            try:
                self.orchestrator.process_and_store(frame)
                return
            except Exception as e:
                logger.warning(
                    "Failed 3-tier orchestration sync, falling back to direct store: %s",
                    e,
                )

        if self.store and hasattr(self.store, "save_thought_frame"):
            try:
                self.store.save_thought_frame(frame)
            except Exception as e:
                logger.warning("Failed to store ThoughtFrame in Redis: %s", e)
