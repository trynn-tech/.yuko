# modules/synths/src/editor/tui_editor.py
import sys
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import (
    Header,
    Footer,
    Tree,
    Static,
    Button,
    Input,
    Select,
    Label,
    RichLog,
)
from textual.widgets.tree import TreeNode
from textual.reactive import reactive
from textual.binding import Binding

from rich.syntax import Syntax
from modular_editor import ModularBlockEditor, CodeBlock


class BlockPreview(Static):
    """Widget to render syntax-highlighted code for selected AST blocks or stages."""

    def update_code(self, code: str, language: str = "python", line_start: int = 1):
        syntax = Syntax(
            code,
            lexer=language,
            theme="monokai",
            line_numbers=True,
            start_line=line_start,
            word_wrap=False,
        )
        self.update(syntax)


class ModularEditorTUI(App):
    """Textual TUI for Modular AST and Stage Block Editor."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
    }

    #left-pane {
        width: 35%;
        border-right: heavy $accent;
    }

    #right-pane {
        width: 65%;
        padding: 1 1;
    }

    #preview-container {
        height: 1fr;
        border: solid $accent;
        overflow: auto auto;
    }

    #mutation-bar {
        height: auto;
        padding: 1;
        border-top: heavy $accent;
        background: $surface;
    }

    .horizontal-controls {
        height: auto;
        margin-bottom: 1;
    }

    .horizontal-controls Select {
        width: 25%;
        margin-right: 1;
    }

    .horizontal-controls Input {
        width: 55%;
        margin-right: 1;
    }

    .horizontal-controls Button {
        width: 18%;
    }

    #status-log {
        height: 3;
        border-top: solid $accent;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_tree", "Reload AST"),
        Binding("a", "apply_mutations", "Apply Batch"),
        Binding("c", "clear_buffer", "Clear Buffer"),
    ]

    selected_block_id: reactive[Optional[int]] = reactive(None)

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = Path(filepath)
        self.editor = ModularBlockEditor(str(self.filepath))
        self.language = self._detect_language()

    def _detect_language(self) -> str:
        ext = self.filepath.suffix.lower()
        if ext == ".nix":
            return "nix"
        elif ext in [".sh", ".bash"]:
            return "bash"
        return "python"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield Label("[bold cyan] Document Structure & AST [/bold cyan]")
                yield Tree("File Root", id="ast-tree")

            with Vertical(id="right-pane"):
                yield Label("[bold cyan] Block Preview Pane [/bold cyan]")
                with Container(id="preview-container"):
                    yield BlockPreview(id="preview-pane")

        with Vertical(id="mutation-bar"):
            yield Label("[bold yellow] Mutation Engine [/bold yellow]")
            with Horizontal(classes="horizontal-controls"):
                yield Select(
                    options=[
                        ("Replace", "replace"),
                        ("Insert Before", "insert_before"),
                        ("Insert After", "insert_after"),
                        ("Smart Replace", "smart_replace"),
                    ],
                    value="replace",
                    id="op-select",
                )
                yield Input(
                    placeholder="Enter inline content or block modification code...",
                    id="content-input",
                )
                yield Button("Queue Op", id="queue-btn", variant="primary")
            yield RichLog(id="status-log", highlight=True, markup=True)

        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Modular Editor — {self.filepath.name}"
        self.populate_tree()

    def populate_tree(self) -> None:
        tree = self.query_one("#ast-tree", Tree)
        tree.clear()
        tree.root.label = f"📄 {self.filepath.name}"
        tree.root.expand()

        summary = self.editor.get_summary()

        # Stage buckets
        stage_nodes = {}
        for stage_num in sorted(self.editor.stages.keys()):
            s_node = tree.root.add(f"🧱 Stage {stage_num}", expand=True)
            stage_nodes[stage_num] = s_node

        # Populate AST Items
        for item in summary["selection_array"]:
            idx = item["index"]
            b_type = item["type"]
            name = item["name"]
            lines = item["lines"]
            stage_id = item["stage"]

            icon = "⚙️" if b_type == "function" else ("📦" if b_type == "class" else "📌")
            label = f"{icon} [{idx}] {b_type}: {name} ({lines})"

            # Direct to parent Stage node if bound, otherwise root
            parent = stage_nodes.get(stage_id, tree.root)
            parent.add_leaf(label, data=idx)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        block_idx = event.node.data
        if block_idx is not None:
            self.selected_block_id = block_idx
            block = next((b for b in self.editor.blocks if b.index == block_idx), None)
            if block:
                preview = self.query_one("#preview-pane", BlockPreview)
                preview.update_code(
                    block.content,
                    language=self.language,
                    line_start=block.start_line,
                )
                self.log_status(
                    f"[green]Selected Block [{block.index}]:[/green] {block.name} (Lines {block.start_line}-{block.end_line})"
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "queue-btn":
            self.action_queue_mutation()

    def action_queue_mutation(self) -> None:
        if self.selected_block_id is None:
            self.log_status("[red]Error:[/red] No AST block selected from the tree!")
            return

        op_type = self.query_one("#op-select", Select).value
        content = self.query_one("#content-input", Input).value

        if not content:
            self.log_status("[yellow]Warning:[/yellow] Content field is empty.")
            return

        # Queue mutation in underlying editor buffer
        self.editor.queue_mutation(op_type, [self.selected_block_id], content)
        self.log_status(
            f"[bold green]Queued {op_type}:[/bold green] Block [{self.selected_block_id}] (Buffer size: {len(self.editor.mutation_buffer)})"
        )
        self.query_one("#content-input", Input).value = ""

    def action_apply_mutations(self) -> None:
        if not self.editor.mutation_buffer:
            self.log_status("[yellow]Buffer empty.[/yellow] Nothing to apply.")
            return

        # Execute queued mutations and save file
        updated_code = self.editor.apply_batch()
        self.filepath.write_text(updated_code)

        self.log_status(f"[bold green]Success![/bold green] Applied changes to disk: {self.filepath}")
        self.populate_tree()

    def action_clear_buffer(self) -> None:
        self.editor.mutation_buffer.clear()
        self.log_status("[yellow]Mutation buffer cleared.[/yellow]")

    def action_refresh_tree(self) -> None:
        self.editor.parse_document()
        self.populate_tree()
        self.log_status("[cyan]AST Tree re-parsed and refreshed.[/cyan]")

    def log_status(self, msg: str) -> None:
        log = self.query_one("#status-log", RichLog)
        log.write(msg)


def main():
    if len(sys.argv) < 2:
        print("Usage: synth-tui <path-to-file>")
        sys.exit(1)

    app = ModularEditorTUI(sys.argv[1])
    app.run()


if __name__ == "__main__":
    main()

