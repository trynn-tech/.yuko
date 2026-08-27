#!/usr/bin/env python3
# modules/synths/src/engine/executor.py

import ast
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import git
from rich.console import Console

from engine.analyzer import CodeAnalyzer
from engine.anchor_patch import AnchorPatcher
from engine.context import RepoContext

console = Console()
logger = logging.getLogger(__name__)


class Executor:
    """Resilient atomic file editor using AST introspection, fuzzy tolerance,
    and Git rollback safety to handle nondeterministic LLM outputs.
    """

    def __init__(self, repo_path: Optional[Path] = None):
        self.repo_path = (repo_path or Path.cwd()).resolve()
        self.patcher = AnchorPatcher()
        self.analyzer = CodeAnalyzer()
        self.has_sd = shutil.which("sd") is not None
        self.has_git = shutil.which("git") is not None
        try:
            self.repo = git.Repo(self.repo_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            self.repo = None

    def _clean_content_payload(self, content: str) -> str:
        """Strips markdown fences and cleans conversational wrapper prose."""
        if not content:
            return ""
        had_trailing_newline = content.endswith("\n")
        cleaned = content.strip()
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        filtered_lines = [
            line
            for line in cleaned.splitlines()
            if not line.strip().startswith("```")
        ]
        cleaned = "\n".join(filtered_lines)
        return cleaned + "\n" if had_trailing_newline else cleaned

    def run_edit_pass(self, *args: Any, **kwargs: Any) -> bool:
        """Universal entry point tolerant to unstructured string blocks, dicts, or objects."""
        if len(args) >= 3:
            return self.apply_resilient_edit(
                str(args[0]), str(args[1]), str(args[2])
            )
        if "filepath" in kwargs and (
            "replace" in kwargs or "replace_block" in kwargs
        ):
            return self.apply_resilient_edit(
                kwargs.get("filepath", ""),
                kwargs.get("search_anchor", kwargs.get("search", "")),
                kwargs.get("replace_block", kwargs.get("replace", "")),
            )
        arg = args[0] if args else kwargs.get("step", kwargs.get("payload", None))
        if arg is None:
            return False

        # 1. Structured payload objects or dicts
        if isinstance(arg, dict) or (
            hasattr(arg, "__dict__") and not isinstance(arg, str)
        ):
            fpath, search, replace = self._extract_payload_fields(arg)
            return self.apply_resilient_edit(fpath, search, replace)

        # 2. Raw string payloads (Unstructured stream blocks)
        if isinstance(arg, str):
            fallback = kwargs.get("fallback_filepath", "main.py")
            blocks = self.patcher.parse_blocks(arg, fallback)
            if not blocks:
                target = Path(fallback)
                if not target.is_absolute():
                    target = (self.repo_path / target).resolve()
                return self.write_file(str(target), arg)
            success_all = True
            for block in blocks:
                res = self.apply_resilient_edit(
                    block.filepath, block.search_anchor, block.replace_block
                )
                if not res:
                    success_all = False
            return success_all
        return False

    def _extract_payload_fields(self, arg: Any) -> Tuple[str, str, str]:
        """Extracts target paths, anchors, and replacement blocks regardless of key naming variation."""
        if isinstance(arg, dict):
            fpath = arg.get(
                "filepath", arg.get("target_file", arg.get("target", ""))
            )
            search = arg.get("search_anchor", arg.get("search", ""))
            replace = arg.get(
                "replace_block", arg.get("replace", arg.get("code", ""))
            )
        else:
            fpath = getattr(
                arg,
                "filepath",
                getattr(arg, "target_file", getattr(arg, "target", "")),
            )
            search = getattr(arg, "search_anchor", getattr(arg, "search", ""))
            replace = getattr(
                arg, "replace_block", getattr(arg, "replace", getattr(arg, "code", ""))
            )
        return str(fpath), str(search), str(replace)

    def apply_resilient_edit(
        self, filepath: str, search_anchor: str, replace_block: str
    ) -> bool:
        """Multi-stage edit pipeline: AST Match -> Exact Search -> Fuzzy Match -> Contextual Fallback."""
        context_finder = RepoContext(root_path=self.repo_path)
        target_file = Path(filepath)
        if not target_file.is_absolute():
            target_file = (self.repo_path / target_file).resolve()
        if target_file.is_dir():
            target_file = target_file / "main.py"

        if not target_file.exists():
            found_path = context_finder.resolve_path_recursively(filepath)
            if found_path:
                target_file = found_path

        if not target_file.exists() and search_anchor:
            found_path = context_finder.find_file_by_anchor(search_anchor)
            if found_path:
                target_file = found_path

        replace_block = self._clean_content_payload(replace_block)
        was_created = not target_file.exists()
        if was_created or not search_anchor.strip():
            return self.write_file(str(target_file), replace_block)

        try:
            original_content = target_file.read_text(encoding="utf-8")
        except Exception as e:
            console.print(
                f"[red]Failed to read target file {target_file.name}:[/red] {e}"
            )
            return False

        # Attempt Stage 1: Explicit or Inferred AST Symbol Target
        symbol_target = self._infer_ast_symbol(
            target_file, original_content, search_anchor, replace_block
        )
        if symbol_target:
            if self.apply_ast_symbol_replace(
                str(target_file), symbol_target, replace_block
            ):
                return True

        # Attempt Stage 2: Exact Text Match (sd / python string replace)
        norm_search = search_anchor.replace("\r\n", "\n").strip()
        norm_replace = replace_block.replace("\r\n", "\n")
        norm_content = original_content.replace("\r\n", "\n")

        if norm_search in norm_content:
            if self.has_sd and self._apply_via_sd(
                target_file, norm_search, norm_replace
            ):
                console.print(f"[green]Patched {target_file.name} via sd[/green]")
                return True
            if self._apply_via_python(
                target_file, norm_content, norm_search, norm_replace
            ):
                console.print(
                    f"[green]Patched {target_file.name} via exact search[/green]"
                )
                return True

        # Attempt Stage 3: Fuzzy Ratio Splicing
        success, line_bounds = self._apply_fuzzy_splice(
            target_file, norm_content, norm_search, norm_replace
        )
        if success and line_bounds:
            console.print(
                f"[green]Fuzzy spliced {target_file.name} [Lines {line_bounds[0]}-{line_bounds[1]}][/green]"
            )
            return True

        # Attempt Stage 4: Append / Structural Recovery Fallback
        if self._apply_structural_fallback(
            target_file, norm_content, replace_block
        ):
            console.print(
                f"[yellow]Applied structural recovery edit to {target_file.name}[/yellow]"
            )
            return True

        console.print(
            f"[red]All edit stages failed for {target_file.name}. Rolling back...[/red]"
        )
        self._rollback(target_file, original_content, was_created)
        return False

    def _infer_ast_symbol(
        self,
        target_file: Path,
        code: str,
        search_anchor: str,
        replace_block: str,
    ) -> Optional[str]:
        """Infers symbol targets (fn:name or class:name) even if the LLM omitted explicit AST prefixing."""
        if search_anchor.startswith(("fn:", "class:")):
            return search_anchor
        if target_file.suffix.lower() != ".py":
            return None

        # Delegate directly to CodeAnalyzer
        facts = self.analyzer.extract_facts(code, filepath=str(target_file))
        anchor_clean = search_anchor.strip()

        # Check for function or class names inside search anchor or replacement header
        for fn in facts.get("functions", []):
            if (
                f"def {fn}" in anchor_clean
                or f"def {fn}" in replace_block
                or anchor_clean == fn
            ):
                return f"fn:{fn}"

        for cls in facts.get("classes", []):
            if (
                f"class {cls}" in anchor_clean
                or f"class {cls}" in replace_block
                or anchor_clean == cls
            ):
                return f"class:{cls}"

        return None

    def apply_ast_symbol_replace(
        self, filepath: str, symbol_target: str, new_code: str
    ) -> bool:
        """Replaces function/class definition AST nodes with adaptive indentation preservation."""
        target_file = Path(filepath)
        if not target_file.is_absolute():
            target_file = (self.repo_path / target_file).resolve()
        if not target_file.exists() or target_file.suffix.lower() != ".py":
            return False

        try:
            code = target_file.read_text(encoding="utf-8")
            tree = ast.parse(code)
            kind, name = (
                symbol_target.split(":", 1)
                if ":" in symbol_target
                else ("fn", symbol_target)
            )

            for node in ast.walk(tree):
                is_fn = kind == "fn" and isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                )
                is_cls = kind == "class" and isinstance(node, ast.ClassDef)
                if (is_fn or is_cls) and getattr(node, "name", "") == name:
                    lines = code.splitlines(keepends=True)
                    start_line = node.lineno - 1
                    end_line = getattr(node, "end_lineno", len(lines))

                    first_line = lines[start_line]
                    indent = first_line[
                        : len(first_line) - len(first_line.lstrip())
                    ]

                    cleaned_code = self._clean_content_payload(new_code)
                    code_lines = cleaned_code.splitlines(keepends=True)

                    # Deduplicate baseline indent if code already contains relative indentation
                    min_code_indent = min(
                        (
                            len(l) - len(l.lstrip())
                            for l in code_lines
                            if l.strip()
                        ),
                        default=0,
                    )

                    formatted = []
                    for line in code_lines:
                        if not line.strip():
                            formatted.append("\n")
                            continue
                        stripped_line = line[min_code_indent:]
                        formatted.append(f"{indent}{stripped_line}")

                    new_lines = (
                        lines[:start_line] + formatted + lines[end_line:]
                    )
                    return self._write_file_safe(target_file, "".join(new_lines))
        except Exception as e:
            logger.warning(f"AST node replacement failed for {filepath}: {e}")
        return False

    def write_file(self, filepath: str, content: str) -> bool:
        """Writes content to disk cleanly, maintaining Git index awareness."""
        target = Path(filepath)
        if not target.is_absolute():
            target = (self.repo_path / target).resolve()
        if target.is_dir():
            target = target / "main.py"

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            cleaned = self._clean_content_payload(content)
            if self._write_file_safe(target, cleaned):
                if self.repo:
                    try:
                        self.repo.git.add(str(target))
                    except Exception:
                        pass
                console.print(f"[green]Wrote file {target.name}[/green]")
                return True
        except Exception as e:
            console.print(f"[red]Error writing file {target}:[/red] {e}")
        return False

    def _apply_via_sd(self, target_file: Path, search: str, replace: str) -> bool:
        try:
            cmd = ["sd", "-s", search, replace, str(target_file)]
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _apply_via_python(
        self, target_file: Path, content: str, search: str, replace: str
    ) -> bool:
        new_content = content.replace(search, replace, 1)
        return self._write_file_safe(target_file, new_content)

    def _apply_fuzzy_splice(
        self, target_file: Path, content: str, search: str, replace: str
    ) -> Tuple[bool, Optional[Tuple[int, int]]]:
        match = self.patcher.locate_fuzzy_anchor(content, search)
        if match:
            start_line, end_line, _ = match
            file_lines = content.splitlines(keepends=True)
            first_line = file_lines[start_line]
            indent_prefix = first_line[
                : len(first_line) - len(first_line.lstrip())
            ]

            replace_lines = replace.splitlines()
            formatted_replacement = [
                f"{indent_prefix}{l.strip()}\n" if l.strip() else "\n"
                for l in replace_lines
            ]

            new_lines = (
                file_lines[:start_line]
                + formatted_replacement
                + file_lines[end_line:]
            )
            write_ok = self._write_file_safe(target_file, "".join(new_lines))
            return write_ok, (start_line + 1, end_line)
        return False, None

    def _apply_structural_fallback(
        self, target_file: Path, content: str, replace_block: str
    ) -> bool:
        """Safely appends complete blocks when search anchors fail entirely."""
        if not replace_block.strip():
            return False
        # Avoid appending duplicate blocks
        if replace_block.strip() in content:
            return True

        separator = "\n\n" if not content.endswith("\n\n") else ""
        new_content = content + separator + replace_block.strip() + "\n"
        return self._write_file_safe(target_file, new_content)

    def _write_file_safe(self, target_file: Path, content: str) -> bool:
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            cleaned = self._clean_content_payload(content)
            target_file.write_text(cleaned, encoding="utf-8")
            return True
        except (PermissionError, OSError) as e:
            console.print(
                f"[red]Write failed for {target_file.name}:[/red] {e}"
            )
            return False

    def _rollback(
        self, target_file: Path, original_content: str, was_created: bool
    ):
        """Restores working tree baseline via Git or file unlinking."""
        if was_created:
            if target_file.exists():
                try:
                    target_file.unlink()
                except OSError:
                    pass
            return

        if self.repo:
            try:
                rel_path = str(target_file.relative_to(self.repo_path))
                self.repo.git.checkout("HEAD", "--", rel_path)
                return
            except Exception:
                pass

        self._write_file_safe(target_file, original_content)
