#!/usr/bin/env python3
# modules/synths/src/engine/executor.py

import shutil
import subprocess
from pathlib import Path
from typing import Optional
import git
from rich.console import Console
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
        self.has_sd = shutil.which("sd") is not None
        self.has_git = shutil.which("git") is not None
        try:
            self.repo = git.Repo(self.repo_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            self.repo = None

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

        # 1. Direct path check
        if not target_file.is_absolute():
            target_file = (self.repo_path / target_file).resolve()

        # 2. Path Fallback A: Try locating filename recursively via `fd`
        if not target_file.exists():
            found_path = context_finder.resolve_path_recursively(filepath)
            if found_path:
                console.print(
                    f"[cyan]ℹ Path resolved via fd:[/cyan] {filepath} ➔ {found_path.relative_to(self.repo_path)}"
                )
                target_file = found_path

        # 3. Path Fallback B: Try locating file via `ripgrep` search anchor matching
        if not target_file.exists() and search_anchor:
            found_path = context_finder.find_file_by_anchor(search_anchor)
            if found_path:
                console.print(
                    f"[cyan]ℹ File located via ripgrep anchor:[/cyan] {found_path.relative_to(self.repo_path)}"
                )
                target_file = found_path

        # Proceed with brand-new file creation if still not found
        was_created = not target_file.exists()
        if was_created or not search_anchor.strip():
            return self._create_file(target_file, replace_block)

        # Read original file contents from disk
        try:
            original_content = target_file.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Failed to read target file {target_file.name}:[/red] {e}")
            return False

        # Checkpoint Git state before attempting modifications
        stash_created = self._git_checkpoint(target_file)

        # Normalize line endings for reliable matching
        norm_search = search_anchor.replace("\r\n", "\n")
        norm_replace = replace_block.replace("\r\n", "\n")
        norm_content = original_content.replace("\r\n", "\n")

        success = False

        # Strategy 1: Fast direct literal replacement via `sd` binary
        if self.has_sd and norm_search in norm_content:
            success = self._apply_via_sd(target_file, norm_search, norm_replace)

        # Strategy 2: Direct Python-level string substitution
        if not success and norm_search in norm_content:
            success = self._apply_via_python(
                target_file, norm_content, norm_search, norm_replace
            )

        # Strategy 3: Indentation-insensitive fuzzy line-splice fallback
        if not success:
            success = self._apply_fuzzy_splice(
                target_file, norm_content, norm_search, norm_replace
            )

        # Verify result or rollback
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
        """Executes non-regex literal string replacement using `sd -s`."""
        try:
            cmd = ["sd", "-s", search, replace, str(target_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _apply_via_python(
        self, target_file: Path, content: str, search: str, replace: str
    ) -> bool:
        """Direct single-occurrence Python string substitution."""
        if content.count(search) > 1:
            console.print(
                "[yellow]Warning:[/yellow] Search anchor matched multiple locations. Targeting first match."
            )
        new_content = content.replace(search, replace, 1)
        return self._write_file_safe(target_file, new_content)

    def _apply_fuzzy_splice(
        self, target_file: Path, content: str, search: str, replace: str
    ) -> bool:
        """
        Indentation-insensitive fallback: Matches lines stripped of whitespace
        and splices the edit into place while keeping line layout clean.
        """
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
        """Creates parent directories and writes a new file safely."""
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
        """Ensures parent directory existence and writes content to disk."""
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content, encoding="utf-8")
            return True
        except (PermissionError, OSError) as e:
            console.print(f"[red]Write failed for {target_file.name}:[/red] {e}")
            return False

    def _git_checkpoint(self, target_file: Path) -> bool:
        """Checks if file is dirty or untracked within a Git repository."""
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
        """Restores file to previous state or unlinks if it was newly created."""
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

        # Manual fallback rollback
        self._write_file_safe(target_file, original_content)
