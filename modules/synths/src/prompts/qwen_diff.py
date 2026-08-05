#!/usr/bin/env python3
# modules/synths/src/prompts/qwen_diff.py

from typing import List, Optional
from engine.context import FileContext

# -------------------------------------------------------------------
# Mode 1: EDIT SYSTEM PROMPT (SEARCH / REPLACE)
# -------------------------------------------------------------------
QWEN_EDIT_SYSTEM_PROMPT = """You are a precise local code editing assistant.
Your task is to propose exact code edits using compact SEARCH/REPLACE blocks.

### OUTPUT FORMAT RULES:
FILE: relative/path/to/file.ext
<<<<<<< SEARCH
[Exact contiguous context lines from original file]
=======
[Replacement lines]
>>>>>>> REPLACE

CRITICAL RULES:
- Keep SEARCH blocks concise (2-5 lines).
- Match SEARCH text verbatim (including indentation).
- Output ONLY valid FILE blocks and concise explanations."""


def get_system_prompt(
    file_contexts: Optional[List[FileContext]] = None,
    is_edit_mode: Optional[bool] = None,
) -> str:
    """
    Selects system prompt based on context state or explicit mode override:
    - Edit Mode: Modifying existing files.
    - Creation Mode: Writing a new file from scratch.
    """
    # 1. Direct override pass from main.py dispatch
    if is_edit_mode is not None:
        if is_edit_mode:
            return QWEN_EDIT_SYSTEM_PROMPT
        
        target_path = None
        if file_contexts:
            new_targets = [ctx for ctx in file_contexts if not ctx.exists or not ctx.content.strip()]
            if new_targets:
                target_path = new_targets[0].relative_path
        return _create_prompt(target_file=target_path)

    # 2. Context inspection fallback
    if not file_contexts:
        return _create_prompt(target_file=None)

    new_targets = [ctx for ctx in file_contexts if not ctx.exists or not ctx.content.strip()]
    if new_targets:
        target_path = new_targets[0].relative_path
        return _create_prompt(target_file=target_path)

    return QWEN_EDIT_SYSTEM_PROMPT


def _create_prompt(target_file: Optional[str]) -> str:
    """Builds the file creation prompt using standard Markdown code fences."""
    if target_file and target_file not in [".", ""]:
        file_header_rule = f"FILE: {target_file}"
        path_guidance = f"The target file destination is strictly '{target_file}'."
    else:
        file_header_rule = "FILE: <path/to/new_file.ext>"
        path_guidance = "Choose a meaningful relative path based on the user instruction (e.g., `app/heartbeat.py`). Do NOT write literal text like 'relative/path/to/file.py'."

    return f"""You are a precise code generation assistant.
Your task is to write complete, working code for a newly requested file.

### OUTPUT FORMAT RULES:
{file_header_rule}
```<language_id>
[Full contents of the new file]

CRITICAL RULES:
{path_guidance}
Always start directly with 'FILE: ' followed by the code block.
Wrap the file content inside standard Markdown code fences (<language_id> ... ).
Do NOT use SEARCH/REPLACE blocks for file creation."""

def build_user_prompt(user_query: str, file_contexts: List[FileContext]) -> str:
    """Assembles user prompt context using RepoContext FileContext objects."""
    prompt_parts = []
    if file_contexts:
        prompt_parts.append("### REPOSITORY CONTEXT:\n")
        for ctx in file_contexts:
            prompt_parts.append(f"FILE: {ctx.relative_path}")
            if ctx.exists and ctx.content:
                prompt_parts.append("```")
                prompt_parts.append(ctx.content)
                prompt_parts.append("```\n")
            else:
                prompt_parts.append(
                    "[STATUS: Target file does not exist yet - pending creation]\n"
                )

    prompt_parts.append(f"### USER INSTRUCTION:\n{user_query}")
    return "\n".join(prompt_parts)
