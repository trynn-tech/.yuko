"""Coordinator subpackage for managing execution recipes, architecture strategy,
and state divergence handling.
"""

from .architect import ArchitectCoordinator, RecipeStep
from .divergence import DivergenceHandler

__all__ = [
    "ArchitectCoordinator",
    "DivergenceHandler",
    "RecipeStep",
]
