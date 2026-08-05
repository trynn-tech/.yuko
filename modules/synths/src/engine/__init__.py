"""
Core parsing, execution, working memory, and repository context engines.
"""
from .analyzer import CodeAnalyzer
from .anchor_patch import AnchorPatcher
from .context import RepoContext
from .executor import Executor
from .llm import LocalInferenceEngine
from .working_memory import ThoughtFrame, WorkingMemoryPipeline

__all__ = [
    "AnchorPatcher",
    "CodeAnalyzer",
    "Executor",
    "LocalInferenceEngine",
    "RepoContext",
    "ThoughtFrame",
    "WorkingMemoryPipeline",
]
