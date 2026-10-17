"""History strategy: per-file undo trees; every checkout is written straight to disk.

Disk is the single source of truth and the undo tree is the safety net, so there is
no separate "buffer state" to manage: commit (Enter) records a state, `u` / Ctrl+R /
g- / g+ / the UndoTree panel move between states and re-write the file.
"""

import sys
from pathlib import Path
from typing import Dict, Optional

from rich.markup import escape

try:
    from ...undo_tree import UndoNode, UndoTree
    from ..base import BaseEditorStrategy
except (ImportError, ValueError):
    for _parent in Path(__file__).resolve().parents:
        if (_parent / "editor" / "modular_editor.py").exists():
            if str(_parent) not in sys.path:
                sys.path.insert(0, str(_parent))
            break
    from editor.undo_tree import UndoNode, UndoTree
    from editor.ui.base import BaseEditorStrategy


class HistoryStrategy(BaseEditorStrategy):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._trees: Dict[Path, UndoTree] = {}  # survives switching between files

    @property
    def tree(self) -> UndoTree:
        key = Path(self.app.filepath).resolve()
        if key not in self._trees:
            self._trees[key] = UndoTree(self.editor.raw_code, label="Original")
        return self._trees[key]

    # --- recording -------------------------------------------------------

    def attach(self) -> None:
        """Call whenever a file becomes active: records out-of-band edits as their own state."""
        tree = self.tree
        if tree.current.text != self.editor.raw_code:
            tree.commit(self.editor.raw_code, "external change")
            self.app.log_status("[#ffb86c]File changed outside the editor, recorded as a history state.[/#ffb86c]")
        self._refresh()

    def record(self, label: str) -> Optional[UndoNode]:
        node = self.tree.commit(self.editor.raw_code, label)
        self._refresh()
        return node

    # --- navigation ------------------------------------------------------

    def undo(self) -> bool:
        return self._checkout(self.tree.undo(), "Undo", "Already at the original state.")

    def redo(self) -> bool:
        return self._checkout(self.tree.redo(), "Redo", "Nothing to redo on this branch.")

    def earlier(self, steps: int = 1) -> bool:
        return self._checkout(self.tree.earlier(steps), "Earlier", "Already at the oldest state.")

    def later(self, steps: int = 1) -> bool:
        return self._checkout(self.tree.later(steps), "Later", "Already at the newest state.")

    def goto(self, seq: int) -> bool:
        if seq == self.tree.current.seq:
            self.app.log_status(f"[#00d7ff]Already at state [{seq}].[/#00d7ff]")
            return True
        return self._checkout(self.tree.goto(seq), "Checkout", "Unknown state.")

    # --- internals -------------------------------------------------------

    def _checkout(self, node: Optional[UndoNode], verb: str, empty_msg: str) -> bool:
        if node is None:
            self.app.log_status(f"[#ffb86c]{empty_msg}[/#ffb86c]")
            return False

        editor, nav = self.editor, self.app.navigation_strategy
        snap = nav.snapshot_selection()

        dropped = len(editor.mutation_buffer)
        editor.mutation_buffer.clear()  # queued ops target block indices that are about to change
        editor.raw_code = node.text
        editor.original_code = node.text
        editor.parse_document()
        Path(self.app.filepath).write_text(node.text)

        nav.populate_tree()
        nav.restore_selection(snap)
        self._refresh()

        extra = f" (dropped {dropped} queued op(s))" if dropped else ""
        self.app.log_status(
            f"[bold #00d7ff]{verb} → state \\[{node.seq}][/bold #00d7ff] {escape(node.label)}, written to disk{extra}"
        )
        return True

    def _refresh(self) -> None:
        refresh = getattr(self.app, "refresh_undotree_view", None)
        if refresh:
            refresh()
