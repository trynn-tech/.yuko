# src/coordinator/__init__.py
"""Coordinator subpackage for managing execution recipes, architecture strategy,
and state divergence handling.
"""

from .architect import ArchitectCoordinator, RecipeStep
from .divergence import DivergenceHandler
from .pachinko import DispatchDecision, OperationalIntent, PachinkoRouter

__all__ = [
    "ArchitectCoordinator",
    "DivergenceHandler",
    "DispatchDecision",
    "OperationalIntent",
    "PachinkoRouter",
    "RecipeStep",
]
