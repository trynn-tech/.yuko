from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .app import ModularEditorTUI


class BaseEditorStrategy(ABC):
    """Abstract Strategy interface for TUI sub-modules."""

    def __init__(self, app: "ModularEditorTUI"):
        self.app = app

    @property
    def editor(self):
        return self.app.frag


class NavigationStrategy(BaseEditorStrategy):
    @abstractmethod
    def resolve_anchor(self, line_num: int) -> Optional[int]:
        pass

    @abstractmethod
    def select_block(self, block_idx: int) -> bool:
        pass


class MutationStrategy(BaseEditorStrategy):
    @abstractmethod
    def queue(self, op_type: str, target_id: int, content: str) -> None:
        pass

    @abstractmethod
    def apply(self) -> None:
        pass

    @abstractmethod
    def pop(self) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass
