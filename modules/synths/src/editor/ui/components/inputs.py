"""VimTextArea component with full multi-key modal sequence handling (dd, dG, gg, G),

motion bindings, system clipboard integration, and submission handling.
"""

import subprocess
from typing import Optional
from textual import events
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import TextArea


class VimTextArea(TextArea):
    """Custom TextArea supporting modal Vim keybindings, multi-key action sequences,

    system clipboard pasting, and seamless input submission/focus surrender.
    """

    vim_mode_enabled: reactive[bool] = reactive(True)
    mode: reactive[str] = reactive("NORMAL")

    BINDINGS = [
        # Mode triggers & submission
        Binding("escape", "handle_escape", "Exit/Normal Mode", show=False),
        Binding("i", "enter_insert_mode", "Insert Mode", show=False),
        Binding("a", "append_mode", "Append Mode", show=False),
        Binding("o", "open_line_below", "Open Line Below", show=False),
        
        # Single-character motions
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
        Binding("u", "undo", "Undo", show=False),
        Binding("ctrl+r", "redo", "Redo", show=False),
        
        # Submission shortcuts from NORMAL mode
        Binding("ctrl+s", "submit_parent_mutation", "Queue Mutation", show=False),
    ]

    def __init__(
        self,
        text: str = "",
        vim_mode: bool = True,
        *args,
        **kwargs,
    ):
        # 1. Initialize instance attributes FIRST before super/reactive triggers
        self._pending_key: Optional[str] = None

        super().__init__(text, *args, **kwargs)

        # 2. Setting reactive properties now safely triggers watch_* methods
        self.vim_mode_enabled = vim_mode
        if self.vim_mode_enabled:
            self.mode = "NORMAL"
            self.read_only = True

    def watch_mode(self, new_mode: str) -> None:
        """Updates border title and read-only status based on modal state."""
        if not self.vim_mode_enabled:
            self.border_title = "EDIT"
            return

        color = "#00d7ff" if new_mode == "NORMAL" else "#00ffaf"
        pending_str = f" [{self._pending_key}]" if self._pending_key else ""
        self.border_title = f"[{color} bold]-- {new_mode}{pending_str} --[/{color} bold]"

    def watch_vim_mode_enabled(self, enabled: bool) -> None:
        """Toggles Vim mode dynamically at runtime."""
        if not enabled:
            self.read_only = False
            self.border_title = "EDIT"
        else:
            self.mode = "NORMAL"
            self.read_only = True

    def on_focus(self) -> None:
        """Enforces NORMAL mode when widget gains focus in Vim mode."""
        if self.vim_mode_enabled:
            self.mode = "NORMAL"
            self.read_only = True
            self._pending_key = None

    # --- Mode & Navigation Actions ---

    def action_handle_escape(self) -> None:
        """Clears pending operators, returns to NORMAL mode, or surrenders focus to AST tree."""
        self._pending_key = None

        if not self.vim_mode_enabled:
            self.action_blur_self()
            return

        if self.mode == "INSERT":
            self.mode = "NORMAL"
            self.read_only = True
        else:
            # When already in NORMAL mode, Esc surrenders focus to navigation controls
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
        """Moves cursor to the bottom of the document (`G`)."""
        if self.vim_mode_enabled and self.mode == "NORMAL":
            self.move_cursor((self.line_count - 1, 0))

    def action_submit_parent_mutation(self) -> None:
        """Routes mutation submission directly to app strategy."""
        if hasattr(self.app, "action_submit_mutation"):
            self.app.action_submit_mutation()
            self.action_handle_escape()

    # --- Deletion Routines ---

    def action_delete_line(self) -> None:
        """Deletes the current line (`dd`)."""
        was_read_only = self.read_only
        self.read_only = False
        
        row, _ = self.cursor_location
        lines = self.text.splitlines()
        
        if lines:
            if row < len(lines):
                del lines[row]
            self.load_text("\n".join(lines))
            # Keep cursor bound within document height
            new_row = min(row, max(0, len(lines) - 1))
            self.move_cursor((new_row, 0))
            
        self.read_only = was_read_only

    def action_delete_to_end(self) -> None:
        """Deletes from current line to end of file (`dG`)."""
        was_read_only = self.read_only
        self.read_only = False
        
        row, _ = self.cursor_location
        lines = self.text.splitlines()
        
        if lines:
            lines = lines[:row]
            self.load_text("\n".join(lines))
            new_row = max(0, len(lines) - 1)
            self.move_cursor((new_row, 0))
            
        self.read_only = was_read_only

    def action_delete_char(self) -> None:
        if self.vim_mode_enabled and self.mode == "NORMAL":
            self.read_only = False
            self.action_delete_right()
            self.read_only = True

    # --- Multi-Key Event Interceptor ---

    def on_key(self, event: events.Key) -> None:
        """Intercepts key events to process multi-character Vim sequences (dd, dG, gg)."""
        if not self.vim_mode_enabled or self.mode != "NORMAL":
            return

        # Explicitly handle Escape in NORMAL mode to surrender focus cleanly
        if event.key == "escape":
            self.action_blur_self()
            event.stop()
            event.prevent_default()
            return

        char = event.character

        # Handle pending operator combinations
        if self._pending_key == "d":
            if char == "d":
                self.action_delete_line()
                self._pending_key = None
                event.stop()
                event.prevent_default()
                return
            elif char == "G":
                self.action_delete_to_end()
                self._pending_key = None
                event.stop()
                event.prevent_default()
                return
            else:
                self._pending_key = None

        elif self._pending_key == "g":
            if char == "g":
                self.move_cursor((0, 0))
                self._pending_key = None
                event.stop()
                event.prevent_default()
                return
            else:
                self._pending_key = None

        # Capture sequence prefix keys
        if char in ("d", "g"):
            self._pending_key = char
            self.watch_mode(self.mode)
            event.stop()
            event.prevent_default()
            return

        # Suppress standard text input in NORMAL mode for unhandled keys
        if char and char not in (
            "h", "j", "k", "l", "w", "b", "0", "$", "x", "p", "i", "a", "o", "u", "G"
        ):
            event.stop()
            event.prevent_default()

    def action_paste_clipboard(self) -> None:
        """Pastes content from internal yank buffer or system clipboard utilities."""
        pasted_text = ""

        if hasattr(self.app, "internal_yank_buffer") and self.app.internal_yank_buffer:
            pasted_text = self.app.internal_yank_buffer
        else:
            for cmd in [
                ["wl-paste", "--no-newline"],
                ["xclip", "-selection", "clipboard", "-o"],
                ["copyq", "clipboard"],
                ["xsel", "--clipboard", "--output"],
            ]:
                try:
                    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                    pasted_text = out.decode("utf-8")
                    if pasted_text:
                        break
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue

        if pasted_text:
            was_read_only = self.read_only
            self.read_only = False
            self.insert(pasted_text)
            self.read_only = was_read_only

            if hasattr(self.app, "log_status"):
                self.app.log_status(
                    "[bold #00ffaf]Pasted content into editor buffer![/bold #00ffaf]"
                )
        elif not self.vim_mode_enabled or self.mode == "INSERT":
            self.insert("p")

    def action_blur_self(self) -> None:
        """Surrenders focus back to parent UI navigation tree."""
        if hasattr(self.app, "action_blur_inputs"):
            self.app.action_blur_inputs()
