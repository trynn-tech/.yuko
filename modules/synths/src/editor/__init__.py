"""
Modular Block & Stage Editor (Frag Engine Interface)
"""

from .modular_editor import (
    CodeBlock,
    ModularBlockEditor,
    MutationOp,
)

# Optional CLI entrypoint
try:
    from .cli_editor import main as cli_main
except ImportError:
    cli_main = None


# Lazy load TUI components to handle environments missing Textual gracefully
def get_tui_app():
    """Returns the Textual TUI App class if Textual is installed."""
    try:
        from .tui_editor import ModularEditorTUI
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
