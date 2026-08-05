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

# Engine & Memory components
from engine.anchor_patch import AnchorPatcher
from engine.analyzer import CodeAnalyzer
from engine.context import RepoContext
from engine.executor import Executor
from engine.llm import LocalInferenceEngine
from engine.redis_store import RedisMemoryStore
from engine.working_memory import WorkingMemoryPipeline

# Reasoning & Knowledge Graph Domain
from reasoning.graph_linker import KnowledgeGraphLinker
from reasoning.pipeline import ReasoningOrchestrator

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
        "--memory-query",
        type=str,
        help="Query Redis working memory for recent ThoughtFrames by session ID",
    )
    parser.add_argument(
        "--inspect-graph",
        action="store_true",
        help="Inspect structural entities and functions recorded in the Neo4j Knowledge Graph",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Flush all active Redis session keys and clear Neo4j graph nodes for clean test runs",
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

    # -------------------------------------------------------------------
    # UTILITY MODE 1: Database Reset (--reset-db)
    # -------------------------------------------------------------------
    if args.reset_db:
        console.print("[bold red]🧹 Resetting Reasoning Stores (Redis & Neo4j)...[/bold red]")
        redis_ok = RedisMemoryStore().flush_db()
        graph_ok = KnowledgeGraphLinker().flush_graph()

        if redis_ok:
            console.print("  [green]✓ Redis reasoning namespace cleared.[/green]")
        else:
            console.print("  [yellow]⚠️ Could not connect to Redis server (skipping).[/yellow]")

        if graph_ok:
            console.print("  [green]✓ Neo4j graph purged.[/green]")
        else:
            console.print("  [yellow]⚠️ Could not connect to Neo4j database (skipping).[/yellow]")

        sys.exit(0)

    # -------------------------------------------------------------------
    # UTILITY MODE 2: Query Redis Memory (--memory-query)
    # -------------------------------------------------------------------
    if args.memory_query:
        store = RedisMemoryStore()
        session_id = args.memory_query.strip()
        console.print(f"[bold cyan]🔍 Querying Working Memory for session:[/bold cyan] '{session_id}'")
        
        data = store.retrieve_thought_frame(session_id)
        if data:
            console.print(
                Panel(
                    Syntax(json.dumps(data, indent=2), "json", theme="ansi_dark", line_numbers=True),
                    title=f"[bold green]ThoughtFrame Hit [{session_id}][/bold green]",
                )
            )
        else:
            console.print("[yellow]No exact ThoughtFrame hit for given session ID.[/yellow]")
        sys.exit(0)

    # -------------------------------------------------------------------
    # UTILITY MODE 3: Inspect Knowledge Graph (--inspect-graph)
    # -------------------------------------------------------------------
    if args.inspect_graph:
        graph = KnowledgeGraphLinker()
        console.print("[bold magenta]🕸️ Inspecting Neo4j Knowledge Graph...[/bold magenta]")
        
        try:
            driver = graph._get_driver()
            with driver.session() as session:
                res = session.run("MATCH (f:CodeFile)-[:CONTAINS_FUNCTION]->(fn:Function) RETURN f.path AS file, fn.name AS function LIMIT 25")
                records = [r.data() for r in res]
                
            if records:
                table = Table(title="Graph Relationships (File ➔ Function)")
                table.add_column("Source File", style="cyan")
                table.add_column("Indexed Function", style="green")
                
                for r in records:
                    table.add_row(r["file"], r["function"])
                console.print(table)
            else:
                console.print("[yellow]Graph is currently empty. Run synthesis creation prompts to populate nodes.[/yellow]")
        except Exception as e:
            console.print(f"[bold red]Graph connection error:[/bold red] {e}")
        sys.exit(0)

    executor = Executor()
    patcher = AnchorPatcher()
    analyzer = CodeAnalyzer()
    context_builder = RepoContext()
    engine = LocalInferenceEngine(endpoint=args.endpoint, model_name=args.model)
    memory_pipeline = WorkingMemoryPipeline(patcher=patcher, analyzer=analyzer)
    orchestrator = ReasoningOrchestrator()

    console.print(
        "[bold cyan]=^-.-^= Local Synth Engine[/bold cyan] [dim](Nix-Bound / RTX 4060 Optimized)[/dim]\n"
    )

    # -------------------------------------------------------------------
    # MODE 1: Apply pre-existing raw LLM response directly
    # -------------------------------------------------------------------
    if args.apply_response:
        response_file = Path(args.apply_response)
        if not response_file.exists():
            console.print(f"[red]Error:[/red] Response file '{args.apply_response}' not found.")
            sys.exit(1)

        raw_llm_output = response_file.read_text(encoding="utf-8")
        console.print("[yellow]Parsing incoming LLM edit blocks via AnchorPatcher...[/yellow]")
        blocks = patcher.parse_blocks(raw_llm_output)

        if not blocks:
            console.print("[bold red]No valid anchor/edit blocks found in response.[/bold red]")
            sys.exit(1)

        _apply_patch_blocks(blocks, patcher, executor, dry_run=args.dry_run)
        return

    # -------------------------------------------------------------------
    # MODE 2: Full pipeline (Context ➔ Prompt ➔ Stream ➔ Working Memory ➔ Graph Sync)
    # -------------------------------------------------------------------
    if not args.all_files and not args.prompt:
        console.print("[yellow]Usage:[/yellow] synth <file1> <file2> -p 'instruction'")
        console.print("       synth --apply-response llm_output.txt")
        console.print("       synth --reset-db | --inspect-graph | --memory-query <session_id>")
        sys.exit(0)

    console.print("[dim]Collecting context via ripgrep & fd...[/dim]")

    target_paths = [Path(f) for f in args.all_files]
    file_contexts = context_builder.build_context(target_paths)

    # MODE ACTIVATION RULE:
    # EDIT MODE: Triggered if ANY target path specified by user exists on disk.
    # CREATION MODE: Triggered if no targets exist OR target is a directory workspace.
    is_edit_mode = any(ctx.exists and ctx.content.strip() for ctx in file_contexts)

    # -------------------------------------------------------------------
    # RETRIEVE GRAPH CONTEXT (Neo4j)
    # -------------------------------------------------------------------
    prompt_keywords = [
        word.strip().lower()
        for word in (args.prompt or "").split()
        if len(word) > 3 and word.isalnum()
    ]
    graph_context = KnowledgeGraphLinker().retrieve_graph_context(keywords=prompt_keywords)

    user_query_payload = args.prompt or "Refactor code as requested."
    if graph_context.get("records"):
        graph_summary_lines = ["\n### KNOWLEDGE GRAPH CONTEXT (Neo4j):"]
        for rec in graph_context["records"]:
            funcs_str = ", ".join(rec["functions"]) if rec["functions"] else "None"
            tags_str = ", ".join(rec["matched_tags"]) if rec["matched_tags"] else "None"
            graph_summary_lines.append(
                f"- File: `{rec['file_path']}` | Functions: `{funcs_str}` | Concepts: [{tags_str}]"
            )
        user_query_payload = "\n".join(graph_summary_lines) + f"\n\n### USER INSTRUCTION:\n{user_query_payload}"

    system_prompt = get_system_prompt(file_contexts, is_edit_mode=is_edit_mode)
    user_prompt = build_user_prompt(
        user_query=user_query_payload,
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
    # WORKING MEMORY & REASONING PIPELINE
    # -------------------------------------------------------------------
    console.print("\n[dim]Processing synthesis through Working Memory Pipeline...[/dim]")

    thought_frame = memory_pipeline.process_synthesis(
        instruction=args.prompt or "Refactor code as requested.",
        raw_llm_response=raw_response,
        llm_client=engine,
        explicit_target=target_paths[0] if target_paths else None,
    )

    # Run vectorization, Redis memory persistence, and Neo4j graph sync
    sync_results = orchestrator.process_and_store(thought_frame)

    # Render ThoughtFrame JSON payload to terminal
    frame_json = thought_frame.to_redis_payload()
    console.print(
        Panel(
            Syntax(frame_json, "json", theme="ansi_dark", line_numbers=True),
            title=f"[bold magenta]Working Memory Frame Payload [{thought_frame.session_id}][/bold magenta]",
        )
    )

    if sync_results["redis_saved"]:
        console.print("[dim green]✓ Persisted to Redis vector memory[/dim green]")
    if sync_results["graph_synced"]:
        console.print("[dim magenta]✓ Synchronized AST nodes in Neo4j graph[/dim magenta]")

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
            else:
                console.print(f"[bold red]✗ Failed to modify {filepath}[/bold red]")
        else:
            console.print("[yellow][DRY RUN] Skipped writing to file.[/yellow]")


if __name__ == "__main__":
    main()
