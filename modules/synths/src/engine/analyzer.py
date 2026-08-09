#!/usr/bin/env python3
# modules/synths/src/engine/analyzer.py
import ast
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

HAS_TREE_SITTER = False
LANGUAGES: Dict[str, Any] = {}
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from tree_sitter import Language, Parser
        import tree_sitter_bash as tsbash
        import tree_sitter_nix as tsnix
        import tree_sitter_python as tspython
        LANGUAGES = {
            ".py": Language(tspython.language()),
            ".nix": Language(tsnix.language()),
            ".sh": Language(tsbash.language()),
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
                "line_count": len(code.splitlines()) if code else 0,
                "character_count": len(code) if code else 0,
            },
        }
        if not code or not code.strip():
            return facts
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
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
        except Exception:
            pass
        return facts

    def analyze(self, code: str, user_instruction: str = "") -> CodeAnalysis:
        """Structured analysis returning a Pydantic CodeAnalysis model."""
        facts = self.extract_facts(code)
        if not code or not code.strip():
            return CodeAnalysis(
                language="text", extension=".txt", suggested_filename="note.txt"
            )
        if "def " in code or "import " in code or facts["functions"] or facts["classes"]:
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
        elif "{" in code and ("pkgs" in code or "stdenv" in code or "=" in code):
            return CodeAnalysis(
                language="nix", extension=".nix", suggested_filename="default.nix"
            )
        elif code.startswith("#!") or "echo " in code or "export " in code:
            return CodeAnalysis(
                language="bash", extension=".sh", suggested_filename="script.sh"
            )
        return CodeAnalysis(
            language="text", extension=".txt", suggested_filename="note.txt"
        )
