#!/usr/bin/env python3
# modules/synths/src/engine/analyzer.py

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

try:
    from tree_sitter import Language, Parser
    import tree_sitter_bash as tsbash
    import tree_sitter_nix as tsnix
    import tree_sitter_python as tspython

    HAS_TREE_SITTER = True
    LANGUAGES = {
        ".py": Language(tspython.language()),
        ".nix": Language(tsnix.language()),
        ".sh": Language(tsbash.language()),
    }
except ImportError:
    HAS_TREE_SITTER = False


class CodeAnalysis(BaseModel):
    language: str
    extension: str
    functions: List[str] = []
    classes: List[str] = []
    imports: List[str] = []
    suggested_filename: str = "generated_module"


class CodeAnalyzer:
    """Analyzes AST structures, extracts facts for working memory, and infers file metadata."""

    def extract_facts(self, code: str) -> Dict[str, Any]:
        """
        Extracts structural AST facts (functions, classes, imports, complexity)
        as a raw dictionary for ThoughtFrame serialization.
        """
        facts: Dict[str, Any] = {
            "functions": [],
            "classes": [],
            "imports": [],
            "complexity_metrics": {
                "line_count": len(code.splitlines()),
                "character_count": len(code),
            },
        }

        if not code.strip():
            return facts

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    facts["functions"].append(node.name)
                elif isinstance(node, ast.ClassDef):
                    facts["classes"].append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        facts["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        facts["imports"].append(node.module)
        except Exception:
            pass

        return facts

    def analyze(self, code: str, user_instruction: str) -> CodeAnalysis:
        """Structured analysis returning a Pydantic CodeAnalysis model."""
        facts = self.extract_facts(code)

        if "def " in code or "import " in code:
            funcs = facts["functions"]
            classes = facts["classes"]

            if funcs:
                primary = funcs[0].lower().replace("check_", "").replace("get_", "")
                filename = f"{primary}.py" if primary else "module.py"
            elif classes:
                filename = f"{classes[0].lower()}.py"
            else:
                filename = "app.py"

            return CodeAnalysis(
                language="python",
                extension=".py",
                functions=funcs,
                classes=classes,
                imports=facts["imports"],
                suggested_filename=filename,
            )
        elif "{" in code and "pkgs" in code:
            return CodeAnalysis(
                language="nix", extension=".nix", suggested_filename="default.nix"
            )
        elif code.startswith("#!") or "echo " in code:
            return CodeAnalysis(
                language="bash", extension=".sh", suggested_filename="script.sh"
            )

        return CodeAnalysis(
            language="text", extension=".txt", suggested_filename="note.txt"
        )
