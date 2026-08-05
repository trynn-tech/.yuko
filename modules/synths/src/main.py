#!/usr/bin/env python3
# modules/synths/src/main.py

import argparse
import json
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# Engine components
from engine.anchor_patch import AnchorPatcher
from engine.analyzer import CodeAnalyzer
from engine.context import RepoContext
from engine.executor import Executor
from engine.llm import LocalInferenceEngine
from engine.working_memory import WorkingMemoryPipeline

# Prompt builders
from prompts.qwen_diff import build_user_prompt, get_system_prompt

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Local-first hardware-optimized AI editing engine bound to Nix."
    )
    parser.add_argument(
        "positional_files",
        nargs="*",
        default=[],
        help="Target files or directories to include in the edit context",
    )
    parser.add_argument(
        "-f",
        "--files",
        nargs="+",
        default=[],
        help="Target files or directories to include in the edit context",
    )
    parser.add_argument(
        "-p", "--prompt", type=str, help="Instructions for the editing task"
    )
    parser.add_argument(
        "--apply-response",
        type=str,
        help="Path to raw model output file to parse and execute directly",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="http://localhost:8081/v1/chat/completions",
        help="Local LLM endpoint URL",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5",
        help="Model ID or proxy alias",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview edits without modifying target files",
    )

    args = parser.parse_args()
    args.all_files = list(set(args.positional_files + args.files))
    return args


def main():
    args = parse_args()

    executor = Executor()
    patcher = AnchorPatcher()
    analyzer = CodeAnalyzer()
    context_builder = RepoContext()
    engine = LocalInferenceEngine(endpoint=args.endpoint, model_name=args.model)
    memory_pipeline = WorkingMemoryPipeline(patcher=patcher, analyzer=analyzer)

    console.print(
        "[bold cyan]=^-.-^= Local Synth Engine[/bold cyan] [dim](Nix-Bound / RTX 4060 Optimized)[/dim]\n"
    )

    # -------------------------------------------------------------------
    # MODE 1: Apply pre-existing raw LLM response directly
    # -------------------------------------------------------------------
    if args.apply_response:
        response_file = Path(args.apply_response)
        if not response_file.exists():
            console.print(
                f"[red]Error:[/red] Response file '{args.apply_response}' not found."
            )
            sys.exit(1)
        raw_llm_output = response_file.read_text(encoding="utf-8")
        console.print("[yellow]Parsing incoming LLM edit blocks via AnchorPatcher...[/yellow]")
        blocks = patcher.parse_blocks(raw_llm_output)
        if not blocks:
            console.print(
                "[bold red]No valid anchor/edit blocks found in response.[/bold red]"
            )
            sys.exit(1)
        _apply_patch_blocks(blocks, patcher, executor, dry_run=args.dry_run)
        return

    # -------------------------------------------------------------------
    # MODE 2: Full pipeline (Context -> Prompt -> Stream -> Working Memory)
    # -------------------------------------------------------------------
    if not args.all_files and not args.prompt:
        console.print(
            "[yellow]Usage:[/yellow] synth <file1> <file2> -p 'instruction'"
        )
        console.print("       synth --apply-response llm_output.txt")
        sys.exit(0)

    console.print("[dim]Collecting context via ripgrep & fd...[/dim]")

    target_paths = [Path(f) for f in args.all_files]
    file_contexts = context_builder.build_context(target_paths)

    # -------------------------------------------------------------------
    # MODE ACTIVATION RULE:
    # EDIT MODE: Triggered if ANY target path specified by user exists on disk.
    # CREATION MODE: Triggered if no targets exist OR target is a directory workspace.
    # -------------------------------------------------------------------
    is_edit_mode = any(ctx.exists and ctx.content.strip() for ctx in file_contexts)

    system_prompt = get_system_prompt(file_contexts, is_edit_mode=is_edit_mode)
    user_prompt = build_user_prompt(
        user_query=args.prompt or "Refactor code as requested.",
        file_contexts=file_contexts,
    )

    console.print(
        Panel(
            Syntax(system_prompt, "markdown", theme="ansi_dark"),
            title="[bold green]System Prompt[/bold green]",
        )
    )
    console.print(
        Panel(
            Syntax(user_prompt, "markdown", theme="ansi_dark"),
            title="[bold blue]User Context Prompt[/bold blue]",
        )
    )

    # Stream synthesis from local endpoint
    raw_response = engine.generate_stream(
        system_prompt=system_prompt, user_prompt=user_prompt
    )
    if not raw_response:
        sys.exit(1)

    # -------------------------------------------------------------------
    # WORKING MEMORY PIPELINE & THOUGHT FRAME DISPLAY
    # -------------------------------------------------------------------
    console.print("\n[dim]Processing synthesis through Working Memory Pipeline...[/dim]")
    
    thought_frame = memory_pipeline.process_synthesis(
        instruction=args.prompt or "Refactor code as requested.",
        raw_llm_response=raw_response,
        llm_client=engine,
        explicit_target=target_paths[0] if target_paths else None,
    )

    # Render ThoughtFrame JSON payload to terminal
    frame_json = thought_frame.to_redis_payload()
    console.print(
        Panel(
            Syntax(frame_json, "json", theme="ansi_dark", line_numbers=True),
            title=f"[bold magenta]Working Memory Frame Payload [{thought_frame.session_id}][/bold magenta]",
        )
    )

    # Branch: Edit Mode (SEARCH/REPLACE) vs Creation Mode
    if is_edit_mode:
        blocks = patcher.parse_blocks(raw_response)
        if not blocks:
            console.print("[yellow]No actionable edit blocks generated by model.[/yellow]")
            return
        _apply_patch_blocks(blocks, patcher, executor, dry_run=args.dry_run)
    else:
        resolved_path = Path(thought_frame.resolved_path)

        # Overwrite Confirmation Guard
        if resolved_path.exists():
            console.print(
                f"\n[bold yellow]⚠️ File Collision:[/bold yellow] Target file '[bold cyan]{resolved_path}[/bold cyan]' already exists."
            )
            confirm = input("Overwrite file contents with synthesized code? [y/N]: ").strip().lower()
            if confirm not in ["y", "yes"]:
                console.print("[yellow]Aborted write operation. File left untouched.[/yellow]")
                sys.exit(0)

        if not args.dry_run:
            success = executor.apply_anchor_edit(
                filepath=str(resolved_path),
                search_anchor="",
                replace_block=thought_frame.extracted_code,
            )
            if success:
                console.print(f"[bold green]✓ Written to {resolved_path}[/bold green]")
        else:
            console.print("[yellow][DRY RUN] Skipped writing to file.[/yellow]")


