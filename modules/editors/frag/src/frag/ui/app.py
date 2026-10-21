"""Modular Block Editor Textual Interface (`ModularEditorTUI`).

Single-file AST navigation, workspace exploration (numbered files, persistent selection),
an active Vim-style code buffer, `:` commands, `/` search, a smart multi-function edit window,
and a jiaoshijie-style UndoTree. Disk is the source of truth; every write is an undo state.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Label, RichLog

try:
    # Package execution: python -m editor.ui.app / installed entrypoint
    from ..modular_editor import ModularBlockEditor
    from .components.cmdline import CommandInput
    from .components.inputs import VimTextArea
    from .components.smartedit import SmartEditScreen
    from .components.tree import NavigableTree
    from .components.undotree import UndoTreePanel
    from .strategies.command import CommandStrategy
    from .strategies.history import HistoryStrategy
    from .strategies.mutation import DefaultMutationStrategy
    from .strategies.navigation import DefaultNavigationStrategy
    from .strategies.search import SearchStrategy
    from .strategies.stage import StageStrategy
    from .strategies.workspace import WorkspaceStrategy
except (ImportError, ValueError):
    # Direct script / Nix-store wrapper: put the directory *containing* `frag/` on sys.path
    for _parent in Path(__file__).resolve().parents:
        if (_parent / "src/frag" / "modular_editor.py").exists():
            if str(_parent) not in sys.path:
                sys.path.insert(0, str(_parent))
            break
    from frag.modular_editor import ModularBlockEditor
    from frag.ui.components.cmdline import CommandInput
    from frag.ui.components.inputs import VimTextArea
    from frag.ui.components.smartedit import SmartEditScreen
    from frag.ui.components.tree import NavigableTree
    from frag.ui.components.undotree import UndoTreePanel
    from frag.ui.strategies.command import CommandStrategy
    from frag.ui.strategies.history import HistoryStrategy
    from frag.ui.strategies.mutation import DefaultMutationStrategy
    from frag.ui.strategies.navigation import DefaultNavigationStrategy
    from frag.ui.strategies.search import SearchStrategy
    from frag.ui.strategies.stage import StageStrategy
    from frag.ui.strategies.workspace import WorkspaceStrategy


class ModularEditorTUI(App):
    """Modular AST Block Editor: the code preview is the active buffer; Enter / :w write to disk."""

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

    #jump-input { margin-bottom: 1; border: solid #333333; background: #121212; color: #00d7ff; }
    #status-log { height: 5; border-top: solid #333333; background: #121212; padding: 0 1; }

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

    # Enter is NOT global: write (buffer, NORMAL), checkout (undotree), select (tree), run (command line).
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_tree", "Reload AST"),
        Binding("colon", "open_cmdline", ":cmd", show=True),
        Binding("slash", "open_search", "/search", show=True),
        Binding("n", "ctx_next", "Next hit / New file", show=True),
        Binding("N", "ctx_prev", "Prev hit", show=False),
        Binding("E", "smart_edit", "Smart edit", show=True),
        Binding("D", "delete_file", "Delete file", show=False),
        Binding("ctrl+e", "toggle_tree_mode", "Workspace", show=True),
        Binding("ctrl+u", "toggle_undotree", "UndoTree", show=True),
        Binding("u", "history_undo", "Undo", show=True),
        Binding("ctrl+r", "history_redo", "Redo", show=True),
        Binding("left_square_bracket", "history_earlier", "g- Earlier", show=False),
        Binding("right_square_bracket", "history_later", "g+ Later", show=False),
        Binding("J", "focus_jump", "Jump (Shift+J)", show=True),
        Binding("i", "focus_mutation", "Edit", show=True),
        Binding("I", "focus_mutation_top", "Edit @ Top", show=False),
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

        self.frag = ModularBlockEditor(str(self.filepath))
        self.language = self._detect_language()
        self.initial_anchor = initial_anchor
        self.start_in_workspace = start_in_workspace
        self.internal_yank_buffer: str = ""
        self.mutation_op: str = "replace"   # set with :op

        self.navigation_strategy = DefaultNavigationStrategy(self)
        self.mutation_strategy = DefaultMutationStrategy(self)
        self.stage_strategy = StageStrategy(self)
        self.history_strategy = HistoryStrategy(self)
        self.command_strategy = CommandStrategy(self)
        self.search_strategy = SearchStrategy(self)
        self.workspace_strategy = WorkspaceStrategy(self)
        self._cmd_mode = ":"
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
                    placeholder="Jump: number (block / file) | letters = file code in AST view | y:n yank",
                    id="jump-input",
                )
                yield NavigableTree("Document Root", id="ast-tree")

            with Vertical(id="right-pane"):
                yield Label("", id="preview-label")
                yield VimTextArea(id="content-input")
                with Horizontal(id="cmdbar"):
                    yield Label(":", id="cmd-label")
                    yield CommandInput(id="cmd-input")

            yield UndoTreePanel(id="undotree-panel")

        yield RichLog(id="status-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Modular Editor — {self.filepath.name}"
        self.refresh_buffer_label()
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
        if self.frag.blocks:
            self.navigation_strategy.select_block(0)  # whole file in the active buffer

    def refresh_buffer_label(self) -> None:
        self.query_one("#preview-label", Label).update(
            "[bold #00d7ff] Active Buffer [/bold #00d7ff]"
            f"[dim](Enter / :w write · op: {self.mutation_op} · / search · E smart edit · :help)[/dim]"
        )

    # --- Tree / mode actions ----------------------------------------------

    def action_toggle_tree_mode(self) -> None:
        new_mode = not self.navigation_strategy.directory_mode
        self.navigation_strategy.set_filesystem_mode(directory_mode=new_mode)
        mode_str = "Workspace Directory Mode (n = new, D = delete)" if new_mode else "Single-File AST Mode"
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

    # --- Command line (: and /) ---------------------------------------------

    def _open_bar(self, mode: str, prefill: str = "") -> None:
        self._cmd_mode = mode
        self._cmd_return_focus = self.focused
        self.query_one("#cmd-label", Label).update(mode)
        self.query_one("#cmdbar").add_class("visible")
        cmd = self.query_one("#cmd-input", CommandInput)
        cmd.reset()
        if prefill:
            cmd.value = prefill
            cmd.cursor_position = len(prefill)
        cmd.focus()

    def action_open_cmdline(self) -> None:
        self._open_bar(":")

    def action_open_search(self) -> None:
        self._open_bar("/")

    def close_cmdline(self) -> None:
        self.query_one("#cmdbar").remove_class("visible")
        target = self._cmd_return_focus
        if target is not None and target.is_attached:
            target.focus()
        else:
            self.query_one("#ast-tree", NavigableTree).focus()

    # --- Search, workspace files, smart edit ----------------------------------

    def action_search_next(self) -> None:
        self.search_strategy.step(1)

    def action_search_prev(self) -> None:
        self.search_strategy.step(-1)

    def action_ctx_next(self) -> None:
        """`n`: new file in workspace mode, otherwise next search hit."""
        if self.navigation_strategy.directory_mode:
            self._open_bar(":", "new ")
        else:
            self.search_strategy.step(1)

    def action_ctx_prev(self) -> None:
        if not self.navigation_strategy.directory_mode:
            self.search_strategy.step(-1)

    def action_delete_file(self) -> None:
        if not self.navigation_strategy.directory_mode:
            self.log_status("[#ffb86c]Delete works in workspace mode (Ctrl+E); in the buffer use :rm.[/#ffb86c]")
            return
        self.workspace_strategy.delete("")

    def action_smart_edit(self) -> None:
        if self.frag is None:
            return
        self.push_screen(SmartEditScreen(), self._after_smart_edit)

    def _after_smart_edit(self, result) -> None:
        if result:
            self.log_status(f"[bold #00ffaf]{result}[/bold #00ffaf]")
        self.query_one("#content-input", VimTextArea).focus()

    # --- Focus / editing ------------------------------------------------------

    def action_focus_jump(self) -> None:
        self.query_one("#jump-input", Input).focus()

    def action_focus_mutation(self) -> None:
        self.query_one("#content-input", VimTextArea).focus()

    def action_focus_mutation_top(self) -> None:
        area = self.query_one("#content-input", VimTextArea)
        area.focus()
        area.move_cursor((0, 0))

    def action_submit_mutation(self) -> None:
        """Queue the buffer without writing (:queue)."""
        self.mutation_strategy.queue()

    def action_commit_and_write_disk(self) -> None:
        """Enter (NORMAL mode in the buffer) or :w."""
        self.mutation_strategy.commit()

    def action_refresh_tree(self) -> None:
        self.frag.parse_document()
        self.navigation_strategy.populate_tree()
        self.log_status("[#00d7ff]AST Tree re-parsed and refreshed.[/#00d7ff]")

    def action_blur_inputs(self) -> None:
        self.query_one("#ast-tree", NavigableTree).focus()

    def action_copy_fragment(self) -> None:
        """y: yank the highlighted node, else the persisted workspace selection, else the block."""
        nav = self.navigation_strategy
        node = self.query_one("#ast-tree", NavigableTree).cursor_node
        if node is not None and isinstance(node.data, dict) and node.data.get("type") == "file":
            nav.yank_target(node)
        elif nav.directory_mode and nav.workspace_selected is not None:
            nav.yank_target({"type": "file", "path": nav.workspace_selected})
        elif node is not None and isinstance(node.data, dict):
            nav.yank_target(node)
        elif self.selected_block_id is not None:
            nav.yank_target(self.selected_block_id)

    # --- Events ---------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Typing a number while the tree is focused jumps straight into the jump box."""
        focused = self.focused
        if isinstance(focused, NavigableTree) and focused.id == "ast-tree":
            if event.is_printable and event.character and event.character.isdigit():
                jump = self.query_one("#jump-input", Input)
                jump.focus()
                jump.value = event.character
                jump.cursor_position = len(jump.value)
                event.stop()
                event.prevent_default()

    def on_tree_node_highlighted(self, event: NavigableTree.NodeHighlighted) -> None:
        """Workspace mode remembers the last highlighted file, so y / D act on it after jumps."""
        nav = self.navigation_strategy
        data = event.node.data
        if nav.directory_mode and isinstance(data, dict) and data.get("type") == "file":
            nav.workspace_selected = Path(data["path"])

    def on_tree_node_selected(self, event: NavigableTree.NodeSelected) -> None:
        if event.node.data is not None:
            self.navigation_strategy.select_block(event.node.data)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "cmd-input":
            event.stop()
            mode = self._cmd_mode
            self.close_cmdline()  # restore focus first so :q / :wq can then leave the buffer
            if mode == "/":
                self.search_strategy.find(event.value)
            else:
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
