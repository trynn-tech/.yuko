#!/usr/bin/env python3
# modules/synths/src/engine/anchor_patch.py
import ast
import difflib
import json
import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

# -------------------------------------------------------------------
# Hermetic Tree-Sitter Setup (Compatible with tree-sitter >= 0.22)
# -------------------------------------------------------------------
HAS_TREE_SITTER = False
LANGUAGES: Dict[str, Any] = {}
Parser: Any = None

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from tree_sitter import Parser as TSParser
        import tree_sitter_bash as tsbash
        import tree_sitter_c as tsc
        import tree_sitter_nix as tsnix
        import tree_sitter_python as tspython

        Parser = TSParser
        LANGUAGES = {
            ".nix": tsnix.language(),
            ".py": tspython.language(),
            ".sh": tsbash.language(),
            ".bash": tsbash.language(),
            ".c": tsc.language(),
            ".h": tsc.language(),
        }
        HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


class PatchBlock(BaseModel):
    filepath: str = ""
    search_anchor: str = ""
    replace_block: str = ""
    language: str = "text"


class AnchorPatcher:
    """
    Hermetic neuro-symbolic gatekeeper and parser.
    Translates unconstrained LLM outputs into structured PatchBlocks,
    validates syntax via Tree-Sitter/AST/heuristics, and extracts
    structural topology facts for the knowledge graph.
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
        ".toml": "toml",
        ".js": "javascript",
        ".ts": "typescript",
    }

    def _detect_language(self, filepath: str) -> str:
        if not filepath:
            return "text"
        ext = Path(filepath).suffix.lower()
        return self.EXT_LANG_MAP.get(ext, "text")

    def parse_blocks(
        self, raw_output: str, fallback_filepath: str = ""
    ) -> List[PatchBlock]:
        """Parses raw model output into structured PatchBlocks supporting JSON, SEARCH/REPLACE, and file sections."""
        blocks: List[PatchBlock] = []
        if not raw_output or not raw_output.strip():
            return blocks

        cleaned = raw_output.strip()

        # 1. JSON Payload Parsing Strategy
        json_candidate = cleaned
        if json_candidate.startswith("```json"):
            json_candidate = json_candidate[7:]
        elif json_candidate.startswith("```"):
            json_candidate = json_candidate[3:]
        if json_candidate.endswith("```"):
            json_candidate = json_candidate[:-3]
        json_candidate = json_candidate.strip()

        try:
            data = json.loads(json_candidate)
            if isinstance(data, dict):
                if "search" in data and "replace" in data:
                    fpath = data.get("filepath", fallback_filepath)
                    blocks.append(
                        PatchBlock(
                            filepath=fpath,
                            search_anchor=data["search"],
                            replace_block=data["replace"],
                            language=self._detect_language(fpath),
                        )
                    )
                elif "blocks" in data and isinstance(data["blocks"], list):
                    for b in data["blocks"]:
                        if "search" in b and "replace" in b:
                            fpath = b.get("filepath", fallback_filepath)
                            blocks.append(
                                PatchBlock(
                                    filepath=fpath,
                                    search_anchor=b["search"],
                                    replace_block=b["replace"],
                                    language=self._detect_language(fpath),
                                )
                            )
        except Exception:
            pass

        if not blocks:
            # Strip standard markdown fences for text-based parsing
            lines = cleaned.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

            # 2. SEARCH/REPLACE Block Parsing Strategy
            pattern = re.compile(
                r"(?:FILE:\s*(?P<filepath>[^\n`#]+)\n)?"
                r"(?:[#\s]*SEARCH:?\s*\n)?"
                r"<<<<<<< SEARCH\n"
                r"(?P<search>.*?)"
                r"=======\n"
                r"(?P<replace>.*?)"
                r">>>>>>> REPLACE",
                re.DOTALL | re.MULTILINE,
            )
            matches = list(pattern.finditer(cleaned))
            if matches:
                for match in matches:
                    raw_path = match.group("filepath")
                    filepath = (
                        raw_path.strip() if raw_path else fallback_filepath
                    )
                    filepath = re.sub(r"^[`'\s]+|[`'\s]+$", "", filepath)
                    search = match.group("search")
                    replace = match.group("replace")
                    lang = self._detect_language(filepath)
                    blocks.append(
                        PatchBlock(
                            filepath=filepath,
                            search_anchor=search,
                            replace_block=replace,
                            language=lang,
                        )
                    )

        if not blocks:
            # 3. File Sections / Full-File Replacement Strategy
            file_sections = re.split(r"^FILE:\s*", cleaned, flags=re.MULTILINE)
            if len(file_sections) > 1:
                for section in file_sections:
                    if not section.strip():
                        continue
                    sec_lines = section.splitlines()
                    raw_filepath = sec_lines[0].strip()
                    filepath = re.sub(r"^[`'\s]+|[`'\s]+$", "", raw_filepath)
                    body = "\n".join(sec_lines[1:]).strip()
                    if not filepath or not body or " " in filepath:
                        continue
                    lang = self._detect_language(filepath)
                    extracted_code = self._extract_code_fault_tolerant(
                        filepath, body
                    )
                    if extracted_code.strip():
                        blocks.append(
                            PatchBlock(
                                filepath=filepath,
                                search_anchor="",
                                replace_block=extracted_code,
                                language=lang,
                            )
                        )

        if not blocks:
            # 4. Fallback Single-Pass Extraction
            extracted = self._extract_code_fault_tolerant(
                fallback_filepath, cleaned
            )
            if extracted.strip():
                blocks.append(
                    PatchBlock(
                        filepath=fallback_filepath,
                        search_anchor="",
                        replace_block=extracted,
                        language=self._detect_language(fallback_filepath),
                    )
                )

        # Enforce unique search anchors to prevent multi-hit collision spam
        seen_anchors = set()
        unique_blocks = []
        for block in blocks:
            anchor_key = (block.filepath, block.search_anchor.strip())
            if anchor_key not in seen_anchors or not block.search_anchor.strip():
                seen_anchors.add(anchor_key)
                unique_blocks.append(block)

        return unique_blocks

    def locate_fuzzy_anchor(
        self, content: str, search_anchor: str, threshold: float = 0.75
    ) -> Optional[tuple[int, int, float]]:
        """Locates search anchor positions using exact match followed by indentation-insensitive SequenceMatcher scoring."""
        norm_search = search_anchor.strip()
        if not norm_search:
            return None
        content_lines = content.splitlines()
        anchor_lines = [l for l in search_anchor.splitlines() if l.strip()]
        window_size = len(anchor_lines)
        if not anchor_lines or window_size > len(content_lines):
            return None

        if norm_search in content:
            for i in range(len(content_lines) - window_size + 1):
                if (
                    "\n".join(content_lines[i : i + window_size]).strip()
                    == norm_search
                ):
                    return (i, i + window_size, 100.0)

        best_match: Optional[tuple[int, int, float]] = None
        best_score = 0.0
        target_str = "\n".join(anchor_lines)

        for i in range(len(content_lines) - window_size + 1):
            window_lines = [l.strip() for l in content_lines[i : i + window_size]]
            window_str = "\n".join(window_lines)
            ratio = difflib.SequenceMatcher(None, target_str, window_str).ratio()
            if ratio > best_score and ratio >= threshold:
                best_score = ratio
                best_match = (i, i + window_size, ratio * 100.0)

        return best_match

    def wrap_symbolic_syntax(self, code: str, ast_facts: Dict[str, Any]) -> str:
        """Compresses vector relations and injects symbolic annotations ('@') for custom reasoning DSL parsing."""
        funcs = ast_facts.get("functions", [])
        wrapped_lines = []
        for line in code.splitlines():
            trimmed = line.strip()
            if any(
                trimmed.startswith(f"def {fn}")
                or trimmed.startswith(f"function {fn}")
                for fn in funcs
            ):
                wrapped_lines.append("@symbolic_node(scope='function')")
            wrapped_lines.append(line)
        return "\n".join(wrapped_lines)

    def _extract_code_fault_tolerant(self, filepath: str, text: str) -> str:
        ext = Path(filepath).suffix.lower() if filepath else ""
        fence_matches = list(
            re.finditer(r"```(?:[a-zA-Z0-9_-]+)?\n(.*?)```", text, re.DOTALL)
        )
        if fence_matches:
            best_candidate = ""
            for match in fence_matches:
                candidate = match.group(1).strip()
                if len(candidate) > len(
                    best_candidate
                ) and self._validate_syntax(ext, candidate):
                    best_candidate = candidate
            if best_candidate:
                return best_candidate + "\n"

        cleaned = text.strip()
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
        if self._validate_syntax(ext, cleaned):
            return cleaned + "\n"

        return ""

    def _validate_syntax(self, ext: str, code: str) -> bool:
        """Validates code blocks and filters out conversational prose using heuristic rules and parsers."""
        if not code.strip():
            return False

        lower_code = code.lower()
        prose_phrases = [
            "here is",
            "this file",
            "breakdown of",
            "key components",
            "user's shell",
            "home manager is used",
            "sets up a user",
            "defines a user environment",
            "this nixos configuration",
        ]
        if any(phrase in lower_code for phrase in prose_phrases):
            return False

        lines = code.splitlines()
        prose_line_count = sum(
            1
            for line in lines
            if line.strip().endswith((".", ",", ";"))
            and not line.strip().startswith(
                (
                    "#",
                    "{",
                    "}",
                    "[",
                    "]",
                    "mk",
                    "environment",
                    "home",
                    "programs",
                    "services",
                )
            )
        )
        if len(lines) > 2 and prose_line_count / len(lines) > 0.4:
            return False

        if HAS_TREE_SITTER and ext in LANGUAGES and Parser is not None:
            try:
                parser = Parser(LANGUAGES[ext])
                tree = parser.parse(bytes(code, "utf-8"))
                return not tree.root_node.has_error
            except Exception:
                pass

        if ext == ".py":
            try:
                ast.parse(code)
                return True
            except (SyntaxError, ValueError, TypeError):
                return False
        elif ext == ".json":
            try:
                json.loads(code)
                return True
            except ValueError:
                return False
        elif ext == ".nix":
            if code.count("{") != code.count("}") or code.count(
                "["
            ) != code.count("]"):
                return False
            return True

        return True

    def extract_ast_facts(self, filepath: str, code: str) -> Dict[str, Any]:
        """Extracts top-level functions, classes, imports, and complexity metrics using Python AST and Tree-Sitter."""
        ext = Path(filepath).suffix.lower() if filepath else ""
        facts: Dict[str, Any] = {
            "functions": [],
            "classes": [],
            "imports": [],
            "symbols": [],
            "complexity_metrics": {
                "line_count": len(code.splitlines()),
                "character_count": len(code),
            },
        }
        if not code.strip():
            return facts

        if ext == ".py":
            try:
                parsed = ast.parse(code)
                for node in ast.walk(parsed):
                    if isinstance(node, ast.ClassDef):
                        if node.name not in facts["classes"]:
                            facts["classes"].append(node.name)
                            facts["symbols"].append(f"class:{node.name}")
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name not in facts["functions"]:
                            facts["functions"].append(node.name)
                            facts["symbols"].append(f"fn:{node.name}")
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name not in facts["imports"]:
                                facts["imports"].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module not in facts["imports"]:
                            facts["imports"].append(node.module)

                facts["symbols_modified"] = facts["symbols"]
                return facts
            except Exception:
                pass

        if HAS_TREE_SITTER and ext in LANGUAGES and Parser is not None:
            try:
                parser = Parser(LANGUAGES[ext])
                tree = parser.parse(bytes(code, "utf-8"))
                func_types = {
                    "function_definition",
                    "async_function_definition",
                    "function_item",
                }
                class_types = {
                    "class_definition",
                    "struct_specifier",
                    "class_specifier",
                }
                import_types = {
                    "import_statement",
                    "import_from_statement",
                    "preproc_include",
                }

                def traverse(node):
                    if node.type in func_types:
                        name_node = node.child_by_field_name("name")
                        if name_node and name_node.text:
                            fn_name = name_node.text.decode("utf-8")
                            if fn_name not in facts["functions"]:
                                facts["functions"].append(fn_name)
                                facts["symbols"].append(f"fn:{fn_name}")
                    elif node.type in class_types:
                        name_node = node.child_by_field_name("name") or node.child_by_field_name("type")
                        if name_node and name_node.text:
                            cls_name = name_node.text.decode("utf-8")
                            if cls_name not in facts["classes"]:
                                facts["classes"].append(cls_name)
                                facts["symbols"].append(f"class:{cls_name}")
                    elif node.type in import_types:
                        imp_text = node.text.decode("utf-8").strip()
                        if imp_text not in facts["imports"]:
                            facts["imports"].append(imp_text)

                    for child in node.children:
                        traverse(child)

                traverse(tree.root_node)
                facts["symbols_modified"] = facts["symbols"]
            except Exception:
                pass

        return facts


