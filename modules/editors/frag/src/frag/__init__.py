"""Modular Block & Stage Editor (Frag Engine Interface)"""

__version__ = "0.1.0"

def __getattr__(name):
    """Lazy-load package attributes to prevent eager import warnings during -m execution."""
    if name in ("CodeBlock", "ModularBlockEditor", "MutationOp"):
        from .modular_editor import CodeBlock, ModularBlockEditor, MutationOp
        return {"CodeBlock": CodeBlock, "ModularBlockEditor": ModularBlockEditor, "MutationOp": MutationOp}[name]
    elif name == "cli_main":
        try:
            from .cli_editor import main as cli_main
            return cli_main
        except ImportError:
            return None
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

def get_tui_app():
    """Returns the Textual TUI App class if Textual is installed."""
    try:
        from .ui.app import ModularEditorTUI
        return ModularEditorTUI
    except ImportError as e:
        raise ImportError(
            "Textual is required to run the TUI editor interface. "
            "Ensure 'textual' is available in your Python environment."
        ) from e

def run_tui(filepath: str) -> None:
    """Convenience runner for launching the TUI editor directly."""
    tui_cls = get_tui_app()
    app = tui_cls(filepath)
    app.run()

__all__ = [
    "CodeBlock",
    "ModularBlockEditor",
    "MutationOp",
    "cli_main",
    "get_tui_app",
    "run_tui",
]
