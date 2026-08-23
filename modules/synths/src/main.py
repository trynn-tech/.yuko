#!/usr/bin/env python3
# src/main.py
import argparse
import sys
import time
from pathlib import Path
from rich.console import Console

from coordinator.architect import ArchitectCoordinator
from engine.anchor_patch import AnchorPatcher
from engine.executor import Executor
from memory import RedisMemoryStore, WorkingMemoryPipeline

try:
    from memory import render_thought_frame
except ImportError:
    # Graceful fallback renderer until memory package exposes render_thought_frame directly
    def render_thought_frame(frame, console=None):
        c = console or Console()
        if isinstance(frame, dict):
            c.print(f"[bold cyan]ThoughtFrame ID:[/bold cyan] {frame.get('session_id', 'N/A')}")
            c.print(f"  [dim]Instruction:[/dim] {frame.get('instruction', '')}")
            c.print(f"  [dim]Target File:[/dim] {frame.get('target_file', 'N/A')}")
            c.print(f"  [dim]Verified:[/dim] {frame.get('verification_passed', False)}")
            if "line_start" in frame:
                c.print(f"  [dim]Line Bounds:[/dim] L{frame.get('line_start')} - L{frame.get('line_end')}")
        else:
            c.print(frame)

try:
    from engine.verifier import VerificationHook
except ImportError:
    try:
        from engine.verification import VerificationHook
    except ImportError:
        VerificationHook = None

from reasoning.embedder import FeatureEmbedder, TextEmbedder
from reasoning.graph_linker import KnowledgeGraphLinker
from reasoning.pipeline import ReasoningOrchestrator

try:
    from engine.llm import LocalInferenceEngine as LLMClient
except ImportError:
    try:
        from engine.llm import LLMClient
    except ImportError:
        LLMClient = None

