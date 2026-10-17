# editor/ui/strategies/mutation.py
from pathlib import Path

from rich.markup import escape
from textual.widgets import Select

try:
    from ..components.inputs import VimTextArea
except (ImportError, ValueError):
    from editor.ui.components.inputs import VimTextArea


class DefaultMutationStrategy:
    def __init__(self, app):
        self.app = app

    # --- queueing -------------------------------------------------------

    def queue(self, op_type: str = None, target_id: int = None, content: str = None) -> bool:
        """Queues the active buffer as a mutation of the selected block. Returns True if queued."""
        if self.app.selected_block_id is None:
            self.app.log_status("[bold #ff5555]Error:[/bold #ff5555] No AST block selected!")
            return False

        op_type = op_type or self.app.query_one("#op-select", Select).value
        content = content if content is not None else self.app.query_one("#content-input", VimTextArea).text
        if not content:
            self.app.log_status("[bold #ffb86c]Warning:[/bold #ffb86c] Buffer is empty.")
            return False

        target = target_id if target_id is not None else self.app.selected_block_id
        self.app.editor.queue_mutation(op_type, [target], content)
        self.app.log_status(
            f"[bold #00ffaf]Queued {op_type}:[/bold #00ffaf] Block \\[{target}] "
            f"(Buffer size: {len(self.app.editor.mutation_buffer)})"
        )
        # NOTE: the buffer is also the preview now, so it is deliberately NOT cleared here.
        return True

    # --- applying -------------------------------------------------------

    def _describe_buffer(self) -> str:
        editor = self.app.editor
        by_index = {b.index: b for b in editor.blocks}
        parts = []
        for op in editor.mutation_buffer:
            for idx in op.target_indices:
                b = by_index.get(idx)
                parts.append(f"{op.op_type}: {b.name if b else idx}")
        if len(parts) > 3:
            return ", ".join(parts[:3]) + f" (+{len(parts) - 3} more)"
        return ", ".join(parts) or "mutation"

    def apply(self) -> bool:
        """Applies queued ops, writes the file, and records a history state."""
        editor = self.app.editor
        if not editor.mutation_buffer:
            self.app.log_status("[bold #ffb86c]Buffer empty.[/bold #ffb86c] Nothing to apply.")
            return False

        nav, history = self.app.navigation_strategy, self.app.history_strategy
        history.attach()  # make sure the pre-change state is already in the tree
        label = self._describe_buffer()
        snap = nav.snapshot_selection()

        updated = editor.apply_batch()
        Path(self.app.filepath).write_text(updated)
        editor.original_code = updated

        node = history.record(label)
        nav.populate_tree()
        nav.restore_selection(snap)  # block indices shift after re-parse; re-find our block
        state = f"state \\[{node.seq}]" if node else "no net change"
        self.app.log_status(
            f"[bold #00ffaf]Written to disk[/bold #00ffaf] ({state}): {escape(label)}"
        )
        return True

    def commit(self) -> bool:
        """Enter in NORMAL mode / :w: queue the active buffer and immediately write it to disk."""
        block_id = self.app.selected_block_id
        if block_id is None:
            self.app.log_status("[bold #ff5555]Error:[/bold #ff5555] No active AST block selected.")
            return False

        area = self.app.query_one("#content-input", VimTextArea)
        op_type = self.app.query_one("#op-select", Select).value
        block = next((b for b in self.app.editor.blocks if b.index == block_id), None)
        if op_type == "replace" and block is not None and area.text == block.content:
            self.app.log_status("[#ffb86c]No changes in buffer.[/#ffb86c]")
            return False

        return self.queue(op_type=op_type, content=area.text) and self.apply()

    # --- buffer management ----------------------------------------------

    def clear(self) -> None:
        self.app.editor.mutation_buffer.clear()
        self.app.log_status("[bold #ffb86c]Mutation buffer cleared.[/bold #ffb86c]")

    def pop(self) -> None:
        if self.app.editor.mutation_buffer:
            popped = self.app.editor.mutation_buffer.pop()
            self.app.log_status(f"[bold #ffb86c]Popped mutation:[/bold #ffb86c] {escape(str(popped))}")
