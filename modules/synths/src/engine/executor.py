#!/usr/bin/env python3
# modules/synths/src/engine/executor.py
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional
import git
from rich.console import Console
from engine.context import RepoContext
from engine.anchor_patch import AnchorPatcher

console = Console()

class Executor:
    """
    Handles atomic file modifications using native Nix-provided binaries:
    - `sd` for string/regex operations
    - `git` for tracking, diff creation, and rollback safety
    """
    def __init__(self, repo_path: Optional[Path] = None):
        self.repo_path = (repo_path or Path.cwd()).resolve()
        self.has_sd = shutil.which("sd") is not None
        self.has_git = shutil.which("git") is not None
        try:
            self.repo = git.Repo(self.repo_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            self.repo = None

    def run_edit_pass(self, *args: Any, **kwargs: Any) -> bool:
        """
        Orchestrates an edit pass supporting multiple calling conventions from architect.py:
        - run_edit_pass(step_obj)
        - run_edit_pass(filepath, search, replace)
        - run_edit_pass(raw_output: str, fallback_filepath: str = "")
        """
        patcher = AnchorPatcher()

        # 1. Explicit positional arguments: (filepath, search, replace)
        if len(args) >= 3:
            return self.apply_anchor_edit(str(args[0]), str(args[1]), str(args[2]))
        
        # 2. Keyword arguments
        if "filepath" in kwargs and "replace" in kwargs:
            return self.apply_anchor_edit(
                kwargs.get("filepath", ""),
                kwargs.get("search_anchor", kwargs.get("search", "")),
                kwargs.get("replace_block", kwargs.get("replace", ""))
            )

        # 3. Step object or dictionary / string payload
        arg = args[0] if args else kwargs.get("step", kwargs.get("payload", None))
        if arg is not None:
            # Check if object/dict has step attributes
            if hasattr(arg, "target_file") or (isinstance(arg, dict) and "target_file" in arg):
                if isinstance(arg, dict):
                    fpath = arg.get("target_file", "")
                    search = arg.get("search", "")
                    replace = arg.get("replace", "")
                    desc = arg.get("description", "")
                else:
                    fpath = getattr(arg, "target_file", "")
                    search = getattr(arg, "search", "")
                    replace = getattr(arg, "replace", "")
                    desc = getattr(arg, "description", "")
                if not replace and desc:
                    replace = f"# {desc}\n"
                return self.apply_anchor_edit(fpath, search, replace)
            elif isinstance(arg, str):
                fallback = kwargs.get("fallback_filepath", "")
                blocks = patcher.parse_blocks(arg, fallback)
                if not blocks:
                    target = Path(fallback or "generated.py")
                    if not target.is_absolute():
                        target = (self.repo_path / target).resolve()
                    return self._create_file(target, arg)
                success_all = True
                for block in blocks:
                    if block.search_anchor:
                        res = self.apply_anchor_edit(block.filepath, block.search_anchor, block.replace_block)
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
        """
        Applies a patch atomically with recursive path resolution fallback.
        """
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

        was_created = not target_file.exists()
        if was_created or not search_anchor.strip():
            return self._create_file(target_file, replace_block)

        try:
            original_content = target_file.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Failed to read target file {target_file.name}:[/red] {e}")
            return False

        stash_created = self._git_checkpoint(target_file)
        norm_search = search_anchor.replace("\r\n", "\n")
        norm_replace = replace_block.replace("\r\n", "\n")
        norm_content = original_content.replace("\r\n", "\n")
        success = False

        if self.has_sd and norm_search in norm_content:
            success = self._apply_via_sd(target_file, norm_search, norm_replace)

        if not success and norm_search in norm_content:
            success = self._apply_via_python(
                target_file, norm_content, norm_search, norm_replace
            )

        if not success:
            success = self._apply_fuzzy_splice(
                target_file, norm_content, norm_search, norm_replace
            )

        if success:
            console.print(f"[green]Successfully patched {target_file.name}[/green]")
            return True
        else:
            console.print(
                f"[red]Failed to apply patch to {target_file.name}. Rolling back changes...[/red]"
            )
            self._rollback(target_file, original_content, was_created, stash_created)
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
    ) -> bool:
        search_lines = [l.strip() for l in search.splitlines() if l.strip()]
        if not search_lines:
            return False
        file_lines = content.splitlines(keepends=True)
        match_start, match_end = -1, -1
        for i in range(len(file_lines) - len(search_lines) + 1):
            window = [file_lines[i + j].strip() for j in range(len(search_lines))]
            if window == search_lines:
                match_start = i
                match_end = i + len(search_lines)
                break
        if match_start != -1:
            replacement_formatted = (
                replace if replace.endswith("\n") else replace + "\n"
            )
            new_lines = (
                file_lines[:match_start]
                + [replacement_formatted]
                + file_lines[match_end:]
            )
            return self._write_file_safe(target_file, "".join(new_lines))
        return False

    def _create_file(self, target_file: Path, content: str) -> bool:
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            if self._write_file_safe(target_file, content):
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
            target_file.write_text(content, encoding="utf-8")
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
