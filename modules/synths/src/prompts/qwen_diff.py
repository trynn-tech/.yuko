#!/usr/bin/env python3
# modules/synths/src/prompts/qwen_diff.py

from pathlib import Path
from typing import List, Optional, Tuple, Union

from engine.context import FileContext

# -------------------------------------------------------------------
# Phase 1: Planner Prompt (Reasoning Space)
# -------------------------------------------------------------------
QWEN_PLANNER_SYSTEM_PROMPT = """You are an expert systems software architect.
Analyze the instruction and how best to implement the instruction given the file. Formulate a concise execution plan for the code edits.

Rules:
1. If modifying an existing file, identify verbatim SEARCH anchors.
2. If creating a new file or writing to an empty file, outline the complete module structure."""

# -------------------------------------------------------------------
# Phase 2: Diff Synthesizer Prompt (Action Space)
# -------------------------------------------------------------------
QWEN_EDIT_SYSTEM_PROMPT = """You are a deterministic code editing engine. Output ONLY valid edit blocks.

STRICT FORMATTING RULES:
1. DO NOT wrap output in markdown backtick fences (e.g. DO NOT use ```python or ```).
2. For EXISTING files, use SEARCH/REPLACE blocks with exact contiguous SEARCH anchors:
FILE: relative/path/to/file.ext
<<<<<<< SEARCH
[Exact contiguous lines from target file]
=======
[Replacement lines]
>>>>>>> REPLACE

3. For NEW or EMPTY files, output full file creation blocks directly:
FILE: relative/path/to/file.ext
[Full file contents]
"""


def get_planner_system_prompt() -> str:
    return QWEN_PLANNER_SYSTEM_PROMPT


def get_edit_system_prompt() -> str:
    return QWEN_EDIT_SYSTEM_PROMPT


get_system_prompt = get_edit_system_prompt


def build_planner_user_prompt(
    user_query: str, file_contexts: List[FileContext]
) -> str:
    prompt_parts = []
    if file_contexts:
        prompt_parts.append("### TARGET FILE CONTENT:\n")
        for ctx in file_contexts:
            prompt_parts.append(f"FILE: {ctx.relative_path}")
            if ctx.exists and ctx.content:
                prompt_parts.append("--- SOURCE START ---")
                prompt_parts.append(ctx.content)
                prompt_parts.append("--- SOURCE END ---\n")
            else:
                prompt_parts.append("[FILE IS CURRENTLY NEW / EMPTY]\n")

    prompt_parts.append(f"### GOAL:\n{user_query}")
    return "\n".join(prompt_parts)


def build_user_prompt(
    user_query: str,
    file_contexts: List[FileContext],
    plan: str = "",
) -> str:
    prompt_parts = []
    target_rel = file_contexts[0].relative_path if file_contexts else "target file"
    is_empty = not file_contexts or not file_contexts[0].exists or not file_contexts[0].content.strip()

    if file_contexts:
        prompt_parts.append("### TARGET FILE CONTENT:\n")
        for ctx in file_contexts:
            prompt_parts.append(f"FILE: {ctx.relative_path}")
            if ctx.exists and ctx.content:
                prompt_parts.append("--- SOURCE START ---")
                prompt_parts.append(ctx.content)
                prompt_parts.append("--- SOURCE END ---\n")
            else:
                prompt_parts.append("[FILE IS CURRENTLY NEW / EMPTY]\n")

    if plan.strip():
        prompt_parts.append("<execution_plan>")
        prompt_parts.append(plan.strip())
        prompt_parts.append("</execution_plan>\n")

    if is_empty:
        prompt_parts.append(
            f"### TASK:\nTarget `{target_rel}` is NEW/EMPTY. Output a complete file creation block starting with `FILE: {target_rel}` followed immediately by the complete implementation code for: {user_query}\n"
            "REMINDER: Do NOT use search anchors for empty files. Do NOT use markdown code fences."
        )
    else:
        prompt_parts.append(
            f"### TASK:\nConstruct a valid SEARCH/REPLACE block targeting `{target_rel}` to achieve: {user_query}\n"
            "REMINDER: Copy exact contiguous lines from SOURCE START/END into <<<<<<< SEARCH verbatim. Do NOT use markdown code fences."
        )

    return "\n".join(prompt_parts)


class QwenDiffPrompt:
    @staticmethod
    def build_planner_prompts(
        filepath: str,
        content: str,
        instruction: str,
        repo_context: Union[str, List[FileContext]] = "",
    ) -> Tuple[str, str]:
        target_path = Path(filepath)
        file_ctx = FileContext(
            path=target_path,
            relative_path=filepath,
            content=content,
            exists=target_path.exists(),
        )
        sys_prompt = get_planner_system_prompt()
        usr_prompt = build_planner_user_prompt(instruction, [file_ctx])

        if isinstance(repo_context, str) and repo_context.strip():
            usr_prompt = f"{repo_context}\n\n{usr_prompt}"

        return sys_prompt, usr_prompt

    @staticmethod
    def build_prompts(
        filepath: str,
        content: str,
        instruction: str,
        plan: str = "",
        repo_context: Union[str, List[FileContext]] = "",
    ) -> Tuple[str, str]:
        target_path = Path(filepath)
        file_ctx = FileContext(
            path=target_path,
            relative_path=filepath,
            content=content,
            exists=target_path.exists(),
        )
        sys_prompt = get_edit_system_prompt()
        usr_prompt = build_user_prompt(instruction, [file_ctx], plan=plan)

        if isinstance(repo_context, str) and repo_context.strip():
            usr_prompt = f"{repo_context}\n\n{usr_prompt}"

        return sys_prompt, usr_prompt
