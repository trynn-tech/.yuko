"""Modular Block Editor Textual Interface (`ModularEditorTUI`).

Asynchronous terminal application driven by Textual, coordinating file parsing,
single-file AST navigation, workspace directory exploration (alphabetical file codes),
an active syntax-highlighted code buffer, direct disk-commit workflows, and an
interactive UndoTree.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select

try:
    # Package execution: python -m editor.ui.app / installed entrypoint
    from ..modular_editor import ModularBlockEditor
    from .components.cmdline import CommandInput
    from .components.inputs import VimTextArea
    from .components.preview import TargetPreviewPanel
    from .components.tree import NavigableTree
    from .components.undotree import UndoTreePanel
    from .strategies.command import CommandStrategy
    from .strategies.history import HistoryStrategy
    from .strategies.mutation import DefaultMutationStrategy
    from .strategies.navigation import DefaultNavigationStrategy
    from .strategies.stage import StageStrategy
except (ImportError, ValueError):
    # Direct script / Nix-store wrapper: put the directory *containing* `editor/` on sys.path
    for _parent in Path(__file__).resolve().parents:
        if (_parent / "editor" / "modular_editor.py").exists():
            if str(_parent) not in sys.path:
                sys.path.insert(0, str(_parent))
            break
    from editor.modular_editor import ModularBlockEditor
    from editor.ui.components.cmdline import CommandInput
    from editor.ui.components.inputs import VimTextArea
    from editor.ui.components.preview import TargetPreviewPanel
    from editor.ui.components.tree import NavigableTree
    from editor.ui.components.undotree import UndoTreePanel
    from editor.ui.strategies.command import CommandStrategy
    from editor.ui.strategies.history import HistoryStrategy
    from editor.ui.strategies.mutation import DefaultMutationStrategy
    from editor.ui.strategies.navigation import DefaultNavigationStrategy
    from editor.ui.strategies.stage import StageStrategy


class ModularEditorTUI(App):
    """Modular AST Block Editor: the code preview is the active buffer; Enter writes to disk."""

    CSS = """
    Screen { layout: vertical; background: #121212; color: #e0e0e0; }
    #main-container { height: 1fr; }
    #left-pane { width: 32%; border-right: solid #333333; background: #181818; }
    #right-pane { width: 68%; padding: 0 1; background: #121212; layout: vertical; }

    /* The code preview IS the active buffer */
    #content-input { height: 1fr; border: solid #333333; background: #121212; }
    #content-input:focus { border: solid #00d7ff; }
    #cmdbar { height: 1; display: none; background: #181818; }
    #cmdbar.visible { display: block; }
    #cmd-label { width: 1; color: #00d7ff; }
    #cmd-input { border: none; height: 1; padding: 0; background: #181818; color: #e0e0e0; }

    #mutation-bar { height: 9; padding: 0 1; border-top: solid #333333; background: #181818; }
    #mutation-controls { height: 3; margin-bottom: 0; }
    #mutation-left { width: 50%; }
    #target-preview { width: 50%; height: 3; border: solid #333333; padding: 0 1; background: #222222; overflow: hidden; }
    .control-row { height: auto; }
    #jump-input { margin-bottom: 1; border: solid #333333; background: #121212; color: #00d7ff; }
    #status-log { height: 3; border-top: solid #333333; background: #121212; }

    /* UndoTree panel */
    #undotree-panel { dock: right; width: 42%; height: 1fr; border-left: solid #00d7ff; background: #151515; display: none; }
    #undotree-panel.visible { display: block; }
    #undo-title, #undo-hints { height: 1; }
    #undo-graph { height: 1fr; border: none; padding: 0; background: #151515; }
    #undo-diff { height: 45%; border: solid #333333; border-title-color: #00d7ff; background: #151515; }
    #undo-diff:focus { border: solid #00d7ff; }

    Tree { background: #181818; color: #d0d0d0; }
    Tree:focus .tree--cursor { background: #005f87; color: #ffffff; }
    """

    # NOTE: Enter is intentionally NOT a global binding. Enter means: write (buffer, NORMAL mode),
    # checkout (undotree), select (tree), run (command line). Each widget owns its own Enter.
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_tree", "Reload AST"),
        Binding("ctrl+e", "toggle_tree_mode", "Toggle Workspace View", show=True),
        Binding("colon", "open_cmdline", ":cmd", show=True),
        Binding("ctrl+u", "toggle_undotree", "UndoTree", show=True),
        Binding("u", "history_undo", "Undo", show=True),
        Binding("ctrl+r", "history_redo", "Redo", show=True),
        Binding("left_square_bracket", "history_earlier", "g- Earlier", show=False),
        Binding("right_square_bracket", "history_later", "g+ Later", show=False),
        Binding("a", "apply_mutations", "Apply Batch"),
        Binding("c", "clear_buffer", "Clear Queue"),
        Binding("x", "pop_buffer_item", "Pop Op"),
        Binding("J", "focus_jump", "Jump (Shift+J)", show=True),
        Binding("i", "focus_mutation", "Edit Content", show=True),
        Binding("I", "focus_mutation_top", "Edit @ Top", show=True),
        Binding("y", "copy_fragment", "Yank"),
        Binding("escape", "blur_inputs", "Nav Mode"),
    ]

    selected_block_id: reactive[Optional[int]] = reactive(None)
    diff_mode: reactive[bool] = reactive(False)
    undotree_visible: reactive[bool] = reactive(False)

    def __init__(self, filepath: str, initial_anchor: Optional[int] = None, start_in_workspace: bool = False):
        super().__init__()
        self.filepath = Path(filepath).resolve()
        self.workspace_root: Optional[Path] = None

        if self.filepath.is_dir():
            start_in_workspace = True
            self.workspace_root = self.filepath
            py_files = sorted(self.filepath.glob("*.py"))
            # Empty/non-Python folder: use a not-yet-existing placeholder rather than read_text() on a directory
            self.filepath = py_files[0].resolve() if py_files else (self.filepath / "untitled.py")

        self.editor = ModularBlockEditor(str(self.filepath))
        self.language = self._detect_language()
        self.initial_anchor = initial_anchor
        self.start_in_workspace = start_in_workspace
        self.internal_yank_buffer: str = ""

        self.navigation_strategy = DefaultNavigationStrategy(self)
        self.mutation_strategy = DefaultMutationStrategy(self)
        self.stage_strategy = StageStrategy(self)
        self.history_strategy = HistoryStrategy(self)
        self.command_strategy = CommandStrategy(self)
        self._cmd_return_focus = None
        self._undotree_return_focus = None

    def _detect_language(self) -> str:
        ext = self.filepath.suffix.lower()
        if ext == ".nix":
            return "nix"
        if ext in (".sh", ".bash"):
            return "bash"
        return "python"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield Label("[bold #00d7ff] Document Structure & AST [/bold #00d7ff]")
                yield Input(
                    placeholder="Jump: block # | file code a, ab | y:code yank",
                    id="jump-input",
                )
                yield NavigableTree("Document Root", id="ast-tree")

            with Vertical(id="right-pane"):
                yield Label(
                    "[bold #00d7ff] Active Buffer [/bold #00d7ff] [dim](Enter or :w = write · u = undo · :help)[/dim]",
                    id="preview-label",
                )
                yield VimTextArea(id="content-input")
                with Horizontal(id="cmdbar"):
                    yield Label(":", id="cmd-label")
                    yield CommandInput(id="cmd-input")

            yield UndoTreePanel(id="undotree-panel")

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
                        yield Button("Queue Op", id="queue-btn", variant="primary")
                yield TargetPreviewPanel(id="target-preview")
            yield RichLog(id="status-log", highlight=True, markup=True)

        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Modular Editor — {self.filepath.name}"
        self.query_one("#content-input", VimTextArea).set_language(
            self.language if self.language in ("python", "bash") else None
        )
        self.history_strategy.attach()
        if self.workspace_root is not None:
            self.navigation_strategy.fs_root_path = self.workspace_root
        if self.start_in_workspace:
            self.navigation_strategy.set_filesystem_mode(directory_mode=True)
        else:
            self.navigation_strategy.populate_tree()
        if self.editor.blocks:
            self.navigation_strategy.select_block(0)  # whole file in the active buffer

    # --- Tree / mode actions ----------------------------------------------

    def action_toggle_tree_mode(self) -> None:
        new_mode = not self.navigation_strategy.directory_mode
        self.navigation_strategy.set_filesystem_mode(directory_mode=new_mode)
        mode_str = "Workspace Directory Mode" if new_mode else "Single-File AST Mode"
        self.log_status(f"[#00d7ff]Switched Tree View to [bold]{mode_str}[/bold].[/#00d7ff]")

    # --- UndoTree -----------------------------------------------------------

    def open_undotree(self) -> None:
        if self.undotree_visible:
            self.query_one("#undotree-panel", UndoTreePanel).focus_graph()
            return
        self._undotree_return_focus = self.focused
        self.undotree_visible = True
        self.query_one("#undotree-panel", UndoTreePanel).add_class("visible")
        self.refresh_undotree_view()
        self.query_one("#undotree-panel", UndoTreePanel).focus_graph()

    def close_undotree(self) -> None:
        """Close and hand focus back to where you were (open, operate, close)."""
        if not self.undotree_visible:
            return
        self.undotree_visible = False
        self.query_one("#undotree-panel", UndoTreePanel).remove_class("visible")
        target = self._undotree_return_focus
        if target is not None and target.is_attached:
            target.focus()
        else:
            self.query_one("#ast-tree", NavigableTree).focus()

    def action_toggle_undotree(self) -> None:
        self.close_undotree() if self.undotree_visible else self.open_undotree()

    def refresh_undotree_view(self, cursor_seq: Optional[int] = None) -> None:
        """Re-renders the undotree from the active file's history (no-op while hidden)."""
        if not self.undotree_visible:
            return
        self.query_one("#undotree-panel", UndoTreePanel).show(self.history_strategy.tree, cursor_seq)

    def action_history_undo(self) -> None:
        self.history_strategy.undo()

    def action_history_redo(self) -> None:
        self.history_strategy.redo()

    def action_history_earlier(self) -> None:
        self.history_strategy.earlier()

    def action_history_later(self) -> None:
        self.history_strategy.later()

    # --- Focus / editing ------------------------------------------------------

    def action_open_cmdline(self) -> None:
        self._cmd_return_focus = self.focused
        self.query_one("#cmdbar").add_class("visible")
        cmd = self.query_one("#cmd-input", CommandInput)
        cmd.reset()
        cmd.focus()

    def close_cmdline(self) -> None:
        self.query_one("#cmdbar").remove_class("visible")
        target = self._cmd_return_focus
        if target is not None and target.is_attached:
            target.focus()
        else:
            self.query_one("#ast-tree", NavigableTree).focus()

    def action_focus_jump(self) -> None:
        self.query_one("#jump-input", Input).focus()

    def action_focus_mutation(self) -> None:
        self.query_one("#content-input", VimTextArea).focus()

    def action_focus_mutation_top(self) -> None:
        area = self.query_one("#content-input", VimTextArea)
        area.focus()
        area.move_cursor((0, 0))

    def action_submit_mutation(self) -> None:
        """Queue the buffer without writing (also :queue and the Queue Op button)."""
        self.mutation_strategy.queue()

    def action_commit_and_write_disk(self) -> None:
        """Enter (NORMAL mode in the buffer): queue the buffer and write it to disk."""
        self.mutation_strategy.commit()

    def action_apply_mutations(self) -> None:
        self.mutation_strategy.apply()

    def action_clear_buffer(self) -> None:
        self.mutation_strategy.clear()

    def action_pop_buffer_item(self) -> None:
        self.mutation_strategy.pop()

    def action_refresh_tree(self) -> None:
        self.editor.parse_document()
        self.navigation_strategy.populate_tree()
        self.log_status("[#00d7ff]AST Tree re-parsed and refreshed.[/#00d7ff]")

    def action_blur_inputs(self) -> None:
        self.query_one("#ast-tree", NavigableTree).focus()

    def action_copy_fragment(self) -> None:
        nav = self.navigation_strategy
        node = self.query_one("#ast-tree", NavigableTree).cursor_node
        if node is not None and isinstance(node.data, dict):
            nav.yank_target(node)
        elif self.selected_block_id is not None:
            nav.yank_target(self.selected_block_id)

    # --- Events ---------------------------------------------------------------

    def on_tree_node_selected(self, event: NavigableTree.NodeSelected) -> None:
        if event.node.data is not None:
            self.navigation_strategy.select_block(event.node.data)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "cmd-input":
            event.stop()
            self.close_cmdline()  # restore focus first so :q / :wq can then leave the buffer
            self.command_strategy.execute(event.value)
            return
        if event.input.id != "jump-input":
            return
        value = event.value.strip()
        if not value:
            return
        nav = self.navigation_strategy
        if value.lower().startswith("y:"):
            if nav.yank_target(value[2:].strip()):
                event.input.value = ""
            return
        if nav.jump_to_block(value):
            event.input.value = ""
            self.query_one("#ast-tree", NavigableTree).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "queue-btn":
            self.action_submit_mutation()

    def log_status(self, msg: str) -> None:
        self.query_one("#status-log", RichLog).write(msg)


def main():
    parser = argparse.ArgumentParser(description="Modular AST Block Editor TUI")
    parser.add_argument("path", type=str, nargs="?", default=".", help="Path to target code file or workspace directory")
    parser.add_argument("-w", "--workspace", action="store_true", help="Start directly in Workspace Directory Mode")
    args = parser.parse_args()

    target_path = Path(args.path).resolve()
    start_workspace = args.workspace or target_path.is_dir()
    ModularEditorTUI(str(target_path), start_in_workspace=start_workspace).run()


if __name__ == "__main__":
    main()
