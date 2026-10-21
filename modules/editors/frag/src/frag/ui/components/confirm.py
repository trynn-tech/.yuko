"""ConfirmScreen: small modal yes/no. Default focus is on "No"; `y` confirms, `n` / Esc cancels."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmScreen { align: center middle; background: #00000099; }
    #confirm-box { width: 64; height: auto; padding: 1 2; border: thick #ff5555; background: #181818; }
    #confirm-msg { margin-bottom: 1; }
    #confirm-hint { color: #888888; margin-bottom: 1; }
    #confirm-buttons { height: 3; align-horizontal: right; }
    #confirm-buttons Button { margin-left: 2; }
    """

    BINDINGS = [
        Binding("y", "answer(True)", "Yes", show=False),
        Binding("n", "answer(False)", "No", show=False),
        Binding("escape", "answer(False)", "Cancel", show=False),
    ]

    def __init__(self, message: str, yes_label: str = "Delete") -> None:
        super().__init__()
        self._message = message
        self._yes = yes_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self._message, id="confirm-msg")
            yield Label("y = confirm    n / Esc = cancel", id="confirm-hint")
            with Horizontal(id="confirm-buttons"):
                yield Button(self._yes, id="confirm-yes", variant="error")
                yield Button("Cancel", id="confirm-no", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#confirm-no", Button).focus()  # a stray Enter never deletes anything

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm-yes")

    def action_answer(self, value: bool) -> None:
        self.dismiss(value)
