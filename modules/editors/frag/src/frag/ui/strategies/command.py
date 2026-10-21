"""Ex command strategy: `:w`, `:wq`, `:q!`, `:u`, `:earlier N`, `:e a` ...

`:w` is the natural way to write: it queues the active buffer and writes it to disk
(recording an UndoTree state). Enter in NORMAL mode in the buffer does the same.
"""

import os
import re
from typing import Callable, Dict, List, Optional

from rich.markup import escape

try:
    from ..base import BaseEditorStrategy
except (ImportError, ValueError):
    import sys
    from pathlib import Path

    for _parent in Path(__file__).resolve().parents:
        if (_parent / "editor" / "modular_editor.py").exists():
            if str(_parent) not in sys.path:
                sys.path.insert(0, str(_parent))
            break
    from frag.ui.base import BaseEditorStrategy

OPS = ("replace", "insert_before", "insert_after", "smart_replace")

HELP = [
    ":w  :write            write buffer to disk (queue + apply + history state)",
    ":wq  :x               write, then leave the buffer (:x only writes if changed)",
    ":q  :q!               leave the buffer (refuses if unsaved; ! discards edits)",
    ":qa  :qa!  :wqa       quit the app",
    ":e!  :e <code|n>      reload block / open file code (a, ab) or block number",
    ":u  :undo [N]         undo, or go to state N      :red[o]  redo",
    ":earlier [N]  :later [N]   step N states through time (g- / g+)",
    ":undotree [open|close|toggle]   history panel",
    ":queue  :apply  :clear  :pop    batch queue (queue only / apply all / clear / pop last)",
    ":op <replace|insert_before|insert_after|smart_replace>   operation used by :w / :queue",
    ":find <text>  /text   select the function containing text (n / N = next / prev; /re/ = regex)",
    ":smart                paste several functions: matched to the file by name, applied as one change",
    ":new <path>  :rm [n]  workspace: create a file / delete one (asks to confirm)",
    ":<number>             go to line in the buffer",
]


