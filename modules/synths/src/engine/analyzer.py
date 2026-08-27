#!/usr/bin/env python3
# modules/synths/src/engine/analyzer.py

import ast
import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

HAS_TREE_SITTER = False
LANGUAGES: Dict[str, Any] = {}
Parser: Any = None

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from tree_sitter import Parser as TSParser
        import tree_sitter_bash as tsbash
        import tree_sitter_nix as tsnix
        import tree_sitter_python as tspython

        Parser = TSParser
        LANGUAGES = {
            ".py": tspython.language(),
            ".nix": tsnix.language(),
            ".sh": tsbash.language(),
            ".bash": tsbash.language(),
        }
        HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


class CodeAnalysis(BaseModel):
    language: str
    extension: str
    functions: List[str] = []
    classes: List[str] = []
    imports: List[str] = []
    suggested_filename: str = "generated_module.py"


class CodeAnalyzer:
    """Analyzes AST structures across languages, extracts top-level facts for graph context,
    decorates symbolic DSL annotations, and infers file metadata with fault tolerance.
    """

    EXT_LANG_MAP = {
        ".py": "python",
        ".nix": "nix",
        ".sh": "bash",
        ".bash": "bash",
    }

    def extract_facts(self, code: str, filepath: str = "") -> Dict[str, Any]:
        """Extracts structural AST facts (functions, classes, imports, complexity metrics).
        Uses Python AST for `.py` and Tree-Sitter as a multi-language fallback.
        """
        facts: Dict[str, Any] = {
            "functions": [],
            "classes": [],
            "imports": [],
            "complexity_metrics": {
                "line_count": len(code.splitlines()) if code else 0,
                "character_count": len(code) if code else 0,
            },
        }

        if not code or not code.strip():
            return facts

        ext = Path(filepath).suffix.lower() if filepath else ""

        # 1. Primary Python AST Pass
        if ext == ".py" or not ext:
            parsed_tree = self._parse_python_ast(code)
            if parsed_tree:
                for node in ast.iter_child_nodes(parsed_tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name not in facts["functions"]:
                            facts["functions"].append(node.name)
                    elif isinstance(node, ast.ClassDef):
                        if node.name not in facts["classes"]:
                            facts["classes"].append(node.name)
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name not in facts["imports"]:
                                facts["imports"].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module not in facts["imports"]:
                            facts["imports"].append(node.module)
                return facts

        # 2. Tree-Sitter Multi-Language Fallback
        if HAS_TREE_SITTER and ext in LANGUAGES and Parser is not None:
            self._extract_via_tree_sitter(code, ext, facts)

        return facts

    def extract_enriched_facts(self, code: str, filepath: str = "") -> Dict[str, Any]:
        """Extracts AST facts and enriches them with formatted symbol tags and module metadata

        for downstream graph linkers (e.g., Neo4j).
        """
        facts = self.extract_facts(code, filepath=filepath)
        analysis = self.analyze(code, filepath=filepath)

        symbols = [f"fn:{fn}" for fn in facts.get("functions", [])] + [
            f"class:{cls}" for cls in facts.get("classes", [])
        ]

        facts["symbols"] = symbols
        facts["symbols_modified"] = symbols
        facts["language"] = analysis.language
        facts["suggested_filename"] = analysis.suggested_filename
        return facts

    def wrap_symbolic_syntax(self, code: str, ast_facts: Dict[str, Any]) -> str:
        """Injects symbolic annotations ('@') into function definitions for custom reasoning DSL parsing."""
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

    def analyze(
        self, code: str, user_instruction: str = "", filepath: str = ""
    ) -> CodeAnalysis:
        """Structured analysis returning a Pydantic CodeAnalysis model."""
        facts = self.extract_facts(code, filepath=filepath)
        if not code or not code.strip():
            return CodeAnalysis(
                language="text", extension=".txt", suggested_filename="note.txt"
            )

        # Detect Python
        if (
            "def " in code
            or "import " in code
            or facts["functions"]
            or facts["classes"]
        ):
            funcs = facts["functions"]
            classes = facts["classes"]
            if funcs:
                filename = f"{funcs[0].lower()}.py"
            elif classes:
                filename = f"{classes[0].lower()}.py"
            else:
                filename = "module.py"
            return CodeAnalysis(
                language="python",
                extension=".py",
                functions=funcs,
                classes=classes,
                imports=facts["imports"],
                suggested_filename=filename,
            )

        # Detect Nix
        if "{" in code and (
            "pkgs" in code or "stdenv" in code or "lib." in code or "=" in code
        ):
            return CodeAnalysis(
                language="nix", extension=".nix", suggested_filename="default.nix"
            )

        # Detect Shell/Bash
        if (
            code.startswith("#!")
            or "echo " in code
            or "export " in code
            or "set -e" in code
        ):
            return CodeAnalysis(
                language="bash", extension=".sh", suggested_filename="script.sh"
            )

        return CodeAnalysis(
            language="text", extension=".txt", suggested_filename="note.txt"
        )

    def _parse_python_ast(self, code: str) -> Optional[ast.AST]:
        """Attempts Python AST parsing with regex sanitization fallbacks for invalid escape sequences."""
        try:
            return ast.parse(code)
        except (SyntaxError, SyntaxWarning):
            # Fallback: Auto-prefix string literals containing invalid backslashes into raw strings
            sanitized = re.sub(
                r'(?<!r)(["\'])(.*?\\[^"\'nrtbfv\\]+.*?)\1',
                r"r\1\2\1",
                code,
            )
            try:
                return ast.parse(sanitized)
            except Exception:
                return None

    def _extract_via_tree_sitter(
        self, code: str, ext: str, facts: Dict[str, Any]
    ) -> None:
        """Traverses Tree-Sitter AST nodes for Nix, Bash, or fallback Python definitions."""
        try:
            parser = Parser(LANGUAGES[ext])
            tree = parser.parse(bytes(code, "utf-8"))
            func_types = {
                "function_definition",
                "async_function_definition",
                "function_item",
                "binding",
            }
            class_types = {"class_definition", "struct_specifier"}

            def traverse(node):
                if node.type in func_types:
                    name_node = node.child_by_field_name("name")
                    if name_node and name_node.text:
                        fn_name = name_node.text.decode("utf-8")
                        if fn_name not in facts["functions"]:
                            facts["functions"].append(fn_name)
                elif node.type in class_types:
                    name_node = node.child_by_field_name("name")
                    if name_node and name_node.text:
                        cls_name = name_node.text.decode("utf-8")
                        if cls_name not in facts["classes"]:
                            facts["classes"].append(cls_name)
                for child in node.children:
                    traverse(child)

            traverse(tree.root_node)
        except Exception:
            pass
