"""UndoTreePanel: a jiaoshijie/undotree-style history browser.

Layout: ASCII graph on top (newest first, trunk in the left lane), diff preview below.
The diff always compares the CURRENT state with the state under the cursor.

Keys (graph):
    j / k     move to next / previous state (no change to the file)
    gj        jump to the parent of the state under the cursor
    gg / G    first / last state
    J / K     move to next / previous state AND apply it (written to disk)
    Enter     apply (checkout) the state under the cursor
    p         switch focus between graph and diff
    q         close the panel (also works in the diff)
    S         re-render from the history
Design intent (same as the plugin): open it, do the operation, close it.
"""

from pathlib import Path
from typing import Dict, Optional

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Label, OptionList, RichLog
from textual.widgets.option_list import Option

try:
    from ...undo_tree import UndoTree, layout_graph
except (ImportError, ValueError):
    from editor.undo_tree import UndoTree, layout_graph

MAX_DIFF_LINES = 400


class UndoGraph(OptionList):
    """One selectable option per state; branch-merge connector rows are disabled (skipped)."""

    BINDINGS = [
        Binding("j", "nav_down", "Next", show=False),
        Binding("k", "nav_up", "Prev", show=False),
        Binding("g", "g_prefix", "gj / gg", show=False),
        Binding("G", "nav_last", "Last", show=False),
        Binding("J", "apply_down", "Next + apply", show=False),
        Binding("K", "apply_up", "Prev + apply", show=False),
        Binding("p", "focus_diff", "Diff", show=False),
        Binding("q", "close_panel", "Close", show=False),
        Binding("S", "resync", "Resync", show=False),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._g = False
        self._index_of: Dict[int, int] = {}
        self._history: Optional[UndoTree] = None

    # --- rendering -------------------------------------------------------

    @property
    def cursor_seq(self) -> Optional[int]:
        if self.highlighted is None:
            return None
        try:
            opt = self.get_option_at_index(self.highlighted)
        except Exception:
            return None
        return int(opt.id) if opt.id is not None else None

    def render_history(self, history: UndoTree, cursor_seq: Optional[int] = None) -> None:
        self._history = history
        self._index_of = {}
        options = []
        for row in layout_graph(history):
            if row.seq is None:
                options.append(Option(Text(row.graph, style="#555555", no_wrap=True), disabled=True))
                continue
            self._index_of[row.seq] = len(options)
            options.append(Option(self._node_text(history, row), id=str(row.seq)))
        self.clear_options()
        self.add_options(options)
        target = cursor_seq if cursor_seq in self._index_of else history.current.seq
        self.call_after_refresh(self.place_cursor, target)

    @staticmethod
    def _node_text(history: UndoTree, row) -> Text:
        node = history.nodes[row.seq]
        is_cur = node is history.current
        t = Text(no_wrap=True, overflow="ellipsis")
        for i, ch in enumerate(row.graph):
            if i == row.node_col:
                t.append("@" if is_cur else "*", style="bold #00ffaf" if is_cur else "#00d7ff")
            else:
                t.append(ch, style="#666666")
        t.append(f" {row.seq}", style="bold #00ffaf" if is_cur else "bold")
        t.append(f"  {node.label}", style="bold" if is_cur else "")
        if node.parent is not None:
            added, removed = node.stats
            t.append(f"  +{added}", style="green")
            t.append(f" -{removed}", style="red")
        from datetime import datetime  # local import keeps module import light

        t.append(f"  {datetime.fromtimestamp(node.timestamp).strftime('%H:%M:%S')}", style="dim")
        return t

    def place_cursor(self, seq: int) -> None:
        idx = self._index_of.get(seq)
        if idx is None:
            return
        self.highlighted = idx
        try:
            self.scroll_to_highlight()
        except Exception:
            pass

    # --- actions (bindings only, so behaviour doesn't depend on key-dispatch order) ---

    def action_nav_down(self) -> None:
        if self._g:  # gj
            self._g = False
            seq = self.cursor_seq
            node = self._history.nodes.get(seq) if (self._history and seq is not None) else None
            if node is not None and node.parent is not None:
                self.place_cursor(node.parent.seq)
            return
        self.action_cursor_down()

    def action_nav_up(self) -> None:
        self._g = False
        self.action_cursor_up()

    def action_g_prefix(self) -> None:
        if self._g:  # gg
            self._g = False
            self.action_first()
        else:
            self._g = True

    def action_nav_last(self) -> None:
        self._g = False
        self.action_last()

    def _apply_cursor(self) -> None:
        seq = self.cursor_seq
        if seq is not None:
            self.app.history_strategy.goto(seq)

    def action_apply_down(self) -> None:
        self._g = False
        self.action_cursor_down()
        self._apply_cursor()

    def action_apply_up(self) -> None:
        self._g = False
        self.action_cursor_up()
        self._apply_cursor()

    def action_focus_diff(self) -> None:
        self._g = False
        self.screen.query_one("#undo-diff").focus()

    def action_close_panel(self) -> None:
        self.app.close_undotree()

    def action_resync(self) -> None:
        self.app.refresh_undotree_view(cursor_seq=self.cursor_seq)

    def on_blur(self) -> None:
        self._g = False


class DiffLog(RichLog):
    BINDINGS = [
        Binding("p", "focus_graph", "Graph", show=False),
        Binding("q", "close_panel", "Close", show=False),
    ]

    def action_focus_graph(self) -> None:
        self.screen.query_one("#undo-graph").focus()

    def action_close_panel(self) -> None:
        self.app.close_undotree()


class UndoTreePanel(Vertical):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._history: Optional[UndoTree] = None

    def compose(self) -> ComposeResult:
        yield Label(" 🌳 Undotree", id="undo-title")
        yield Label("[dim] j/k move · J/K apply · gj parent · ⏎ checkout · p diff · q close · S resync[/dim]", id="undo-hints")
        yield UndoGraph(id="undo-graph")
        yield DiffLog(id="undo-diff", highlight=False, markup=False, wrap=False)

    def show(self, history: UndoTree, cursor_seq: Optional[int] = None) -> None:
        self._history = history
        self.query_one("#undo-title", Label).update(
            f" 🌳 Undotree  [dim]{history.size} states · now [{history.current.seq}][/dim]"
        )
        self.query_one("#undo-graph", UndoGraph).render_history(history, cursor_seq)

    def focus_graph(self) -> None:
        self.query_one("#undo-graph", UndoGraph).focus()

    def _show_diff(self, seq: int) -> None:
        log = self.query_one("#undo-diff", DiffLog)
        log.clear()
        h = self._history
        if h is None or seq not in h.nodes:
            return
        cur = h.current.seq
        log.border_title = f"now [{cur}] → [{seq}]"
        if seq == cur:
            log.write(Text("This is the current state.", style="dim"))
            return
        name = Path(getattr(self.app, "filepath", "file")).name
        diff = h.diff(cur, seq, filename=name)
        if not diff:
            log.write(Text("(identical text)", style="dim"))
            return
        lines = diff.splitlines()
        if len(lines) > MAX_DIFF_LINES:
            diff = "\n".join(lines[:MAX_DIFF_LINES]) + f"\n… {len(lines) - MAX_DIFF_LINES} more lines"
        log.write(Syntax(diff, "diff", theme="monokai", background_color="#151515"))

    # Messages from our own graph are stopped here so the app's other handlers never see them.
    def on_option_list_option_highlighted(self, event) -> None:
        event.stop()
        if event.option.id is not None:
            self._show_diff(int(event.option.id))

    def on_option_list_option_selected(self, event) -> None:
        event.stop()
        if event.option.id is not None:
            self.app.history_strategy.goto(int(event.option.id))  # Enter == checkout