def _apply_patch_blocks(
    blocks: list, patcher: AnchorPatcher, executor: Executor, dry_run: bool = False
):
    """Executes or previews parsed PatchBlock actions on target files with syntax highlighting."""
    for block in blocks:
        filepath = Path(block.filepath)
        search_anchor = block.search_anchor
        replace_block = block.replace_block
        lang = block.language

        console.print(f"\n[bold blue]Target File:[/bold blue] {filepath} [dim]({lang})[/dim]")

        if search_anchor:
            title = "Proposed Anchor Patch"
            diff_text = f"# SEARCH ANCHOR\n{search_anchor}\n\n# REPLACE BLOCK\n{replace_block}"
            highlighted_preview = Syntax(diff_text, lang, theme="ansi_dark", line_numbers=True)
        else:
            title = "Proposed New File"
            highlighted_preview = Syntax(replace_block, lang, theme="ansi_dark", line_numbers=True)

        console.print(Panel(highlighted_preview, title=title))

        if not dry_run:
            success = executor.apply_anchor_edit(
                filepath=str(filepath),
                search_anchor=search_anchor,
                replace_block=replace_block,
            )
            if success:
                console.print(f"[bold green]✓ Applied changes to {filepath}[/bold green]")
            else:                console.print(f"[bold red]✗ Failed to modify {filepath}[/bold red]")
        else:
            console.print("[yellow][DRY RUN] Skipped writing to file.[/yellow]")


if __name__ == "__main__":
    main()
