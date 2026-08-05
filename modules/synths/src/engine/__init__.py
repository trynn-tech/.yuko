"""
Core parsing, execution, and repository context engines.
"""
from .anchor_patch import AnchorPatcher
from .context import RepoContext
from .executor import Executor
from .llm import LocalInferenceEngine

__all__ = ["AnchorPatcher", "RepoContext", "Executor", "LocalInferenceEngine"]
