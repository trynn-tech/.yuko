"""VimTextArea: the active code buffer (preview + editor in one), driven by VimEngine.

NORMAL mode speaks real Vim: counts, operators (d c y > <) with motions and text objects
(dw, d$, ciw, di", da(, 3dd, yyp ...), visual v / V, x X D C Y s S p P J ~ r o O a A i I.
See vimcore.py for the exact grammar.

Editor-specific keys (NORMAL mode, buffer focused only):
    Enter   write to disk (same as :w)        :   ex command line      /   search
    u       undo (typing, or the file's UndoTree once the buffer is clean)    Ctrl+R  redo
    g- g+   UndoTree back / forward in time   n N next / previous search hit
"""

import subprocess
from typing import Optional

from textual import events
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import TextArea
from textual.widgets.text_area import Selection

try:
    from .vimcore import VISUAL_MODES, VimEngine, _first_nonblank, _line_end, _line_start
except (ImportError, ValueError):
    from editor.ui.components.vimcore import VISUAL_MODES, VimEngine, _first_nonblank, _line_end, _line_start  # noqa: F401


class VimTextArea(TextArea):
    vim_mode_enabled: reactive[bool] = reactive(True)
    mode: reactive[str] = reactive("NORMAL")

    BINDINGS = [
        Binding("escape", "handle_escape", "Exit/Normal Mode", show=False),
    ]

    def __init__(self, text: str = "", vim_mode: bool = True, *args, **kwargs):
        # Instance attributes FIRST: reactive watchers can fire during super().__init__
        self._engine = VimEngine()
        self._baseline: str = text

        kwargs.setdefault("show_line_numbers", True)
        kwargs.setdefault("theme", "monokai")
        super().__init__(text, *args, **kwargs)

        self.vim_mode_enabled = vim_mode
        if self.vim_mode_enabled:
            self._vim_set_mode("NORMAL")

    # --- Active-buffer API ----------------------------------------------

    @property
    def is_dirty(self) -> bool:
        return self.text != self._baseline

    def set_language(self, language: Optional[str]) -> None:
        """Syntax highlighting; silently degrades to plain text if the grammar is unavailable."""
        try:
            self.language = language or None
        except Exception:
            try:
                self.language = None
            except Exception:
                pass

    def load_block(self, content: str, language: Optional[str] = None, name: str = "",
                   start_line: int = 1, end_line: Optional[int] = None) -> None:
        """Loads a block as the new clean baseline of the buffer."""
        self._baseline = content
        if language is not None:
            self.set_language(language if language in ("python", "bash") else None)
        self.load_text(content)  # also clears TextArea's local edit history
        self.move_cursor((0, 0))
        span = f"L{start_line}-{end_line}" if end_line else f"L{start_line}"
        self.border_subtitle = f"{name}  {span}" if name else span
        if self.vim_mode_enabled:
            self._vim_set_mode("NORMAL")

    def enter_insert(self) -> None:
        """Start typing immediately (used by the smart-edit window)."""
        self._vim_set_mode("INSERT")

    # --- mode plumbing ------------------------------------------------------

    def _vim_set_mode(self, mode: str) -> None:
        self._engine.mode = mode
        if mode == "NORMAL":
            self._engine._reset()
        self.read_only = mode != "INSERT"
        if self.mode != mode:
            self.mode = mode
        else:
            self.watch_mode(mode)

    def watch_mode(self, new_mode: str) -> None:
        if not self.vim_mode_enabled:
            self.border_title = "EDIT"
            return
        color = {"NORMAL": "#00d7ff", "INSERT": "#00ffaf"}.get(new_mode, "#ffb86c")
        pending = self._engine.pending
        tail = f" {pending}" if pending else ""
        self.border_title = f"[{color} bold]-- {new_mode}{tail} --[/{color} bold]"

    def watch_vim_mode_enabled(self, enabled: bool) -> None:
        if not enabled:
            self.read_only = False
            self.border_title = "EDIT"
        else:
            self._vim_set_mode("NORMAL")

    def on_focus(self) -> None:
        if self.vim_mode_enabled and self.mode == "INSERT":
            return  # keep typing if we were already inserting
        if self.vim_mode_enabled:
            self._vim_set_mode("NORMAL")

    # --- helpers ---------------------------------------------------------------

    def _host_call(self, name: str) -> None:
        """Route editor-level actions to the enclosing screen if it defines them, else the app."""
        host = self.screen if hasattr(self.screen, name) else self.app
        fn = getattr(host, name, None)
        if fn:
            fn()

    @staticmethod
    def _vim_idx(text: str, loc) -> int:
        row, col = loc
        lines = text.split("\n")
        row = max(0, min(row, len(lines) - 1))
        return sum(len(l) + 1 for l in lines[:row]) + min(col, len(lines[row]))

    @staticmethod
    def _vim_loc(text: str, idx: int):
        idx = max(0, min(idx, len(text)))
        return text.count("\n", 0, idx), idx - (text.rfind("\n", 0, idx) + 1)

    def _with_edit_rights(self, fn) -> None:
        was = self.read_only
        self.read_only = False
        try:
            fn()
        finally:
            self.read_only = was

    # --- registers / clipboard ---------------------------------------------------

    def _vim_on_yank(self, text: str, linewise: bool, to_system: bool) -> None:
        self.app.internal_yank_buffer = text  # keeps `p` and the tree's yanks in one register
        if to_system:
            try:
                self.app.navigation_strategy._copy_text(text)
            except Exception:
                pass

    def _vim_sync_register(self) -> None:
        buf = getattr(self.app, "internal_yank_buffer", "")
        if not buf and not self._engine.register[0]:
            for cmd in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"],
                        ["xsel", "--clipboard", "--output"]):
                try:
                    buf = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=1).decode("utf-8")
                    if buf:
                        break
                except Exception:
                    continue
        if buf and buf != self._engine.register[0]:
            self._engine.register = (buf, buf.endswith("\n"))  # e.g. a yanked file or block pastes as lines

    # --- feeding the engine -------------------------------------------------------

    def _vim_feed(self, key: str) -> bool:
        text = self.text
        cur = self._vim_idx(text, self.cursor_location)
        if key in ("p", "P"):
            self._vim_sync_register()
        r = self._engine.feed(key, text, cur)

        if r.edits:
            def do_edits() -> None:
                for e in sorted(r.edits, key=lambda e: e.start, reverse=True):
                    self.replace(e.text, self._vim_loc(text, e.start), self._vim_loc(text, e.end))
            self._with_edit_rights(do_edits)
        new = self.text

        if r.yank:
            self._vim_on_yank(*r.yank)
        if r.mode is not None:
            self._vim_set_mode(r.mode)  # also sets read_only for INSERT
        if r.cursor is not None:
            self.move_cursor(self._vim_loc(new, r.cursor))
        if r.selection is not None:
            self._vim_show_visual(new, *r.selection)
        if r.external:
            self._vim_external(r.external)
        self.watch_mode(self.mode)  # refresh the pending-keys indicator
        return r.handled

    def _vim_show_visual(self, text: str, anchor: int, cur: int) -> None:
        lo, hi = sorted((anchor, cur))
        if self._engine.mode == "V-LINE":
            lo, hi = _line_start(text, lo), _line_end(text, hi)
        else:
            hi = min(hi + 1, len(text))
        self.selection = Selection(start=self._vim_loc(text, lo), end=self._vim_loc(text, hi))

    def _vim_external(self, name: str) -> None:
        if name == "undo":
            self.action_vim_undo()
        else:
            self._host_call({"earlier": "action_history_earlier", "later": "action_history_later",
                             "search_next": "action_search_next", "search_prev": "action_search_prev"}[name])

    # --- key handling --------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        if not self.vim_mode_enabled:
            return

        def consume() -> None:
            event.stop()
            event.prevent_default()

        if self.mode == "INSERT":
            if event.key == "escape":
                self._vim_leave_insert()
                consume()
            return  # everything else is normal typing

        key = event.key
        if key == "ctrl+r":
            consume()
            self.action_vim_redo()
            return
        if key == "escape":
            if not self._vim_feed("<Esc>"):
                self.action_blur_self()  # nothing pending: surrender focus to the tree
            consume()
            return
        if key == "enter":
            if self.mode == "NORMAL" and not self._engine.pending:
                self._host_call("action_commit_and_write_disk")  # Enter == :w, only here
            consume()
            return

        ch = event.character if event.is_printable else None
        if ch is None:
            return  # arrows, tab, etc. keep their default behaviour
        if not self._engine.pending:
            if ch == ":":
                consume()
                self._host_call("action_open_cmdline")
                return
            if ch == "/":
                consume()
                self._host_call("action_open_search")
                return
        self._vim_feed(ch)
        consume()

    def _vim_leave_insert(self) -> None:
        self._vim_set_mode("NORMAL")
        row, col = self.cursor_location
        if col > 0:
            self.move_cursor((row, col - 1))  # Vim steps back one char when leaving INSERT

    # --- actions ----------------------------------------------------------------------

    def action_handle_escape(self) -> None:
        if self.mode == "INSERT":
            self._vim_leave_insert()
        elif not self._vim_feed("<Esc>"):
            self.action_blur_self()

    def action_vim_undo(self) -> None:
        if self.is_dirty:
            self._with_edit_rights(lambda: TextArea.action_undo(self))  # undo typing in the buffer
        else:
            self._host_call("action_history_undo")  # buffer is clean: walk the file's UndoTree

    def action_vim_redo(self) -> None:
        if self.is_dirty:
            self._with_edit_rights(lambda: TextArea.action_redo(self))
        else:
            self._host_call("action_history_redo")

    def action_blur_self(self) -> None:
        if hasattr(self.screen, "action_blur_inputs"):
            self.screen.action_blur_inputs()
        elif hasattr(self.app, "action_blur_inputs"):
            self.app.action_blur_inputs()
