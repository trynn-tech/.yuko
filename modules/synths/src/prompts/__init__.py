# modules/synths/src/prompts/__init__.py
"""
Prompts module for generating low-token, anchor-based edit instructions tailored for local LLMs.
"""
from .qwen_diff import build_user_prompt, get_system_prompt

__all__ = ["get_system_prompt", "build_user_prompt"]
