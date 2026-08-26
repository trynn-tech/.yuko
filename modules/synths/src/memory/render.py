#!/usr/bin/env python3
# src/memory/render.py

import json
import shutil
from typing import Any, Dict, Union, Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()

def render_thought_frame(frame: Union[Dict[str, Any], Any], console_out: Optional[Console] = None, header_title: Optional[str] = None) -> None:
    """Renders a ThoughtFrame to the console using Rich tables, panels, and syntax highlighting."""
    c = console_out or console
    if not frame:
        c.print("[bold yellow]⚠️ No matching ThoughtFrame found.[/bold yellow]")
        return

    columns, _ = shutil.get_terminal_size((80, 24))
    if header_title:
        c.print(f"\n[bold magenta]{header_title}[/bold magenta]")

    # Normalize frame into dictionary format
    if hasattr(frame, "model_dump"):
        data = frame.model_dump()
    elif hasattr(frame, "to_dict"):
        data = frame.to_dict()
    elif isinstance(frame, str):
        try:
            data = json.loads(frame)
        except json.JSONDecodeError:
            c.print(f"[bold red]Unable to parse raw frame payload:[/bold red]\n{frame}")
            return
    elif isinstance(frame, dict):
        data = frame
    else:
        data = getattr(frame, "__dict__", {})

    session_id = data.get("session_id", getattr(frame, "session_id", "N/A"))
    payload_type = data.get("payload_type", getattr(frame, "payload_type", "UNKNOWN"))
    
    target_file = (
        data.get("resolved_path")
        or data.get("target_file")
        or data.get("file_path")
        or getattr(frame, "resolved_path", None)
        or getattr(frame, "target_file", "N/A")
    )
    
    lang = (
        data.get("language")
        or getattr(frame, "language", None)
        or ("python" if str(target_file).endswith(".py") else "text")
    )

    verified = data.get("verification_passed", getattr(frame, "verification_passed", True))
    ver_status = "[bold green]PASS[/bold green]" if verified else "[bold red]FAIL[/bold red]"

    ast_facts = data.get("ast_facts", {})
    payload = data.get("payload", {})

    # Metadata Table
    meta_table = Table(show_header=False, box=None, padding=(0, 1))
    meta_table.add_column("Key", style="bold cyan")
    meta_table.add_column("Value", style="white")

    meta_table.add_row("Session ID:", str(session_id))
    meta_table.add_row("Payload Type:", str(payload_type))
    meta_table.add_row("Target File:", str(target_file))
    meta_table.add_row("Language:", str(lang))
    meta_table.add_row("Verification:", ver_status)

    summary = data.get("semantic_summary") or getattr(frame, "semantic_summary", None)
    if summary:
        meta_table.add_row("Summary:", f"[italic white]{summary}[/italic white]")

    tags = data.get("concept_tags") or getattr(frame, "concept_tags", [])
    if tags:
        meta_table.add_row("Concept Tags:", f"[yellow]{', '.join(tags)}[/yellow]")

    c.print(meta_table)

    # Instruction Panel
    instruction = data.get("instruction") or getattr(frame, "instruction", None)
    if instruction:
        c.print(
            Panel(
                instruction,
                title="[bold yellow]Instruction[/bold yellow]",
                border_style="yellow",
                expand=True,
            )
        )

    # Payload Specific Analysis
    if payload_type == "EDIT" or "lines_added" in payload:
        c.print("\n[bold magenta]📝 Edit Analysis:[/bold magenta]")
        lines_added = payload.get("lines_added", 0)
        lines_removed = payload.get("lines_removed", 0)
        symbols = ast_facts.get("symbols_modified", ast_facts.get("symbols", []))

        edit_table = Table(show_header=True, header_style="bold blue")
        edit_table.add_column("Lines Added")
        edit_table.add_column("Lines Removed")
        edit_table.add_column("AST Symbols")
        edit_table.add_row(
            f"[green]+{lines_added}[/green]",
            f"[red]-{lines_removed}[/red]",
            ", ".join(symbols) if symbols else "None",
        )
        c.print(edit_table)

    elif payload_type == "CREATE" or "created_content" in payload:
        c.print("\n[bold green]✨ File Creation Details:[/bold green]")
        create_table = Table(show_header=True, header_style="bold green")
        create_table.add_column("Total Lines")
        create_table.add_column("File Size (Bytes)")
        create_table.add_column("AST Symbols")
        create_table.add_row(
            str(payload.get("line_count", 0)),
            str(payload.get("byte_size", 0)),
            ", ".join(ast_facts.get("symbols", [])) or "None",
        )
        c.print(create_table)

    # Code Display (Fallback chain across payload variations)
    code_payload = (
        payload.get("updated_content")
        or payload.get("created_content")
        or data.get("extracted_code")
        or data.get("synthesized_code")
        or data.get("raw_response")
        or data.get("code")
    )

    if code_payload:
        clean_code = str(code_payload).strip()
        if clean_code.startswith("```"):
            lines = clean_code.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_code = "\n".join(lines).strip()

        syntax_lang = "python" if lang in ("text", "", None) else lang
        syntax = Syntax(
            clean_code[:2000],
            syntax_lang,
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        c.print(
            Panel(
                syntax,
                title=f"[bold green]Synthesized Code ({syntax_lang})[/bold green]",
                border_style="green",
                expand=True,
            )
        )

    c.print("-" * columns)
