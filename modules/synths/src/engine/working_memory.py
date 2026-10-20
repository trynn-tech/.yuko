#!/usr/bin/env python3
# modules/synths/src/engine/working_memory.py

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from engine.anchor_patch import AnchorPatcher, PatchBlock
from engine.analyzer import CodeAnalyzer


class ThoughtFrame(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = Field(default_factory=time.time)
    instruction: str
    raw_response: str = ""
    extracted_code: str = ""
    language: str = "text"
    ast_facts: Dict[str, Any] = Field(default_factory=dict)
    concept_tags: List[str] = Field(default_factory=list)
    semantic_summary: str = ""
    predicted_title: str = ""
    resolved_path: Optional[str] = None
    verification_passed: bool = False

    def to_redis_payload(self) -> str:
        return self.model_dump_json(indent=2)


class WorkingMemoryPipeline:
    # Reverse mapping for standard language aliases to valid extensions
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
    ):
        self.patcher = patcher or AnchorPatcher()
        self.analyzer = analyzer or CodeAnalyzer()

    def process_synthesis(
        self,
        instruction: str,
        raw_llm_response: str,
        llm_client: Any,
        explicit_target: Optional[Path] = None,
    ) -> ThoughtFrame:
        """Executes the complete Code ➔ Sanitize/Lint ► Analyze ➔ Predict Title ➔ Verify pipeline."""

        # 1. Extract block using AnchorPatcher
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

        # 2. Lint/Sanitize: Strip lingering outer markdown fences if present
        code_content = self._sanitize_code_content(code_content)

        # 3. Resolve Proper File Extension
        ext = self.LANG_EXT_MAP.get(lang, f".{lang}")

        # 4. Validate Syntax & Extract AST Facts
        syntax_ok = self.patcher._validate_syntax(ext, code_content)
        ast_facts = self.analyzer.extract_facts(code_content)

        frame = ThoughtFrame(
            instruction=instruction,
            raw_response=raw_llm_response,
            extracted_code=code_content,
            language=lang,
            ast_facts=ast_facts,
            verification_passed=syntax_ok,
        )

        # 5. Predict Title & Semantic Metadata
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

        # 6. Path Resolution
        if explicit_target and not explicit_target.is_dir():
            frame.resolved_path = str(explicit_target)
        else:
            filename = f"{frame.predicted_title}{ext}"
            frame.resolved_path = str(
                explicit_target / filename if explicit_target else Path(filename)
            )

        return frame

    def _sanitize_code_content(self, code: str) -> str:
        """Lints code content to ensure backtick fences do not pollute destination files."""
        lines = code.splitlines()
        # Strip leading fence line if matched
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        # Strip trailing fence line if matched
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        sanitized = "\n".join(lines).strip()
        return sanitized + "\n"

    def _predict_semantic_metadata(
        self, llm_client: Any, frame: ThoughtFrame
    ) -> Dict[str, Any]:
        code_preview = "\n".join(frame.extracted_code.splitlines()[:12])

        user_prompt = f"""USER INSTRUCTION:
{frame.instruction}

STRUCTURAL AST FACTS:
{json.dumps(frame.ast_facts, indent=2)}

CODE SNIPPET (PREVIEW):
{code_preview}"""

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
