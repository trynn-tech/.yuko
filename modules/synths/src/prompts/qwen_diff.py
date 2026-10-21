#!/usr/bin/env python3
# modules/synths/src/prompts/qwen_diff.py
from pathlib import Path
from typing import List, Optional, Tuple, Union
from engine.context import FileContext

# -------------------------------------------------------------------
# AST-Targeted Diff Synthesizer System Prompt (Action Space)
# -------------------------------------------------------------------
QWEN_EDIT_SYSTEM_PROMPT = """You are a deterministic code editing engine. Output ONLY structured symbol replacement directives.

STRICT FORMATTING RULES:
1. DO NOT wrap output in markdown backtick fences (e.g., DO NOT use ```python or ```).
2. All string literals containing backslashes (ASCII art, regex, shell paths) MUST use raw string notation r"..." or r'''...'''.
3. To modify a function, method, or class, specify the AST target symbol node:

TARGET_FILE: relative/path/to/file.ext
TARGET_SYMBOL: fn:process_stream
<<<<<<< REPLACE
[New Python implementation for process_stream]
>>>>>>> REPLACE

4. For NEW or EMPTY files, output full file blocks directly:
FILE: relative/path/to/file.ext
[Full file contents]"""

def get_edit_system_prompt() -> str:
    return QWEN_EDIT_SYSTEM_PROMPT


def build_user_prompt_ast_mode(
    user_query: str,
    file_contexts: List[FileContext],
    symbol_outline: str = "",
    plan: str = "",
) -> str:
    """Builds an AST-compact user prompt sending only structural outlines 
    instead of full target file buffers.
    """
    prompt_parts = []
    target_rel = file_contexts[0].relative_path if file_contexts else "target file"
    is_empty = not file_contexts or not file_contexts[0].exists or not file_contexts[0].content.strip()

    if is_empty:
        prompt_parts.append(
            f"### TASK:\nTarget `{target_rel}` is NEW/EMPTY. Output a complete file creation block starting with `FILE: {target_rel}`.\n"
            f"GOAL: {user_query}\n"
        )
    else:
        prompt_parts.append(f"### TARGET FILE AST MAP:\nFILE: {target_rel}\n")
        if symbol_outline:
            prompt_parts.append("--- SYMBOL OUTLINE ---")
            prompt_parts.append(symbol_outline)
            prompt_parts.append("--- OUTLINE END ---\n")

        if plan.strip():
            prompt_parts.append("<execution_plan>")
            prompt_parts.append(plan.strip())
            prompt_parts.append("</execution_plan>\n")

        prompt_parts.append(
            f"### TASK:\nConstruct a TARGET_SYMBOL replacement block targeting `{target_rel}` to achieve: {user_query}\n"
            "REMINDER: Specify `TARGET_SYMBOL: fn:<name>` or `TARGET_SYMBOL: class:<name>`. Do NOT repeat unmodified surrounding code."
        )

    return "\n".join(prompt_parts)
