"""Prompts module for generating low-token, anchor-based edit instructions tailored for local LLMs."""

from .qwen_diff import (
    QwenDiffPrompt,
    build_planner_user_prompt,
    build_user_prompt,
    get_edit_system_prompt,
    get_planner_system_prompt,
    get_system_prompt,
)

__all__ = [
    "QwenDiffPrompt",
    "get_system_prompt",
    "get_planner_system_prompt",
    "get_edit_system_prompt",
    "build_planner_user_prompt",
    "build_user_prompt",
]
