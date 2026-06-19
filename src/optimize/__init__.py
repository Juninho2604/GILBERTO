"""Optimización de mezclas (Fase 2 del brief)."""

from .optimizer import (
    BlendPlan,
    OptimizeResult,
    marginal_values,
    optimize_blend,
)

__all__ = [
    "BlendPlan",
    "OptimizeResult",
    "marginal_values",
    "optimize_blend",
]