class CommandStrategy(BaseEditorStrategy):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.history: List[str] = []
        self._table: Dict[str, Callable[[bool, str], bool]] = {}
        for names, fn in (
            (("w", "write"), self._write),
            (("wq",), self._write_quit),
            (("x", "xit", "exit"), self._xit),
            (("q", "quit"), self._quit),
            (("qa", "qall", "quitall"), self._quit_all),
            (("wqa", "wqall", "xa", "xall"), self._write_quit_all),
            (("e", "edit"), self._edit),
            (("u", "undo"), self._undo),
            (("red", "redo"), self._redo),
            (("earlier", "ea"), self._earlier),
            (("later", "lat"), self._later),
            (("undotree", "ut"), self._undotree),
            (("queue",), self._queue),
            (("apply",), self._apply),
            (("clear",), self._clear),
            (("pop",), self._pop),
            (("op",), self._op),
            (("find", "search", "grep"), self._find),
            (("new", "touch"), self._new),
            (("rm", "delete", "del"), self._rm),
            (("smart", "sm"), self._smart),
            (("help", "h"), self._help),
        ):
            for n in names:
                self._table[n] = fn

    # --- public ------------------------------------------------------------

    def execute(self, line: str) -> bool:
        line = line.strip().lstrip(":").strip()
        if not line:
            return False
        if not self.history or self.history[-1] != line:
            self.history.append(line)

        if line.isdigit():
            return self._goto_line(int(line))

        m = re.match(r"^([A-Za-z]+)(!?)\s*(.*)$", line)
        fn = self._table.get(m.group(1).lower()) if m else None
        if fn is None:
            return self._err(f"E492: Not an editor command: {line}")
        return bool(fn(m.group(2) == "!", m.group(3).strip()))

    def complete(self, text: str) -> Optional[str]:
        if " " in text or not text:
            return None
        names = sorted(n for n in self._table if len(n) > 1 and n.startswith(text.lower()))
        if not names:
            return None
        if len(names) == 1:
            return names[0] + " "
        prefix = os.path.commonprefix(names)
        self.app.log_status("[#00d7ff]" + escape("  ".join(names)) + "[/#00d7ff]")
        return prefix if len(prefix) > len(text) else None

    # --- helpers -----------------------------------------------------------

    @property
    def area(self):
        return self.app.query_one("#content-input")

    def _err(self, msg: str) -> bool:
        self.app.log_status(f"[bold #ff5555]{escape(msg)}[/bold #ff5555]")
        return False

    def _guard_dirty(self, bang: bool) -> bool:
        """True if it is OK to discard the buffer."""
        if self.area.is_dirty and not bang:
            self._err("E37: No write since last change (add ! to override)")
            return False
        return True

    def _reload_block(self) -> bool:
        sid = self.app.selected_block_id
        return self.app.navigation_strategy.select_block(sid if sid is not None else 0)

    def _leave_buffer(self) -> None:
        self.app.action_blur_inputs()

    # --- commands ----------------------------------------------------------

    def _write(self, bang: bool, arg: str) -> bool:
        return self.app.mutation_strategy.commit()

    def _write_quit(self, bang: bool, arg: str) -> bool:
        self.app.mutation_strategy.commit()
        if self.area.is_dirty:  # write failed: stay put
            return False
        self._leave_buffer()
        return True

    def _xit(self, bang: bool, arg: str) -> bool:
        if self.area.is_dirty:
            return self._write_quit(bang, arg)
        self._leave_buffer()
        return True

    def _quit(self, bang: bool, arg: str) -> bool:
        if not self._guard_dirty(bang):
            return False
        if bang and self.area.is_dirty:
            self._reload_block()
        self._leave_buffer()
        return True

    def _quit_all(self, bang: bool, arg: str) -> bool:
        if not self._guard_dirty(bang):
            return False
        self.app.exit()
        return True

    def _write_quit_all(self, bang: bool, arg: str) -> bool:
        self.app.mutation_strategy.commit()
        if self.area.is_dirty:
            return False
        self.app.exit()
        return True

    def _edit(self, bang: bool, arg: str) -> bool:
        if not self._guard_dirty(bang):
            return False
        if not arg:
            return self._reload_block()  # :e! discards edits
        return self.app.navigation_strategy.jump_to_block(arg)

    def _undo(self, bang: bool, arg: str) -> bool:
        if arg:
            return self.app.history_strategy.goto(int(arg)) if arg.isdigit() else self._err(f"E474: Invalid argument: {arg}")
        return self.app.history_strategy.undo()

    def _redo(self, bang: bool, arg: str) -> bool:
        return self.app.history_strategy.redo()

    def _steps(self, arg: str) -> Optional[int]:
        if not arg:
            return 1
        if arg.isdigit() and int(arg) > 0:
            return int(arg)
        self._err(f"E474: Invalid argument: {arg}")
        return None

    def _earlier(self, bang: bool, arg: str) -> bool:
        n = self._steps(arg)
        return n is not None and self.app.history_strategy.earlier(n)

    def _later(self, bang: bool, arg: str) -> bool:
        n = self._steps(arg)
        return n is not None and self.app.history_strategy.later(n)

    def _undotree(self, bang: bool, arg: str) -> bool:
        mode = (arg or "toggle").lower()
        if mode == "open":
            self.app.open_undotree()
        elif mode == "close":
            self.app.close_undotree()
        elif mode == "toggle":
            self.app.action_toggle_undotree()
        else:
            return self._err(f"E474: Invalid argument: {arg}")
        return True

    def _queue(self, bang: bool, arg: str) -> bool:
        return self.app.mutation_strategy.queue()

    def _apply(self, bang: bool, arg: str) -> bool:
        return self.app.mutation_strategy.apply()

    def _clear(self, bang: bool, arg: str) -> bool:
        self.app.mutation_strategy.clear()
        return True

    def _pop(self, bang: bool, arg: str) -> bool:
        self.app.mutation_strategy.pop()
        return True

    def _op(self, bang: bool, arg: str) -> bool:
        if arg not in OPS:
            return self._err(f"E474: :op needs one of {', '.join(OPS)}")
        self.app.mutation_op = arg
        self.app.refresh_buffer_label()
        self.app.log_status(f"[#00d7ff]Operation set to {arg}.[/#00d7ff]")
        return True

    def _find(self, bang: bool, arg: str) -> bool:
        return self.app.search_strategy.find(arg)

    def _new(self, bang: bool, arg: str) -> bool:
        return self.app.workspace_strategy.new_file(arg)

    def _rm(self, bang: bool, arg: str) -> bool:
        return self.app.workspace_strategy.delete(arg)

    def _smart(self, bang: bool, arg: str) -> bool:
        self.app.action_smart_edit()
        return True

    def _goto_line(self, n: int) -> bool:
        area = self.area
        area.move_cursor((max(0, min(n - 1, area.document.line_count - 1)), 0))
        return True

    def _help(self, bang: bool, arg: str) -> bool:
        for line in HELP:
            self.app.log_status(f"[#a0a0a0]{escape(line)}[/#a0a0a0]")
        return True
