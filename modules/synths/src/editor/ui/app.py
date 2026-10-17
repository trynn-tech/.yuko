# editor/ui/app.py
"""Modular Block Editor Textual Interface (`ModularEditorTUI`).

Provides an asynchronous terminal application interface driven by Textual,
coordinating file parsing, structural document navigation, target AST block previews,
and batch code mutation workflows.
"""

import ctypes
import subprocess
import sys
from pathlib import Path
from typing import Optional

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Tree

try:
    from ..modular_editor import ModularBlockEditor
    from .components.inputs import VimTextArea
    from .components.preview import BlockPreview, TargetPreviewPanel
    from .components.tree import NavigableTree
    from .strategies.mutation import DefaultMutationStrategy
    from .strategies.navigation import DefaultNavigationStrategy
    from .strategies.stage import StageStrategy
except (ImportError, ValueError):
    from editor.modular_editor import ModularBlockEditor
    from editor.ui.components.inputs import VimTextArea
    from editor.ui.components.preview import BlockPreview, TargetPreviewPanel
    from editor.ui.components.tree import NavigableTree
    from editor.ui.strategies.mutation import DefaultMutationStrategy
    from editor.ui.strategies.navigation import DefaultNavigationStrategy
    from editor.ui.strategies.stage import StageStrategy


