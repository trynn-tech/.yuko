"""CommandInput: the `:` ex-line shown under the active buffer.

Esc / Backspace-on-empty cancels, Up/Down walks history, Tab completes command names.
Enter is NOT handled here: Input.Submitted bubbles to the app, which runs the command.
"""

from textual.binding import Binding
from textual.widgets import Input


class CommandInput(Input):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("backspace", "backspace_or_cancel", "Backspace", show=False),
        Binding("up", "history_prev", "Prev", show=False),
        Binding("down", "history_next", "Next", show=False),
        Binding("tab", "complete", "Complete", show=False),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._hist_idx: int = -1  # -1 = fresh line

    def reset(self) -> None:
        self.value = ""
        self._hist_idx = -1

    def _host(self):
        """The enclosing modal screen if it owns a command bar, else the app."""
        return self.screen if hasattr(self.screen, "close_cmdline") else self.app

    def action_cancel(self) -> None:
        self._host().close_cmdline()

    def action_backspace_or_cancel(self) -> None:
        if self.value:
            self.action_delete_left()
        else:
            self.action_cancel()  # vim: backspace on an empty ':' line leaves it

    def _history(self):
        return self._host().command_strategy.history

    def _set(self, text: str) -> None:
        self.value = text
        self.cursor_position = len(text)

    def action_history_prev(self) -> None:
        hist = self._history()
        if hist and self._hist_idx < len(hist) - 1:
            self._hist_idx += 1
            self._set(hist[-1 - self._hist_idx])

    def action_history_next(self) -> None:
        hist = self._history()
        if self._hist_idx > 0:
            self._hist_idx -= 1
            self._set(hist[-1 - self._hist_idx])
        else:
            self._hist_idx = -1
            self._set("")

    def action_complete(self) -> None:
        completed = self._host().command_strategy.complete(self.value)
        if completed is not None:
            self._set(completed)
