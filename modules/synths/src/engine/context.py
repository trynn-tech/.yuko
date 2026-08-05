#!/usr/bin/env python3
# modules/synths/src/engine/context.py

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel


class FileContext(BaseModel):
    path: Path
    relative_path: str
    content: str = ""
    exists: bool = True


class RepoContext:
    """Discovers repository structure and builds prompts using ripgrep & fd."""

    def __init__(self, root_path: Optional[Path] = None):
        self.root_path = (root_path or Path.cwd()).resolve()
        self.has_rg = shutil.which("rg") is not None
        self.has_fd = shutil.which("fd") is not None

    def resolve_path_recursively(self, target: str) -> Optional[Path]:
        """
        Attempts to resolve a path. If non-existent relative to root,
        uses `fd` to locate matching filename recursively under root_path.
        """
        candidate = Path(target)
        if candidate.is_absolute():
            direct_path = candidate
        else:
            direct_path = (self.root_path / target).resolve()

        if direct_path.exists():
            return direct_path

        if self.has_fd:
            filename = candidate.name
            try:
                cmd = ["fd", "-H", "-I", "--type", "f", f"^{filename}$", str(self.root_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                matches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                if matches:
                    return Path(matches[0]).resolve()
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

        return None

    def find_file_by_anchor(self, search_anchor: str) -> Optional[Path]:
        """Uses `ripgrep` to locate which file in the workspace contains the anchor."""
        if not self.has_rg or not search_anchor.strip():
            return None

        lines = [l.strip() for l in search_anchor.splitlines() if l.strip()]
        if not lines:
            return None

        query = lines[0]
        try:
            cmd = ["rg", "--fixed-strings", "--files-with-matches", query, str(self.root_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            matches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if matches:
                return Path(matches[0]).resolve()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return None

    def build_context(self, target_paths: List[Path]) -> List[FileContext]:
        """Builds context objects for provided target files or directories."""
        contexts: List[FileContext] = []

        for raw_path in target_paths:
            resolved = self.resolve_path_recursively(str(raw_path))
            target = resolved or (self.root_path / raw_path).resolve()

            if target.exists():
                if target.is_file():
                    try:
                        content = target.read_text(encoding="utf-8")
                        rel_path = self._to_rel_path(target)
                        contexts.append(FileContext(path=target, relative_path=rel_path, content=content, exists=True))
                    except Exception:
                        contexts.append(FileContext(path=target, relative_path=str(target), content="", exists=True))
                elif target.is_dir() and self.has_fd:
                    # Target is a workspace directory: discover code files inside
                    try:
                        cmd = ["fd", "--type", "f", "--max-depth", "3", str(target)]
                        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                        discovered = [Path(p) for p in result.stdout.splitlines() if p.strip()]
                        for sub_path in discovered[:10]:  # Limit initial context budget
                            try:
                                content = sub_path.read_text(encoding="utf-8")
                                rel_path = self._to_rel_path(sub_path)
                                contexts.append(FileContext(path=sub_path, relative_path=rel_path, content=content, exists=True))
                            except Exception:
                                pass
                    except subprocess.CalledProcessError:
                        pass
            else:
                # Target path does not exist on disk (New creation target)
                rel_path = self._to_rel_path(target)
                contexts.append(FileContext(path=target, relative_path=rel_path, content="", exists=False))

        return contexts

    def _to_rel_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root_path))
        except ValueError:
            return str(path)
