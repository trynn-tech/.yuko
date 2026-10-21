"""Engine subpackage for code context resolution, AST/grammar analysis,
patch generation, and local LLM execution.
"""

from .analyzer import CodeAnalysis, CodeAnalyzer
from .anchor_patch import AnchorPatcher, PatchBlock
from .context import FileContext, RepoContext
from .executor import Executor
from .llm import LocalInferenceEngine
from .intake import ScriptIntakeResult, ScriptStreamHandler

__all__ = [
    "AnchorPatcher",
    "CodeAnalysis",
    "CodeAnalyzer",
    "Executor",
    "FileContext",
    "LocalInferenceEngine",
    "PatchBlock",
    "RepoContext",
    "ScriptIntakeResult",
    "ScriptStreamHandler",
]
