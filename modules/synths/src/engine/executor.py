#!/usr/bin/env python3
# modules/synths/src/engine/executor.py
import ast
import difflib
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional, Tuple

import git
from rich.console import Console
from engine.anchor_patch import AnchorPatcher
from engine.context import RepoContext

console = Console()


class Executor:
    """
    Handles atomic file modifications using native Nix-provided binaries:
    - `sd` for string/regex operations
    - `git` for tracking, diff creation, and rollback safety
    """

    def __init__(self, repo_path: Optional[Path] = None):
        self.repo_path = (repo_path or Path.cwd()).resolve()
        self.patcher = AnchorPatcher()
        self.has_sd = shutil.which("sd") is not None
        self.has_git = shutil.which("git") is not None
        try:
            self.repo = git.Repo(self.repo_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            self.repo = None

    def _clean_content_payload(self, content: str) -> str:
        """Strips markdown code block backticks/fences while maintaining target string structure."""
        if not content:
            return ""

        # Record whether original content intended a trailing newline
        had_trailing_newline = content.endswith("\n")

        cleaned = content.strip()

        # Remove opening markdown code fences (e.g. ```python, ```bash, ```)
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        # Remove closing markdown code fences
        cleaned = re.sub(r"\n?```$", "", cleaned)

        # Filter isolated fence lines
        lines = cleaned.splitlines()
        filtered_lines = [
            line for line in lines if not line.strip().startswith("```")
        ]
        cleaned = "\n".join(filtered_lines)

        # Only append terminating newline if the original string explicitly had one
        return cleaned + "\n" if had_trailing_newline else cleaned

    def run_edit_pass(self, *args: Any, **kwargs: Any) -> bool:
        """
        Executes an edit pass across multiple call signatures:
        - Exact tuple positional args: (filepath, search_anchor, replace_block)
        - Keyword arguments: filepath=..., replace=...
        - Object/dict/raw string payloads passed via args[0] or step=...
        """
        if len(args) >= 3:
            return self.apply_anchor_edit(str(args[0]), str(args[1]), str(args[2]))

        if "filepath" in kwargs and ("replace" in kwargs or "replace_block" in kwargs):
            return self.apply_anchor_edit(
                kwargs.get("filepath", ""),
                kwargs.get("search_anchor", kwargs.get("search", "")),
                kwargs.get("replace_block", kwargs.get("replace", "")),
            )

        arg = args[0] if args else kwargs.get("step", kwargs.get("payload", None))
        if arg is None:
            return False

        # 1. Object or Dict payloads (Step, DummyStep, or dict)
        is_dict = isinstance(arg, dict)
        has_obj_attr = any(
            hasattr(arg, attr)
            for attr in ("target_file", "filepath", "target", "search_anchor", "search", "replace_block", "replace", "code")
        )

        if is_dict or (has_obj_attr and not isinstance(arg, str)):
            if is_dict:
                fpath = arg.get("filepath", arg.get("target_file", arg.get("target", "")))
                search = arg.get("search_anchor", arg.get("search", ""))
                replace = arg.get("replace_block", arg.get("replace", arg.get("code", "")))
                desc = arg.get("description", "")
            else:
                fpath = getattr(arg, "filepath", getattr(arg, "target_file", getattr(arg, "target", "")))
                search = getattr(arg, "search_anchor", getattr(arg, "search", ""))
                replace = getattr(arg, "replace_block", getattr(arg, "replace", getattr(arg, "code", "")))
                desc = getattr(arg, "description", "")

            if not replace and desc:
                replace = f"# {desc}\n"

            return self.apply_anchor_edit(str(fpath), str(search), str(replace))

        # 2. Raw String Block Payloads (LLM generated string outputs)
        if isinstance(arg, str):
            fallback = kwargs.get("fallback_filepath", "")
            blocks = self.patcher.parse_blocks(arg, fallback)
            if not blocks:
                target = Path(fallback or "generated.py")
                if not target.is_absolute():
                    target = (self.repo_path / target).resolve()
                return self._create_file(target, arg)

            success_all = True
            for block in blocks:
                if block.search_anchor:
                    res = self.apply_anchor_edit(
                        block.filepath, block.search_anchor, block.replace_block
                    )
                else:
                    target = Path(block.filepath)
                    if not target.is_absolute():
                        target = (self.repo_path / target).resolve()
                    res = self._create_file(target, block.replace_block)

                if not res:
                    success_all = False
            return success_all

        return False

    def apply_anchor_edit(
        self,
        filepath: str,
        search_anchor: str,
        replace_block: str,
    ) -> bool:
        context_finder = RepoContext(root_path=self.repo_path)
        target_file = Path(filepath)

        if not target_file.is_absolute():
            target_file = (self.repo_path / target_file).resolve()

        if not target_file.exists():
            found_path = context_finder.resolve_path_recursively(filepath)
            if found_path:
                console.print(
                    f"[cyan]ℹ Path resolved via fd:[/cyan] {filepath} ➔ {found_path.relative_to(self.repo_path)}"
                )
                target_file = found_path

        if not target_file.exists() and search_anchor:
            found_path = context_finder.find_file_by_anchor(search_anchor)
            if found_path:
                console.print(
                    f"[cyan]ℹ File located via ripgrep anchor:[/cyan] {found_path.relative_to(self.repo_path)}"
                )
                target_file = found_path

        replace_block = self._clean_content_payload(replace_block)
        was_created = not target_file.exists()

        if was_created or not search_anchor.strip():
            return self._create_file(target_file, replace_block)

        try:
            original_content = target_file.read_text(encoding="utf-8")
        except Exception as e:
            console.print(
                f"[red]Failed to read target file {target_file.name}:[/red] {e}"
            )
            return False

        stash_created = self._git_checkpoint(target_file)
        norm_search = search_anchor.replace("\r\n", "\n")
        norm_replace = replace_block.replace("\r\n", "\n")
        norm_content = original_content.replace("\r\n", "\n")

        success = False
        line_bounds: Optional[Tuple[int, int]] = None

        if self.has_sd and norm_search in norm_content:
            success = self._apply_via_sd(target_file, norm_search, norm_replace)

        if not success and norm_search in norm_content:
            success = self._apply_via_python(
                target_file, norm_content, norm_search, norm_replace
            )

        if not success:
            success, line_bounds = self._apply_fuzzy_splice(
                target_file, norm_content, norm_search, norm_replace
            )

        if success:
            if line_bounds:
                console.print(
                    f"[green]Successfully spliced {target_file.name} "
                    f"[Lines {line_bounds[0]}-{line_bounds[1]}][/green]"
                )
            else:
                console.print(
                    f"[green]Successfully patched {target_file.name}[/green]"
                )
            return True
        else:
            console.print(
                f"[red]Failed to apply patch to {target_file.name}. Rolling back changes...[/red]"
            )
            self._rollback(
                target_file, original_content, was_created, stash_created
            )
            return False

    def apply_symbolic_edit(
        self, filepath: str, symbol_type: str, symbol_name: str, replace_content: str
    ) -> bool:
        """Deterministically manages symbolic items (like imports or functions) with scope awareness."""
        target_file = Path(filepath)
        if not target_file.is_absolute():
            target_file = (self.repo_path / target_file).resolve()

        if not target_file.exists():
            console.print(
                f"[red]Target file {target_file.name} does not exist for symbolic edit.[/red]"
            )
            return False

        try:
            content = target_file.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Failed to read {target_file.name}:[/red] {e}")
            return False

        lines = content.splitlines()
        success = False
        replace_content = self._clean_content_payload(replace_content).strip()

        if symbol_type == "import":
            escaped_symbol = re.escape(symbol_name)
            import_pattern = re.compile(
                rf"^\s*(?:import\s+{escaped_symbol}|from\s+\S+\s+import\s+.*{escaped_symbol})"
            )
            exists = any(import_pattern.match(l) for l in lines)

            if exists:
                new_lines = [
                    replace_content if import_pattern.match(l) else l for l in lines
                ]
                success = True
            else:
                insert_idx = 0
                for idx, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith(("import ", "from ", "#")) or (
                        stripped.startswith(('"', "'")) and idx < 5
                    ):
                        insert_idx = idx + 1
                    elif stripped and not stripped.startswith(('"', "'")):
                        break

                lines.insert(insert_idx, replace_content)
                new_lines = lines
                success = True

            if success:
                new_content = "\n".join(new_lines) + "\n"
                console.print(
                    f"[green]Successfully synchronized symbolic import '{symbol_name}' in {target_file.name}[/green]"
                )
                return self._write_file_safe(target_file, new_content)

        return False

    def _apply_via_sd(self, target_file: Path, search: str, replace: str) -> bool:
        try:
            cmd = ["sd", "-s", search, replace, str(target_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _apply_via_python(
        self, target_file: Path, content: str, search: str, replace: str
    ) -> bool:
        if content.count(search) > 1:
            console.print(
                "[yellow]Warning:[/yellow] Search anchor matched multiple locations. Targeting first match."
            )
        new_content = content.replace(search, replace, 1)
        return self._write_file_safe(target_file, new_content)

    def _apply_fuzzy_splice(
        self, target_file: Path, content: str, search: str, replace: str
    ) -> Tuple[bool, Optional[Tuple[int, int]]]:
        # Delegate fuzzy matching to AnchorPatcher first
        match = self.patcher.locate_fuzzy_anchor(content, search)
        if match:
            start_line, end_line, _ = match
            file_lines = content.splitlines(keepends=True)
            first_line = file_lines[start_line]
            indent_prefix = first_line[: len(first_line) - len(first_line.lstrip())]

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

    def write_file(self, filepath: str, content: str) -> bool:
        """Public alias for file creation and safe writing."""
        target = Path(filepath)
        if not target.is_absolute():
            target = (self.repo_path / target).resolve()
        return self._create_file(target, content)

    def _create_file(self, target_file: Path, content: str) -> bool:
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            cleaned = self._clean_content_payload(content)
            if self._write_file_safe(target_file, cleaned):
                if self.repo:
                    try:
                        self.repo.git.add(str(target_file))
                    except Exception:
                        pass
                console.print(f"[green]Created new file {target_file.name}[/green]")
                return True
        except Exception as e:
            console.print(f"[red]Error creating file {target_file}:[/red] {e}")
        return False

    def _write_file_safe(self, target_file: Path, content: str) -> bool:
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            cleaned = self._clean_content_payload(content)
            target_file.write_text(cleaned, encoding="utf-8")
            return True
        except (PermissionError, OSError) as e:
            console.print(f"[red]Write failed for {target_file.name}:[/red] {e}")
            return False

    def _git_checkpoint(self, target_file: Path) -> bool:
        if not self.repo:
            return False
        try:
            rel_path = str(target_file.relative_to(self.repo_path))
            return rel_path in self.repo.untracked_files or self.repo.is_dirty(
                path=rel_path
            )
        except Exception:
            return False

    def _rollback(
        self,
        target_file: Path,
        original_content: str,
        was_created: bool,
        stash_created: bool,
    ):
        if was_created:
            if target_file.exists():
                try:
                    target_file.unlink()
                except OSError:
                    pass
            return

        if self.repo and stash_created:
            try:
                rel_path = str(target_file.relative_to(self.repo_path))
                self.repo.git.checkout("HEAD", "--", rel_path)
                return
            except Exception:
                pass

        self._write_file_safe(target_file, original_content)
