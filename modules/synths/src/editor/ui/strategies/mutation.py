# editor/ui/strategies/mutation.py
from textual.widgets import Select
try:
    from ..components.inputs import VimTextArea
except (ImportError, ValueError):
    from editor.ui.components.inputs import VimTextArea


class DefaultMutationStrategy:
    def __init__(self, app):
        self.app = app

    def queue(self, op_type: str = None, target_id: int = None, content: str = None) -> None:
        if self.app.selected_block_id is None:
            self.app.log_status("[bold #ff5555]Error:[/bold #ff5555] No AST block selected!")
            return

        op_type = op_type or self.app.query_one("#op-select", Select).value
        content_input = self.app.query_one("#content-input", VimTextArea)
        content = content if content is not None else content_input.text

        if not content:
            self.app.log_status("[bold #ffb86c]Warning:[/bold #ffb86c] Content field is empty.")
            return

        self.app.editor.queue_mutation(op_type, [self.app.selected_block_id], content)
        buffer_len = len(getattr(self.app.editor, "mutation_buffer", []))
        self.app.log_status(
            f"[bold #00ffaf]Queued {op_type}:[/bold #00ffaf] Block [{self.app.selected_block_id}] "
            f"(Buffer size: {buffer_len})"
        )
        content_input.text = ""

    def apply(self) -> None:
        if not getattr(self.app.editor, "mutation_buffer", None):
            self.app.log_status("[bold #ffb86c]Buffer empty.[/bold #ffb86c] Nothing to apply.")
            return

        updated_code = self.app.editor.apply_batch()
        self.app.filepath.write_text(updated_code)
        self.app.log_status(
            f"[bold #00ffaf]Success![/bold #00ffaf] Applied changes to disk: {self.app.filepath}"
        )
        self.app.navigation_strategy.populate_tree()

    def clear(self) -> None:
        if hasattr(self.app.editor, "mutation_buffer"):
            self.app.editor.mutation_buffer.clear()
        self.app.log_status("[bold #ffb86c]Mutation buffer cleared.[/bold #ffb86c]")

    def pop(self) -> None:
        if hasattr(self.app.editor, "mutation_buffer") and self.app.editor.mutation_buffer:
            popped = self.app.editor.mutation_buffer.pop()
            self.app.log_status(f"[bold #ffb86c]Popped mutation:[/bold #ffb86c] {popped}")
