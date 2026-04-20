# judgment/self_model/belief.py
from subsystems.judgment.closed_loop import get_dimension_beliefs

DIMS = [
    "cognitive", "game_theory", "economic", "dialectical",
    "emotional", "intuitive", "moral", "social", "temporal", "metacognitive",
]


def get_belief_status() -> dict:
    """
    返回各维度的置信度 belief 状态。
    CLI cmd_status 用的。
    """
    beliefs = get_dimension_beliefs()
    result = {}
    for dim in DIMS:
        if dim in beliefs:
            result[dim] = {"confidence": beliefs[dim].get("belief", 0.5)}
        else:
            result[dim] = {"confidence": 0.5}
    return result
