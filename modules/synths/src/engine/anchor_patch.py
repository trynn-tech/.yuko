#!/usr/bin/env python3
# modules/synths/src/engine/anchor_patch.py

import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

# -------------------------------------------------------------------
# Hermetic Tree-Sitter Setup (Nix-Provided Grammars)
# -------------------------------------------------------------------
HAS_TREE_SITTER = False
LANGUAGES: Dict[str, object] = {}

try:
    from tree_sitter import Language, Parser
    import tree_sitter_bash as tsbash
    import tree_sitter_c as tsc
    import tree_sitter_nix as tsnix
    import tree_sitter_python as tspython

    LANGUAGES = {
        ".nix": Language(tsnix.language()),
        ".py": Language(tspython.language()),
        ".sh": Language(tsbash.language()),
        ".bash": Language(tsbash.language()),
        ".c": Language(tsc.language()),
        ".h": Language(tsc.language()),
    }
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


class PatchBlock(BaseModel):
    filepath: str
    search_anchor: str = ""
    replace_block: str = ""
    language: str = "text"


class AnchorPatcher:
    """
    Parses raw model output into structured PatchBlocks using a fault-tolerant multi-language strategy:
    1. Dynamic extension-to-syntax language mapping for UI highlight rendering.
    2. Token-sanitize incoming LLM text (normalizing backtick-wrapped paths and double-fenced output).
    3. Parse explicit SEARCH/REPLACE blocks.
    4. Extract code blocks with Tree-Sitter / AST / JSON syntax validation.
    """

    EXT_LANG_MAP = {
        ".py": "python",
        ".nix": "nix",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".rs": "rust",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".tom": "toml",
        ".toml": "toml",
        ".js": "javascript",
        ".ts": "typescript",
    }

    def _detect_language(self, filepath: str) -> str:
        """Maps target file extension to a Rich-compatible syntax highlighting key."""
        ext = Path(filepath).suffix.lower()
        return self.EXT_LANG_MAP.get(ext, "text")

    def parse_blocks(self, raw_output: str) -> List[PatchBlock]:
        blocks: List[PatchBlock] = []

        # ------------------------------------------------------------------
        # Token Pre-Sanitization
        # ------------------------------------------------------------------
        # Convert ```app/heartbeat.py or ```python app/heartbeat.py to standard "FILE: app/heartbeat.py"
        sanitized = re.sub(
            r"^```(?:[a-zA-Z0-9_-]+)?\s*([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)\s*$",
            r"FILE: \1",
            raw_output,
            flags=re.MULTILINE,
        )

        # Split output into per-file sections on "FILE:"
        file_sections = re.split(r"^FILE:\s*", sanitized, flags=re.MULTILINE)

        for section in file_sections:
            if not section.strip():
                continue

            lines = section.splitlines()

            # Extract and sanitize the target path header
            raw_filepath = lines[0].strip()
            filepath = re.sub(r"^[`'\s]+|[`'\s]+$", "", raw_filepath)

            body = "\n".join(lines[1:]).strip()

            if not filepath or not body or filepath.startswith("```"):
                continue

            lang = self._detect_language(filepath)

            # Strategy A: SEARCH/REPLACE Edit Blocks
            if (
                "<<<<<<< SEARCH" in body
                and "=======" in body
                and ">>>>>>> REPLACE" in body
            ):
                pattern = (
                    r"<<<<<<< SEARCH\n(.*?)=======\n(.*?)>>>>>>> REPLACE"
                )
                matches = re.findall(pattern, body, re.DOTALL)
                for search, replace in matches:
                    blocks.append(
                        PatchBlock(
                            filepath=filepath,
                            search_anchor=search,
                            replace_block=replace,
                            language=lang,
                        )
                    )

            # Strategy B: Creation / Full Replacement Block
            else:
                extracted_code = self._extract_code_fault_tolerant(filepath, body)
                blocks.append(
                    PatchBlock(
                        filepath=filepath,
                        search_anchor="",
                        replace_block=extracted_code,
                        language=lang,
                    )
                )

        return blocks

    def _extract_code_fault_tolerant(self, filepath: str, text: str) -> str:
        """
        Extracts valid code from LLM output using layered multi-language resilience:
        1. Fence-based Extraction + Language Validation
        2. Heuristic Regex Cleanup + Language Validation
        3. Raw Content Fallback
        """
        ext = Path(filepath).suffix.lower()

        # ------------------------------------------------------------------
        # Layer 1: Extract code within standard backtick fences (```python ... ```)
        # ------------------------------------------------------------------
        fence_match = re.search(
            r"```(?:[a-zA-Z0-9_-]+)?\n(.*?)```", text, re.DOTALL
        )
        if fence_match:
            candidate = fence_match.group(1).strip()
            if self._validate_syntax(ext, candidate):
                return candidate + "\n"

        # ------------------------------------------------------------------
        # Layer 2: Heuristic Cleanup (strip unclosed leading/trailing fences)
        # ------------------------------------------------------------------
        cleaned = text.strip()
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

        if self._validate_syntax(ext, cleaned):
            return cleaned + "\n"

        # ------------------------------------------------------------------
        # Layer 3: Graceful Degraded Fallback
        # ------------------------------------------------------------------
        return cleaned + "\n"

    def _validate_syntax(self, ext: str, code: str) -> bool:
        """
        Validates syntax against extension rules using Nix Tree-Sitter grammars or stdlib parsers.
        Returns True if code compiles without syntax errors or if no parser is available.
        """
        if not code.strip():
            return False

        # 1. Primary Validator: Nix-bound Tree-Sitter (.nix, .py, .sh, .c)
        if HAS_TREE_SITTER and ext in LANGUAGES:
            try:
                parser = Parser(LANGUAGES[ext])
                tree = parser.parse(bytes(code, "utf-8"))
                return not tree.root_node.has_error
            except Exception:
                pass

        # 2. Secondary Validator: Native Python AST Fallback
        if ext == ".py":
            try:
                ast.parse(code)
                return True
            except (SyntaxError, ValueError, TypeError):
                return False

        # 3. Secondary Validator: Native JSON Parser
        elif ext == ".json":
            try:
                json.loads(code)
                return True
            except ValueError:
                return False

        # Default pass-through for extensions without formal parsers (Markdown, Plaintext, etc.)
        return True

    def locate_fuzzy_anchor(
        self, content: str, search_anchor: str
    ) -> Optional[tuple[int, int, float]]:
        """
        Locates the start and end line indices of a search anchor using exact
        or whitespace-normalized matching.
        """
        norm_search = search_anchor.strip()
        if not norm_search:
            return None

        # Direct string hit
        if norm_search in content:
            lines = content.splitlines()
            search_lines = norm_search.splitlines()
            for i in range(len(lines) - len(search_lines) + 1):
                if "\n".join(lines[i : i + len(search_lines)]).strip() == norm_search:
                    return (i, i + len(search_lines), 100.0)

        # Line-by-line whitespace-insensitive hit
        content_lines = [l.strip() for l in content.splitlines()]
        anchor_lines = [l.strip() for l in search_anchor.splitlines() if l.strip()]

        if not anchor_lines:
            return None

        for i in range(len(content_lines) - len(anchor_lines) + 1):
            window = content_lines[i : i + len(anchor_lines)]
            if window == anchor_lines:
                return (i, i + len(anchor_lines), 90.0)

        return None