class ModularEditorTUI(App):
    """Main Textual application context for the Modular AST Block Editor.

    Manages layout execution, keyboard shortcut bindings, reactive status state,
    and delegation to navigation/mutation strategies.
    """

    CSS = """
    Screen { layout: vertical; background: #121212; color: #e0e0e0; }
    #main-container { height: 1fr; }
    #left-pane { width: 35%; border-right: solid #333333; background: #181818; }
    #right-pane { width: 65%; padding: 0 1; background: #121212; }
    #preview-container { height: 1fr; border: solid #333333; background: #121212; overflow: auto auto; }
    #mutation-bar { height: 16; padding: 0 1; border-top: solid #333333; background: #181818; }
    #mutation-controls { height: 4; margin-bottom: 0; }
    #mutation-left { width: 50%; }
    #target-preview { width: 50%; height: 4; border: solid #333333; padding: 0 1; background: #222222; overflow: hidden; }
    .control-row { height: auto; }
    #jump-input { margin-bottom: 1; border: solid #333333; background: #121212; color: #00d7ff; }
    #content-input { height: 4; margin-top: 1; margin-bottom: 1; border: solid #333333; background: #121212; }
    #status-log { height: 3; border-top: solid #333333; background: #121212; }
    Tree { background: #181818; color: #d0d0d0; }
    Tree:focus .tree--cursor { background: #005f87; color: #ffffff; }
    """

    # Global keyboard shortcuts mapped to TUI actions
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_tree", "Reload AST"),
        Binding("ctrl+e", "toggle_tree_mode", "Toggle Workspace View", show=True),
        Binding("a", "apply_mutations", "Apply Batch"),
        Binding("c", "clear_buffer", "Clear Buffer"),
        Binding("x", "pop_buffer_item", "Pop Op"),
        Binding("j", "focus_jump", "Jump to Index", show=True),
        Binding("i", "focus_mutation", "Edit Content (i)", show=True),
        Binding("I", "focus_mutation_top", "Edit Content Top (Shift+I)", show=True),
        Binding("ctrl+s", "submit_mutation", "Queue Mutation", show=True),
        Binding("y", "copy_fragment", "Yank Fragment"),
        Binding("escape", "blur_inputs", "Nav Mode"),
    ]

    # Reactive state properties dynamically trigger re-renders on change
    selected_block_id: reactive[Optional[int]] = reactive(None)
    diff_mode: reactive[bool] = reactive(False)

    def __init__(self, filepath: str, initial_anchor: Optional[int] = None):
        """Initializes application state, underlying document parser, and strategies.

        Args:
            filepath: Path string pointing to the target code file.
            initial_anchor: Optional block ID to focus upon mounting.
        """
        super().__init__()
        self.filepath = Path(filepath).resolve()
        self.editor = ModularBlockEditor(str(self.filepath))
        self.language = self._detect_language()
        self.initial_anchor = initial_anchor

        # Behavioral design pattern delegates
        self.navigation_strategy = DefaultNavigationStrategy(self)
        self.mutation_strategy = DefaultMutationStrategy(self)
        self.stage_strategy = StageStrategy(self)

    def _detect_language(self) -> str:
        """Infers syntax highlighting domain based on target file extension."""
        ext = self.filepath.suffix.lower()
        if ext == ".nix":
            return "nix"
        elif ext in [".sh", ".bash"]:
            return "bash"
        return "python"

    def compose(self) -> ComposeResult:
        """Yields child UI components to construct the application layout hierarchy."""
        yield Header(show_clock=True)

        # Upper workspace pane: split tree navigator and code block viewer
        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield Label(
                    "[bold #00d7ff] Document Structure & AST [/bold #00d7ff]"
                )
                yield Input(
                    placeholder="Jump to block index (e.g. 0, 1) + Enter...",
                    id="jump-input",
                )
                yield NavigableTree("Document Root", id="ast-tree")

            with Vertical(id="right-pane"):
                yield Label(
                    "[bold #00d7ff] Block Preview Pane [/bold #00d7ff]",
                    id="preview-label",
                )
                with Container(id="preview-container"):
                    yield BlockPreview(id="preview-pane")

        # Lower control bar: mutation type selection, input buffer, target details, and status log
        with Vertical(id="mutation-bar"):
            yield Label("[bold #00d7ff] Mutation Engine [/bold #00d7ff]")
            with Horizontal(id="mutation-controls"):
                with Vertical(id="mutation-left"):
                    with Horizontal(classes="control-row"):
                        yield Select(
                            options=[
                                ("Replace Target", "replace"),
                                ("Insert Before", "insert_before"),
                                ("Insert After", "insert_after"),
                                ("Smart Replace", "smart_replace"),
                            ],
                            value="replace",
                            id="op-select",
                        )
                        yield Button(
                            "Queue Op", id="queue-btn", variant="primary"
                        )
                yield TargetPreviewPanel(id="target-preview")
            yield VimTextArea(id="content-input")
            yield RichLog(id="status-log", highlight=True, markup=True)

        yield Footer()

    def on_mount(self) -> None:
        """Lifecycle hook fired after application layout finishes rendering."""
        self.title = f"Modular Editor — {self.filepath.name}"
        self.navigation_strategy.populate_tree()

    def on_key(self, event: events.Key) -> None:
        jump_input = self.query_one("#jump-input", Input)
        if self.focused and isinstance(self.focused, (Select, NavigableTree)):
            if event.character and event.character.isdigit():
                jump_input.focus()
                event.stop()

    def action_toggle_tree_mode(self) -> None:
        """Toggles between single-file AST view and full workspace directory mode."""
        current_mode = getattr(self.navigation_strategy, "directory_mode", False)
        new_mode = not current_mode
        self.navigation_strategy.set_filesystem_mode(directory_mode=new_mode)
        mode_str = "Workspace Directory Mode" if new_mode else "Single-File AST Mode"
        self.log_status(
            f"[#00d7ff]Switched Tree View to [bold]{mode_str}[/bold].[/#00d7ff]"
        )

    def action_focus_jump(self) -> None:
        """Focuses the block jump input widget."""
        self.query_one("#jump-input", Input).focus()

    def action_focus_mutation(self) -> None:
        """Focuses the Vim mutation code input editor."""
        self.query_one("#content-input", VimTextArea).focus()

    def action_focus_mutation_top(self) -> None:
        """Focuses the mutation input editor and places the cursor at line 0, column 0 (Shift+I)."""
        input_area = self.query_one("#content-input", VimTextArea)
        input_area.focus()
        if hasattr(input_area, "cursor_location"):
            input_area.cursor_location = (0, 0)

    def action_submit_mutation(self) -> None:
        """Queues the currently configured mutation payload into the staging buffer."""
        self.mutation_strategy.queue()

    def action_apply_mutations(self) -> None:
        """Applies all staged mutations to the AST and flushes back to disk."""
        self.mutation_strategy.apply()

    def action_clear_buffer(self) -> None:
        """Clears all unapplied mutations from the buffer."""
        self.mutation_strategy.clear()

    def action_pop_buffer_item(self) -> None:
        """Removes the most recently queued mutation from the buffer."""
        self.mutation_strategy.pop()

    def action_refresh_tree(self) -> None:
        """Re-runs document parsing and rebuilds the AST tree view UI."""
        self.editor.parse_document()
        self.navigation_strategy.populate_tree()
        self.log_status("[#00d7ff]AST Tree re-parsed and refreshed.[/#00d7ff]")

    def action_blur_inputs(self) -> None:
        """Returns focus to the primary AST navigation tree (Nav Mode)."""
        self.query_one("#ast-tree", NavigableTree).focus()

    def action_copy_fragment(self) -> None:
        if self.selected_block_id is None:
            return
        block = next(
            (b for b in self.editor.blocks if b.index == self.selected_block_id),
            None,
        )
        if not block:
            return
        self.internal_yank_buffer = block.content
        copied = False
        try:
            # Try using xclip for X11 environments
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            process.communicate(input=block.content.encode("utf-8"))
            if process.returncode == 0:
                copied = True
        except FileNotFoundError:
            pass
        if copied:
            self.log_status(
                f"[bold #00ffaf]Yanked Block [{block.index}] to Clipboard & Internal Buffer![/bold #00ffaf]"
            )
        else:
            self.log_status(
                f"[#00ffaf]Yanked Block [{block.index}] to Internal Buffer.[/#00ffaf]"
            )

    def on_tree_node_selected(self, event: NavigableTree.NodeSelected) -> None:
        """Handles selection events triggered by tree node navigation (supports AST blocks & directory paths)."""
        if event.node.data is not None:
            self.navigation_strategy.select_block(event.node.data)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Processes submitted input events, focusing target AST nodes by ID."""
        if event.input.id == "jump-input":
            value = event.value.strip()
            if value.isdigit():
                tree = self.query_one("#ast-tree", NavigableTree)
                found = tree.jump_to_block_id(int(value))
                if found:
                    event.input.value = ""
                else:
                    self.log_status(
                        f"[bold #ff5555]Block ID {value} not found.[/bold #ff5555]"
                    )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Routes button click interactions."""
        if event.button.id == "queue-btn":
            self.action_submit_mutation()

    def log_status(self, msg: str) -> None:
        """Appends formatted status messages to the bottom RichLog pane."""
        self.query_one("#status-log", RichLog).write(msg)


def main():
    """CLI entry point for running the synth-tui application context."""
    if len(sys.argv) < 2:
        print("Usage: synth-tui <path-to-file>")
        sys.exit(1)
    app = ModularEditorTUI(sys.argv[1])
    app.run()


if __name__ == "__main__":
    main()
