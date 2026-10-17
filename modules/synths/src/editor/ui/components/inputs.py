"""VimTextArea: the active code buffer (preview + editor in one).

* Shows the selected block with syntax highlighting; edit it in place.
* NORMAL mode `Enter` (only while this buffer has focus) or `:w` writes it to disk.
* `:` opens the ex command line (:w :wq :q :q! :u :earlier :e a ...).
* `u` / `Ctrl+R` are dirty-aware: with uncommitted edits they undo/redo typing in the
  buffer; otherwise they walk the file's UndoTree (and re-write the file).
* `g-` / `g+` travel the UndoTree by time, across branches.
* Multi-key sequences: dd, dG, gg, g-, g+, plus G and the usual motions.
"""

import subprocess
from typing import Optional

from textual import events
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import TextArea


class VimTextArea(TextArea):
    vim_mode_enabled: reactive[bool] = reactive(True)
    mode: reactive[str] = reactive("NORMAL")

    BINDINGS = [
        # Mode triggers & submission
        Binding("escape", "handle_escape", "Exit/Normal Mode", show=False),
        Binding("i", "enter_insert_mode", "Insert Mode", show=False),
        Binding("a", "append_mode", "Append Mode", show=False),
        Binding("o", "open_line_below", "Open Line Below", show=False),
        # Motions
        Binding("h", "cursor_left", "Move Left", show=False),
        Binding("j", "cursor_down", "Move Down", show=False),
        Binding("k", "cursor_up", "Move Up", show=False),
        Binding("l", "cursor_right", "Move Right", show=False),
        Binding("w", "cursor_word_right", "Next Word", show=False),
        Binding("b", "cursor_word_left", "Prev Word", show=False),
        Binding("0", "cursor_home", "Start of Line", show=False),
        Binding("$", "cursor_end", "End of Line", show=False),
        Binding("G", "move_bottom", "Go to Bottom", show=False),
        # Operations
        Binding("x", "delete_char", "Delete Char", show=False),
        Binding("p", "paste_clipboard", "Paste Clipboard", show=False),
        Binding("u", "vim_undo", "Undo", show=False),
        Binding("ctrl+r", "vim_redo", "Redo", show=False),
    ]

    def __init__(self, text: str = "", vim_mode: bool = True, *args, **kwargs):
        # Instance attributes FIRST: reactive watchers can fire during super().__init__
        self._pending_key: Optional[str] = None
        self._baseline: str = text

        kwargs.setdefault("show_line_numbers", True)
        kwargs.setdefault("theme", "monokai")
        super().__init__(text, *args, **kwargs)

        self.vim_mode_enabled = vim_mode
        if self.vim_mode_enabled:
            self.mode = "NORMAL"
            self.read_only = True

    # --- Active-buffer API ----------------------------------------------

    @property
    def is_dirty(self) -> bool:
        """True if the buffer differs from what was last loaded/committed."""
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

    def load_block(
        self,
        content: str,
        language: Optional[str] = None,
        name: str = "",
        start_line: int = 1,
        end_line: Optional[int] = None,
    ) -> None:
        """Loads a block as the new clean baseline of the buffer."""
        self._baseline = content
        if language is not None:
            self.set_language(language if language in ("python", "bash") else None)
        self.load_text(content)  # also clears TextArea's local edit history
        self.move_cursor((0, 0))
        span = f"L{start_line}-{end_line}" if end_line else f"L{start_line}"
        self.border_subtitle = f"{name}  {span}" if name else span
        self._pending_key = None

    # --- Reactive watchers ------------------------------------------------

    def watch_mode(self, new_mode: str) -> None:
        if not self.vim_mode_enabled:
            self.border_title = "EDIT"
            return
        color = "#00d7ff" if new_mode == "NORMAL" else "#00ffaf"
        pending = f" [{self._pending_key}]" if self._pending_key else ""
        self.border_title = f"[{color} bold]-- {new_mode}{pending} --[/{color} bold]"

    def watch_vim_mode_enabled(self, enabled: bool) -> None:
        if not enabled:
            self.read_only = False
            self.border_title = "EDIT"
        else:
            self.mode = "NORMAL"
            self.read_only = True

    def on_focus(self) -> None:
        if self.vim_mode_enabled:
            self.mode = "NORMAL"
            self.read_only = True
            self._pending_key = None

    # --- Mode & navigation actions ----------------------------------------

    def action_handle_escape(self) -> None:
        self._pending_key = None
        if not self.vim_mode_enabled:
            self.action_blur_self()
            return
        if self.mode == "INSERT":
            self.mode = "NORMAL"
            self.read_only = True
        else:
            self.action_blur_self()

    def action_enter_insert_mode(self) -> None:
        if not self.vim_mode_enabled:
            return
        self.mode = "INSERT"
        self.read_only = False
        self._pending_key = None

    def action_append_mode(self) -> None:
        if not self.vim_mode_enabled or self.mode != "NORMAL":
            return
        self.action_cursor_right()
        self.mode = "INSERT"
        self.read_only = False
        self._pending_key = None

    def action_open_line_below(self) -> None:
        if not self.vim_mode_enabled or self.mode != "NORMAL":
            return
        self.action_cursor_end()
        self.read_only = False
        self.insert("\n")
        self.mode = "INSERT"
        self._pending_key = None

    def action_move_bottom(self) -> None:
        if self.vim_mode_enabled and self.mode == "NORMAL":
            self.move_cursor((self.document.line_count - 1, 0))

    def action_commit_buffer(self) -> None:
        """Enter (NORMAL): queue the buffer and write it to disk."""
        if hasattr(self.app, "action_commit_and_write_disk"):
            self.app.action_commit_and_write_disk()

    # --- Undo / redo (dirty-aware) ----------------------------------------

    def _with_edit_rights(self, fn) -> None:
        was_read_only = self.read_only
        self.read_only = False
        try:
            fn()
        finally:
            self.read_only = was_read_only

    def action_vim_undo(self) -> None:
        if self.is_dirty:
            self._with_edit_rights(lambda: TextArea.action_undo(self))  # undo typing in the buffer
        elif hasattr(self.app, "action_history_undo"):
            self.app.action_history_undo()  # buffer is clean: walk the file's UndoTree

    def action_vim_redo(self) -> None:
        if self.is_dirty:
            self._with_edit_rights(lambda: TextArea.action_redo(self))
        elif hasattr(self.app, "action_history_redo"):
            self.app.action_history_redo()

    # --- Deletion (uses TextArea edit API so `u` can undo it) --------------

    def action_delete_line(self) -> None:
        """dd"""
        doc = self.document
        if doc.line_count == 0:
            return
        row, _ = self.cursor_location
        row = min(row, doc.line_count - 1)
        if row < doc.line_count - 1:
            start, end = (row, 0), (row + 1, 0)
        elif row > 0:
            start, end = (row - 1, len(doc.get_line(row - 1))), (row, len(doc.get_line(row)))
        else:
            start, end = (0, 0), (0, len(doc.get_line(0)))
        self._with_edit_rights(lambda: self.delete(start, end))
        self.move_cursor((min(row, self.document.line_count - 1), 0))

    def action_delete_to_end(self) -> None:
        """dG"""
        row, _ = self.cursor_location
        if row == 0:
            start = (0, 0)
        else:
            start = (row - 1, len(self.document.get_line(row - 1)))  # also eat the preceding newline
        self._with_edit_rights(lambda: self.delete(start, self.document.end))
        self.move_cursor((max(0, self.document.line_count - 1), 0))

    def action_delete_char(self) -> None:
        if self.vim_mode_enabled and self.mode == "NORMAL":
            self._with_edit_rights(self.action_delete_right)

    # --- Multi-key event interceptor ---------------------------------------

    def on_key(self, event: events.Key) -> None:
        if not self.vim_mode_enabled or self.mode != "NORMAL":
            return

        def consume() -> None:
            event.stop()
            event.prevent_default()

        if event.key == "escape":
            self.action_blur_self()
            return consume()

        # ":" opens the ex command line (NORMAL mode only; INSERT mode types a colon)
        if event.key == "colon" or event.character == ":":
            self._pending_key = None
            self.app.action_open_cmdline()
            return consume()

        # Enter == :w, but ONLY here: NORMAL mode with this buffer focused
        if event.key == "enter":
            self._pending_key = None
            self.action_commit_buffer()
            return consume()

        char = event.character

        if self._pending_key == "d":
            self._pending_key = None
            if char == "d":
                self.action_delete_line()
                return consume()
            if char == "G":
                self.action_delete_to_end()
                return consume()

        elif self._pending_key == "g":
            self._pending_key = None
            if char == "g":
                self.move_cursor((0, 0))
                return consume()
            if char in ("-", "+") and hasattr(self.app, "action_history_earlier"):
                (self.app.action_history_earlier if char == "-" else self.app.action_history_later)()
                return consume()

        if char in ("d", "g"):
            self._pending_key = char
            self.watch_mode(self.mode)
            return consume()

        # Suppress plain text input in NORMAL mode for unhandled printable keys
        if char and char not in ("h", "j", "k", "l", "w", "b", "0", "$", "x", "p", "i", "a", "o", "u", "G"):
            consume()

    # --- Clipboard -----------------------------------------------------------

    def action_paste_clipboard(self) -> None:
        pasted_text = ""
        if getattr(self.app, "internal_yank_buffer", ""):
            pasted_text = self.app.internal_yank_buffer
        else:
            for cmd in (
                ["wl-paste", "--no-newline"],
                ["xclip", "-selection", "clipboard", "-o"],
                ["copyq", "clipboard"],
                ["xsel", "--clipboard", "--output"],
            ):
                try:
                    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                    pasted_text = out.decode("utf-8")
                    if pasted_text:
                        break
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue

        if pasted_text:
            self._with_edit_rights(lambda: self.insert(pasted_text))
            if hasattr(self.app, "log_status"):
                self.app.log_status("[bold #00ffaf]Pasted content into buffer![/bold #00ffaf]")
        elif not self.vim_mode_enabled or self.mode == "INSERT":
            self.insert("p")

    def action_blur_self(self) -> None:
        if hasattr(self.app, "action_blur_inputs"):
            self.app.action_blur_inputs()
