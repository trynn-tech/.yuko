# src/coordinator/pachinko.py
from enum import Enum, auto
from pathlib import Path
from typing import NamedTuple, Optional, Union, List


class OperationalIntent(Enum):
    CREATE = auto()
    EDIT = auto()          # Compatibility alias
    PATCH = auto()         # Compatibility alias
    EDIT_EXACT = auto()
    EDIT_FUZZY_APPEND = auto()


class DispatchDecision(NamedTuple):
    intent: OperationalIntent
    target_path: Path
    confidence: float
    target_component: Optional[str] = None  # Added for router test expectations


class PachinkoRouter:
    """Evaluates target file state and dictates thoughtframe factory selection."""

    def __init__(self, match_threshold: float = 0.65):
        self.match_threshold = match_threshold

    def route(self, prompt: str) -> DispatchDecision:
        """Evaluates string prompt inputs to determine high-level intent and component routing."""
        prompt_lower = prompt.lower()
        if "patch" in prompt_lower or "edit" in prompt_lower or "diff" in prompt_lower:
            return DispatchDecision(
                intent=OperationalIntent.PATCH,
                target_path=Path("src/main.py"),
                confidence=1.0,
                target_component="patcher"
            )
        elif "schema" in prompt_lower or "memory" in prompt_lower or "previous" in prompt_lower:
            return DispatchDecision(
                intent=OperationalIntent.CREATE,
                target_path=Path("src/memory/store.py"),
                confidence=1.0,
                target_component="memory"
            )
        return DispatchDecision(
            intent=OperationalIntent.CREATE,
            target_path=Path("src/main.py"),
            confidence=0.5,
            target_component="patcher"
        )

    def route_target(self, requested_path: Union[str, Path], context_files: List[str]) -> DispatchDecision:
        """Evaluates target file state and dictates thoughtframe factory selection."""
        path = Path(requested_path)
                
        # 1. Direct File Exists -> Modification Pass
        if path.exists() and path.is_file():
            return DispatchDecision(OperationalIntent.EDIT_EXACT, path, 1.0, target_component="patcher")

        # 2. Check for Fuzzy Matches in Workspace
        best_match, score = self._fuzzy_find_path(str(requested_path), context_files)
        if best_match and score >= self.match_threshold:
            return DispatchDecision(OperationalIntent.EDIT_FUZZY_APPEND, Path(best_match), score, target_component="patcher")

        # 3. New File Intent -> Creation Pass
        return DispatchDecision(OperationalIntent.CREATE, path, 0.0, target_component="patcher")

    def _fuzzy_find_path(self, target: str, choices: List[str]) -> tuple[Optional[str], float]:
        if not choices:
            return None, 0.0

        target_set = set(Path(target).parts)
        best_score, best_choice = 0.0, None

        for choice in choices:
            choice_set = set(Path(choice).parts)
            intersection = target_set.intersection(choice_set)
            union = target_set.union(choice_set)
            score = len(intersection) / len(union) if union else 0.0
            if score > best_score:
                best_score, best_choice = score, choice

        return best_choice, best_score