console = Console()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local Synth Engine (Nix-Bound / RTX 4060 Optimized)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Operational Modes
    mode_group = parser.add_argument_group("Execution Modes")
    mode_group.add_argument(
        "target_file",
        nargs="?",
        default=None,
        help="Target file path for standard single-file editing.",
    )
    mode_group.add_argument(
        "-i",
        "--input",
        type=str,
        dest="prompt",
        help="Instruction prompt for single-file edit synthesis.",
    )
    mode_group.add_argument(
        "-c",
        "--composer",
        "--recipe",
        type=str,
        dest="recipe_goal",
        help="Run semi-autonomous Composer mode to execute a multi-step recipe.",
    )
    mode_group.add_argument(
        "-t",
        "--targets",
        nargs="+",
        help="Target file(s) for Composer recipe or single-file execution.",
    )

    # Store Maintenance & Debug Flags
    db_group = parser.add_argument_group("Working Memory & Graph Diagnostics")
    db_group.add_argument(
        "--reset-db",
        action="store_true",
        help="Purge reasoning keys in Redis and reset Neo4j knowledge graph.",
    )
    db_group.add_argument(
        "--inspect-graph",
        action="store_true",
        help="Display summary table of file-to-function graph relationships.",
    )
    db_group.add_argument(
        "--memory-query",
        type=str,
        metavar="SESSION_ID",
        help="Retrieve raw ThoughtFrame payload from Redis by session ID or explicit numeric timestamp head.",
    )
    db_group.add_argument(
        "--watch",
        action="store_true",
        help="Observe real-time thought frame queue events.",
    )
    db_group.add_argument(
        "--memory-step",
        type=int,
        default=0,
        help="Historical depth step offset (1 = 1 frame back in time, -1 = 1 frame forward). Anchors to current time unless --memory-query provides a timestamp.",
    )

    # Engine Testing & Diagnostics
    test_group = parser.add_argument_group("Engine Testing & Diagnostics")
    test_group.add_argument(
        "--test",
        action="store_true",
        help="Run comprehensive engine self-tests, verifying 3-tier memory and test coverage.",
    )

    # Divergence Controls
    div_group = parser.add_argument_group("Composer Divergence Flags")
    div_group.add_argument(
        "--no-searxng",
        action="store_true",
        help="Disable SearXNG web discovery during divergence passes.",
    )
    div_group.add_argument(
        "--no-upstream",
        action="store_true",
        help="Disable upstream LLM strategy queries during divergence passes.",
    )

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    # 1. Initialize Memory, Vector, and Graph Infrastructure
    patcher = AnchorPatcher()
    graph_linker = KnowledgeGraphLinker()
    redis_store = RedisMemoryStore()
    embedder = TextEmbedder()
    feature_embedder = FeatureEmbedder()

    # Orchestrator unifies 3-tier sync (Redis, RediSearch vectors, Neo4j)
    orchestrator = ReasoningOrchestrator(
        embedder=feature_embedder,
        redis_store=redis_store,
        graph_linker=graph_linker,
    )

    memory_pipeline = WorkingMemoryPipeline(
        patcher=patcher,
        store=redis_store,
        orchestrator=orchestrator,
    )

    executor = Executor()
    llm_client = LLMClient() if LLMClient else None

    # 2. Real-Time Stream Watcher
    if args.watch:
        from memory.redis_store import watch_thought_stream
        watch_thought_stream(redis_store)
        return

    # 3. Database Maintenance & Query Commands
    if args.reset_db:
        console.print("[bold yellow]🧹 Resetting Reasoning Stores (Redis & Neo4j)...[/bold yellow]")
        redis_ok = getattr(redis_store, "flush_db", lambda: getattr(redis_store, "clear", lambda: True)())()
        neo_ok = graph_linker.flush_graph()
        if redis_ok:
            console.print("  [green]✓ Redis vector store flushed.[/green]")
        else:            console.print("  [red]⚠️ Could not flush Redis server.[/red]")
        if neo_ok:
            console.print("  [green]✓ Neo4j graph purged.[/green]")
        else:            console.print("  [red]⚠️ Could not purge Neo4j graph.[/red]")
        return

    if args.inspect_graph:
        console.print("[bold cyan]🕸️ Inspecting Neo4j Knowledge Graph...[/bold cyan]")
        ctx = graph_linker.retrieve_graph_context(keywords=["*"], limit=20)
        console.print(ctx)
        return

    if args.memory_query is not None or args.memory_step != 0:
        base_head = args.memory_query if args.memory_query is not None else time.time()
        try:
            ts_query = float(base_head)
            frame, idx, total = redis_store.retrieve_nearest_thought_frame(
                target_timestamp=ts_query,
                offset_step=args.memory_step,
            )
            direction = "past" if args.memory_step > 0 else ("future" if args.memory_step < 0 else "head")
            console.print(
                f"[bold cyan]🔍 Memory Linked-List Traversal "
                f"[Index: {idx + 1}/{total} | Step: {args.memory_step} ({direction})]:[/bold cyan]"
            )
            if frame:
                render_thought_frame(frame, console=console)
            else:
                console.print("[yellow]No matching ThoughtFrame found.[/yellow]")
        except ValueError:
            if args.memory_step != 0:
                console.print(
                    "[bold yellow]⚠️ Note: --memory-step offset is ignored when querying an explicit non-numeric Session ID string.[/bold yellow]"
                )
            console.print(f"[bold cyan]🔍 Querying Working Memory for session: '{base_head}'[/bold cyan]")
            frame = redis_store.retrieve_thought_frame(str(base_head))
            if frame:
                render_thought_frame(frame, console=console)
            else:
                console.print("[yellow]No matching ThoughtFrame found in Redis.[/yellow]")
        return

    # 4. Engine Self-Test & Coverage Integration (--test)
    if args.test:
        console.print("[bold cyan]🧪 Running Yuko Synthesizer Engine Self-Test & Coverage Audit...[/bold cyan]")
        if feature_embedder:
            encoded_vec = feature_embedder.encode("Initialize vector index and persist thought frames")
            if isinstance(encoded_vec, list) and len(encoded_vec) > 0 and isinstance(encoded_vec[0], list):
                dummy_vec: list[float] = [float(x) for x in encoded_vec[0]]
            elif isinstance(encoded_vec, list):
                dummy_vec = [float(x) for x in encoded_vec]
            else:                dummy_vec = [0.01] * 768
        else:
            dummy_vec = [0.01] * 768

        console.print("[cyan]▶ Testing Neo4j & Redis Multi-File Context Resolution...[/cyan]")
        try:
            graph_ctx = graph_linker.retrieve_graph_context(keywords=["redis_store"], limit=5)
            redis_hits = redis_store.knn_search(query_vector=dummy_vec, top_k=2)
            console.print("  [green]✓ Neo4j graph query executed successfully.[/green]")
            console.print(f"  [green]✓ RediSearch KNN hits found:[/green] {len(redis_hits)} vectors")
        except Exception as e:
            console.print(f"  [yellow]⚠️ 3-Tier context check warning: {e}[/yellow]")

        console.print("\n[cyan]▶ Running Pytest Coverage Suite (Live Stream)...[/cyan]")
        import subprocess
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--cov=src",
            "--cov=engine",
            "--cov=reasoning",
            "--cov=coordinator",
            "--cov=prompts",
            "--cov=vista",
            "--durations=5",
        ]
        passed = True
        with console.status("[bold yellow]Executing test suite live...", spinner="dots"):
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if process.stdout is not None:
                for line in process.stdout:
                    line_str = line.strip()
                    if line_str:
                        if "PASSED" in line_str:
                            console.print(f"  [green]✔[/green] {line_str}")
                        elif "FAILED" in line_str or "ERROR" in line_str:
                            console.print(f"  [bold red]✖ {line_str}[/bold red]")
                            passed = False
                        else:                            console.print(f"    [dim]{line_str}[/dim]")
            process.wait()
            if process.returncode != 0:
                passed = False

        if passed:
            console.print("\n[bold green]✨ Engine Self-Test & Verification Passed Successfully![/bold green]")
        else:
            console.print("\n[bold red]❌ Test suite encountered errors or failures.[/bold red]")
            sys.exit(1)
        return

    target_file = args.target_file or (args.targets[0] if args.targets else None)

    # 5. Composer Mode (Multi-Step Recipe Execution)
    if args.recipe_goal:
        target_files = args.targets or ([args.target_file] if args.target_file else [])
        coordinator = ArchitectCoordinator(
            executor=executor,
            patcher=patcher,
            graph_linker=graph_linker,
            redis_store=redis_store,
            embedder=embedder,
            memory_pipeline=memory_pipeline,
            llm_client=llm_client,
            enable_searxng=not args.no_searxng,
            enable_upstream=not args.no_upstream,
        )
        console.print("[bold magenta]=^-.-^= Composer Coordinator Active[/bold magenta]")
        console.print(f"[cyan]Goal:[/cyan] {args.recipe_goal}")
        recipe = coordinator.create_recipe(goal=args.recipe_goal, target_files=target_files)
        if not recipe:
            console.print("[bold red]❌ Error: No valid target files could be identified or inferred for recipe.[/bold red]")
            sys.exit(1)

        console.print(f"[cyan]Resolved Targets:[/cyan] {', '.join([s.target_file for s in recipe])}\n")
        overall_success = True
        for step in recipe:
            success = coordinator.execute_step(step)
            if not success:
                console.print(f"[bold red]❌ Recipe halted at Step {step.step_id}: {step.target_file}[/bold red]")
                overall_success = False
                break

        if overall_success:
            console.print("\n[bold green]✨ Composer Recipe Executed Successfully![/bold green]")
        else:
            sys.exit(1)
        return

    # 6. Standard Single-File Synthesis Mode (-i / --input)
    if args.prompt:
        if not target_file:
            console.print(
                "[red]Error: Single-file edit mode (-i/--input) requires a target file "
                "via positional argument or -t/--targets.[/red]"
            )
            sys.exit(1)
        if not llm_client:
            console.print("[red]Error: LLM client could not be initialized in environment.[/red]")
            sys.exit(1)

        console.print(f"[bold green]=^-.-^= Synthesizing edits for {target_file}...[/bold green]")
        file_path = Path(target_file)
        original_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""

        system_prompt = (
            "CRITICAL: Output ONLY valid SEARCH and REPLACE blocks or code blocks. "
            "Never include conversational prose, preambles, or explanations."
        )
        user_prompt = f"Target File: {target_file}\nInstruction: {args.prompt}\n\nCurrent Content:\n{original_content}"

        raw_response = (
            llm_client.generate(system_prompt, user_prompt)
            if hasattr(llm_client, "generate")
            else llm_client.generate_stream(system_prompt, user_prompt)
        )

        frame = memory_pipeline.process_synthesis(
            instruction=args.prompt,
            raw_llm_response=raw_response,
            llm_client=llm_client,
            explicit_target=file_path,
            original_code=original_content,
        )

        blocks = patcher.parse_blocks(raw_response, fallback_filepath=target_file)
        applied_any = False
        for block in blocks:
            target = block.filepath or target_file
            r_block = block.replace_block if block.replace_block.strip() else block.search_anchor
            success = executor.apply_anchor_edit(
                filepath=target,
                search_anchor=block.search_anchor,
                replace_block=r_block,
            )
            if success:
                applied_any = True

        if applied_any and getattr(frame, "verification_passed", True):
            console.print(f"[bold green]✓ Applied changes and synchronized 3-tier memory (Redis, Vector, Neo4j) for {target_file}[/bold green]")
            if frame:
                render_thought_frame(frame, console=console)
        else:
            console.print(f"[bold red]❌ Synthesis or patching failed for {target_file}[/bold red]")
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
