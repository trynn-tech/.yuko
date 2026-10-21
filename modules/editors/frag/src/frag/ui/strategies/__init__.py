"""src/frag/ui/strategies/__init__"""

from .navigation import DefaultNavigationStrategy
from .mutation import DefaultMutationStrategy
from .stage import StageStrategy
from .history import HistoryStrategy
from .command import CommandStrategy
from .search import SearchStrategy
from .workspace import WorkspaceStrategy

__all__ = [
    "DefaultNavigationStrategy",
    "DefaultMutationStrategy",
    "StageStrategy",
    "HistoryStrategy",
    "CommandStrategy",
    "SearchStrategy",
    "WorkspaceStrategy",
]
