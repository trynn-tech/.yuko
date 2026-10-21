"""CLI entry point for frag: headless AST inspection, smart edits, and line count metrics.

Supports:
  -h, --help      Display usage guide and CLI command examples
  -o, --overview  Print structured semantic overview of AST blocks, functions, and stages
  -l, --lines     Compute line count, character footprints, and block distribution
  -e, --edit      Apply smart search/replace anchor patches from standard input or arguments
"""

import sys
import argparse
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.markup import escape

try:
    from frag.modular_editor import ModularBlockEditor
    from frag.smart_edit import plan_edits
except (ImportError, ValueError):
    # Direct script execution fallback
    for _parent in Path(__file__).resolve().parents:
        if (_parent / "modular_editor.py").exists():
            if str(_parent) not in sys.path:
                sys.path.insert(0, str(_parent))
            break
    from frag.modular_editor import ModularBlockEditor
    from frag.smart_edit import plan_edits

console = Console()


def print_help() -> None:
    help_text = """
[bold #00d7ff]frag[/bold #00d7ff] — AST Block Manager & Structural Code Parser

[bold]Usage:[/bold]
  [bold #00ffaf]frag-tui [filepath][/bold #00ffaf]          Launch interactive Textual TUI editor & workspace explorer
  [bold #00ffaf]frag [filepath] [flags][/bold #00ffaf]      Run headless CLI utilities, AST overview, and code metrics

[bold]Flags:[/bold]
  [bold #ffb86c]-h, --help[/bold #ffb86c]        Show this help message and exit
  [bold #ffb86c]-o, --overview[/bold #ffb86c]      Print structured semantic breakdown (functions, classes, stages, imports)
  [bold #ffb86c]-l, --lines[/bold #ffb86c]       Compute granular line counts, character footprints, and block distribution
  [bold #ffb86c]-e, --edit <patch>[/bold #ffb86c] Execute smart edits via non-destructive search/replace anchor blocks
  [bold #ffb86c]-w, --edit <patch>[/bold #ffb86c] Execute smart edits via non-destructive search/replace anchor blocks

[bold]Examples:[/bold]
  [dim]# Launch interactive TUI[/dim]
  frag-tui flake.nix

  [dim]# Launch interactive TUI In Workspace Directory Mode[/dim]
  frag-tui flake.nix

  [dim]# Print AST overview to terminal / pipe to LLM context[/dim]
  frag src/frag/modular_editor.py -o

  [dim]# Display line and block metrics[/dim]
  frag flake.nix -l

  [dim]# Apply a smart search/replace edit[/dim]
  cat patch.diff | frag target.py -e -
"""
    console.print(help_text.strip())


def run_overview(editor: ModularBlockEditor) -> None:
    summary = editor.get_summary()
    
    console.print(f"\n[bold #00d7ff]📄 File:[/#00d7ff] [bold]{escape(summary['file'])}[/bold]")
    console.print(
        f"[dim]Total Lines:[/dim] {summary['line_count']}  |  "
        f"[dim]Functions:[/dim] {summary['function_count']}  |  "
        f"[dim]Classes:[/dim] {summary['class_count']}  |  "
        f"[dim]Stages:[/dim] {summary['stage_count']}\n"
    )

    table = Table(title="AST Selection Array & Structural Blocks", show_header=True, header_style="bold #00ffaf")
    table.add_column("Index", style="cyan", justify="right")
    table.add_column("Type", style="yellow")
    table.add_column("Name", style="bold white")
    table.add_column("Lines", style="green")
    table.add_column("Stage", style="magenta")

    for b in summary["selection_array"]:
        stage_str = f"Stage {b['stage']}" if b["stage"] is not None else "-"
        table.add_row(str(b["index"]), b["type"], escape(b["name"]), b["lines"], stage_str)

    console.print(table)


def run_lines(editor: ModularBlockEditor) -> None:
    lines = editor.raw_code.splitlines()
    total_lines = len(lines)
    blank_lines = sum(1 for line in lines if not line.strip())
    code_lines = total_lines - blank_lines
    char_count = len(editor.raw_code)

    funcs = [b for b in editor.blocks if b.block_type == "function"]
    classes = [b for b in editor.blocks if b.block_type == "class"]
    stages = [b for b in editor.blocks if b.block_type == "stage"]

    table = Table(title="Line & Symbol Metrics", show_header=True, header_style="bold #00ffaf")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Count / Value", style="bold yellow", justify="right")

    table.add_row("Total Lines", str(total_lines))
    table.add_row("Code Lines (non-blank)", str(code_lines))
    table.add_row("Blank / Whitespace Lines", str(blank_lines))
    table.add_row("Character Footprint", f"{char_count:,} chars")
    table.add_row("AST Function Blocks", str(len(funcs)))
    table.add_row("AST Class/Struct Blocks", str(len(classes)))
    table.add_row("Explicit Stage Headers", str(len(stages)))

    console.print(table)


def run_edit(editor: ModularBlockEditor, patch_arg: str) -> None:
    if patch_arg == "-":
        patch_text = sys.stdin.read()
    elif Path(patch_arg).exists():
        patch_text = Path(patch_arg).read_text()
    else:
        patch_text = patch_arg

    is_python = editor.filepath.suffix.lower() in (".py", ".pyi")
    plan, err = plan_edits(
        code=editor.raw_code,
        blocks=editor.blocks,
        snippet=patch_text,
        selected_index=0,
        is_python=is_python
    )

    if err:
        console.print(f"[bold #ff5f5f]Smart Edit Error:[/bold #ff5f5f] {escape(err)}")
        sys.exit(1)

    if not plan:
        console.print("[#ffb86c]No applicable search/replace targets matched.[/#ffb86c]")
        return

    for op_type, target_indices, content in plan:
        editor.queue_mutation(op_type, target_indices, content)

    updated_code = editor.apply_batch()
    editor.filepath.write_text(updated_code)
    console.print(f"[bold #00ffaf]Successfully applied smart edit(s) to {escape(str(editor.filepath))}[/bold #00ffaf]")


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-o", "--overview", action="store_true")
    parser.add_argument("-l", "--lines", action="store_true")
    parser.add_argument("-e", "--edit", type=str, nargs="?", const="-")
    parser.add_argument("filepath", nargs="?", type=str)

    args, unknown = parser.parse_known_args()

    if args.help or (not args.filepath and not args.overview and not args.lines and not args.edit):
        print_help()
        sys.exit(0)

    target_path = Path(args.filepath) if args.filepath else Path(".")
    if not target_path.exists() and not args.help:
        console.print(f"[bold #ff5f5f]Error:[/bold #ff5f5f] File path '{escape(str(target_path))}' does not exist.")
        sys.exit(1)

    editor = ModularBlockEditor(str(target_path))

    if args.overview:
        run_overview(editor)
    elif args.lines:
        run_lines(editor)
    elif args.edit is not None:
        run_edit(editor, args.edit)
    else:
        # Default fallback if filepath provided without flags
        run_overview(editor)


if __name__ == "__main__":
    main()
