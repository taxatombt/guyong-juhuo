# judgment/self_model/__init__.py
from subsystems.judgment.closed_loop import get_dimension_beliefs

DIMS = [
    "cognitive", "game_theory", "economic", "dialectical",
    "emotional", "intuitive", "moral", "social", "temporal", "metacognitive",
]

from .belief import get_belief_status

__all__ = ["get_belief_status", "DIMS", "get_dimension_beliefs"]
