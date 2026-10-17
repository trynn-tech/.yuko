"""SmartEditScreen: paste/type several functions or classes and apply them in one go.

Left: input (same Vim keys as the main buffer).  Right: live plan showing, per piece of code,
whether it REPLACES an existing function/class/variable (matched by name and scope), is
UNCHANGED, or is INSERTED (placed after its previous match, before the next, or at the end).
Write the plan with :w  (or Enter in NORMAL mode). :q cancels, :q! discards.
Everything lands as ONE undo state in the UndoTree.
"""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, RichLog, TextArea

try:
    from ...smart_edit import apply_plan, plan_edits, plan_label
    from .cmdline import CommandInput
    from .inputs import VimTextArea
except (ImportError, ValueError):
    from editor.smart_edit import apply_plan, plan_edits, plan_label
    from editor.ui.components.cmdline import CommandInput
    from editor.ui.components.inputs import VimTextArea

ICON = {"replace": ("~", "#ffb86c"), "unchanged": ("=", "#888888"), "insert_after": ("+", "#00ffaf"),
        "insert_before": ("+", "#00ffaf"), "error": ("!", "#ff5555")}


class _MiniEx:
    """Just enough of CommandStrategy for CommandInput (history + completion)."""
    history: list = []

    def complete(self, text):
        return next((c + " " for c in ("write", "wq", "quit", "help") if c.startswith(text) and text), None)


class SmartEditScreen(ModalScreen):
    DEFAULT_CSS = """
    SmartEditScreen { align: center middle; background: #000000aa; }
    #smart-box { width: 94%; height: 90%; border: thick #00d7ff; background: #121212; }
    #smart-body { height: 1fr; }
    #smart-left { width: 55%; }
    #smart-right { width: 45%; border-left: solid #333333; }
    #smart-input { height: 1fr; border: solid #333333; }
    #smart-input:focus { border: solid #00d7ff; }
    #smart-plan { height: 1fr; padding: 0 1; background: #121212; }
    #smart-cmdbar { height: 1; display: none; }
    #smart-cmdbar.visible { display: block; }
    #smart-cmd-label { width: 1; color: #00d7ff; }
    #smart-cmd { border: none; height: 1; padding: 0; }
    #smart-status { height: 1; color: #888888; }
    """

    BINDINGS = [Binding("escape", "noop", show=False)]

    def __init__(self) -> None:
        super().__init__()
        self.command_strategy = _MiniEx()
        self._plan = []
        self._error = None

    # --- layout ---------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(id="smart-box"):
            yield Label("[bold #00d7ff] Smart Edit [/bold #00d7ff] [dim]paste functions/classes; they are matched to the file by name[/dim]")
            with Horizontal(id="smart-body"):
                with Vertical(id="smart-left"):
                    yield VimTextArea(id="smart-input")
                with Vertical(id="smart-right"):
                    yield Label("[bold] Plan [/bold]")
                    yield RichLog(id="smart-plan", highlight=False, markup=False, wrap=True)
            with Horizontal(id="smart-cmdbar"):
                yield Label(":", id="smart-cmd-label")
                yield CommandInput(id="smart-cmd")
            yield Label("i / p = type or paste · :w or Enter(NORMAL) = apply · :q = cancel · :help", id="smart-status")

    def on_mount(self) -> None:
        area = self.query_one("#smart-input", VimTextArea)
        area.set_language("python" if self._is_python() else None)
        area.focus()
        self.call_after_refresh(area.enter_insert)  # ready to paste immediately
        self._refresh_plan()

    # --- plan -----------------------------------------------------------------

    def _is_python(self) -> bool:
        return self.app.filepath.suffix.lower() in (".py", ".pyi", "")

    def _refresh_plan(self) -> None:
        text = self.query_one("#smart-input", VimTextArea).text
        log = self.query_one("#smart-plan", RichLog)
        log.clear()
        ed = self.app.editor
        self._plan, self._error = plan_edits(ed.raw_code, ed.blocks, text, self.app.selected_block_id, self._is_python())
        if not text.strip():
            log.write(Text("Paste code on the left.", style="dim"))
            return
        if self._error:
            log.write(Text(self._error, style="bold #ff5555"))
            return
        for p in self._plan:
            icon, color = ICON[p.action]
            line = Text()
            line.append(f"{icon} ", style=f"bold {color}")
            line.append(f"{p.action.replace('_', ' '):<13}", style=color)
            line.append(p.label, style="bold")
            if p.applies:
                line.append(f"  +{p.added} -{p.removed}", style="dim")
            log.write(line)
            if p.note:
                log.write(Text(f"    {p.note}", style="dim"))
        n = sum(1 for p in self._plan if p.applies)
        log.write(Text(f"\n{n} change(s) ready" if n else "\nNothing to apply.", style="bold #00d7ff" if n else "dim"))

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "smart-input":
            event.stop()
            self._refresh_plan()

    # --- hooks used by VimTextArea (it routes to the screen when the screen defines them) ---

    def action_open_cmdline(self) -> None:
        self.query_one("#smart-cmdbar").add_class("visible")
        cmd = self.query_one("#smart-cmd", CommandInput)
        cmd.reset()
        cmd.focus()

    def close_cmdline(self) -> None:
        self.query_one("#smart-cmdbar").remove_class("visible")
        self.query_one("#smart-input", VimTextArea).focus()

    def action_commit_and_write_disk(self) -> None:
        self._apply()

    def action_blur_inputs(self) -> None:
        pass  # Esc in NORMAL mode must not leave the window; use :q

    def action_noop(self) -> None:
        pass

    action_open_search = action_search_next = action_search_prev = action_noop
    action_history_undo = action_history_redo = action_history_earlier = action_history_later = action_noop

    # --- commands ---------------------------------------------------------------

    def on_input_submitted(self, event) -> None:
        if event.input.id != "smart-cmd":
            return
        event.stop()
        line = event.value.strip().lstrip(":").strip()
        self.close_cmdline()
        name, _, _ = line.partition(" ")
        bang = name.endswith("!")
        name = name.rstrip("!").lower()
        if name in ("w", "write", "wq", "x"):
            self._apply()
        elif name in ("q", "quit"):
            area = self.query_one("#smart-input", VimTextArea)
            if area.text.strip() and not bang:
                self.app.log_status("[bold #ff5555]E37: unsaved input (use :q! to discard, :w to apply)[/bold #ff5555]")
            else:
                self.dismiss(None)
        elif name in ("help", "h"):
            self.app.log_status("[#a0a0a0]:w apply the plan · :q cancel · :q! discard input[/#a0a0a0]")
        elif line:
            self.app.log_status(f"[bold #ff5555]E492: Not an editor command: {line}[/bold #ff5555]")

    def _apply(self) -> None:
        if self._error:
            self.app.log_status(f"[bold #ff5555]{self._error}[/bold #ff5555]")
            return
        if not any(p.applies for p in self._plan):
            self.app.log_status("[#ffb86c]Nothing to apply.[/#ffb86c]")
            return
        ed = self.app.editor
        if ed.mutation_buffer:
            self.app.log_status(f"[#ffb86c]Dropped {len(ed.mutation_buffer)} queued op(s): smart edit applies as one batch.[/#ffb86c]")
        apply_plan(ed, self._plan)
        label = plan_label(self._plan)
        ok = self.app.mutation_strategy.apply(label=label)
        if ok:
            self.dismiss(label)
