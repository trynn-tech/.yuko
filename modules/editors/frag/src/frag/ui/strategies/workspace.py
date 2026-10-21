"""Workspace strategy: create and delete documents from the workspace tree.

new_file()   `:new path/name.py`  or  `n` in workspace mode (relative to the highlighted folder)
delete()     `:rm [n]`  or  `D`   always asks for confirmation in a modal; files only, never folders
Both stay inside the workspace root.
"""

import sys
from pathlib import Path
from typing import Optional

from rich.markup import escape

try:
    from ..base import BaseEditorStrategy
    from ..components.confirm import ConfirmScreen
except (ImportError, ValueError):
    for _parent in Path(__file__).resolve().parents:
        if (_parent / "editor" / "modular_editor.py").exists():
            if str(_parent) not in sys.path:
                sys.path.insert(0, str(_parent))
            break
    from frag.ui.base import BaseEditorStrategy
    from frag.ui.components.confirm import ConfirmScreen


class WorkspaceStrategy(BaseEditorStrategy):
    @property
    def nav(self):
        return self.app.navigation_strategy

    def _err(self, msg: str) -> bool:
        self.app.log_status(f"[bold #ff5555]{escape(msg)}[/bold #ff5555]")
        return False

    def _inside_root(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.nav._get_base_dir())
            return True
        except ValueError:
            return False

    def _target_dir(self) -> Path:
        """Folder of the highlighted node (a file's parent), else the workspace root."""
        node = self.app.query_one("#ast-tree").cursor_node
        data = node.data if node is not None else None
        if isinstance(data, dict) and data.get("path"):
            p = Path(data["path"])
            return p if data.get("type") == "directory" else p.parent
        sel = self.nav.workspace_selected
        return sel.parent if sel else self.nav._get_base_dir()

    # --- create ------------------------------------------------------------------

    def new_file(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return self._err("E471: Argument required: :new <name>")
        target = (self._target_dir() / name).resolve()
        if not self._inside_root(target):
            return self._err("E212: Can't create a file outside the workspace")
        if target.exists():
            return self._err(f"E189: \"{target.name}\" exists already")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        except OSError as e:
            return self._err(f"E212: Can't create file: {e}")
        self.app.log_status(f"[bold #00ffaf]Created[/bold #00ffaf] {escape(str(target.relative_to(self.nav._get_base_dir())))}")
        self.nav.workspace_selected = target
        return self.nav.select_block({"type": "file", "path": target})  # opens it and refreshes the tree

    # --- delete ------------------------------------------------------------------

    def _resolve(self, arg: str) -> Optional[Path]:
        if arg:
            files = self.nav._workspace_files()
            if arg.isdigit() and 1 <= int(arg) <= len(files):
                return files[int(arg) - 1]
            idx = self.nav._alpha_to_index(arg)
            if not arg.isdigit() and 1 <= idx <= len(files):
                return files[idx - 1]
            self._err(f"E484: No file [{arg}] in the workspace")
            return None
        node = self.app.query_one("#ast-tree").cursor_node
        data = node.data if node is not None else None
        if isinstance(data, dict) and data.get("type") == "file":
            return Path(data["path"])
        return self.nav.workspace_selected

    def delete(self, arg: str = "") -> bool:
        path = self._resolve(arg.strip())
        if path is None:
            return self._err("E471: Highlight a file first (or :rm <number>)") if not arg else False
        if not path.is_file():
            return self._err("Only files can be deleted (folders are never removed).")
        if not self._inside_root(path):
            return self._err("E212: Refusing to delete outside the workspace")
        rel = path.relative_to(self.nav._get_base_dir())
        active = "  (currently open)" if path.resolve() == Path(self.app.filepath).resolve() else ""
        self.app.push_screen(
            ConfirmScreen(f"Delete {rel}?{active}\nThis cannot be undone.", "Delete"),
            lambda ok: self._finish(path, bool(ok)),
        )
        return True

    def _finish(self, path: Path, ok: bool) -> None:
        if not ok:
            self.app.log_status("[#ffb86c]Delete cancelled.[/#ffb86c]")
            return
        was_active = path.resolve() == Path(self.app.filepath).resolve()
        try:
            path.unlink()
        except OSError as e:
            self._err(f"E212: Can't delete: {e}")
            return
        self.app.history_strategy._trees.pop(path.resolve(), None)
        if self.nav.workspace_selected and self.nav.workspace_selected.resolve() == path.resolve():
            self.nav.workspace_selected = None
        self.app.log_status(f"[bold #ff5f5f]Deleted[/bold #ff5f5f] {escape(path.name)}")
        if was_active:
            others = [p for p in self.nav._workspace_files() if p != path]
            if others:
                self.nav.select_block({"type": "file", "path": others[0]})
            else:
                self.app.log_status("[#ffb86c]No files left in the workspace; the buffer still shows the deleted file.[/#ffb86c]")
        self.nav.populate_tree()
