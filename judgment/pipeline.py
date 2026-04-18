# judgment/pipeline.py — check10d_full 入口
# Real implementation (NOT a shim — avoids circular import)
# The shim pattern caused: benchmark → subsystems/judgment/pipeline → judgment.router → judgment.__init__ → judgment.pipeline (shim) → subsystems.judgment.pipeline (not yet initialized)
# Fix: directly import from judgment.router (which is the actual router)
from typing import Dict, Optional


def check10d_full(task_text: str, agent_profile: Optional[Dict] = None, complexity: str = "auto") -> Dict:
    """
    完整判断流水线

    直接调用 judgment.router 中的核心函数。
    benchmark 用这个来跑所有案例。
    """
    # Import here to avoid any circular import risk
    from judgment.router import check10d, check10d_run

    try:
        result = check10d_run(task_text, agent_profile)
        if result is None:
            # fallback：直接用 check10d
            result = check10d(task_text, agent_profile, complexity)
        return result
    except Exception as e:
        # graceful degradation
        return {
            "task": task_text,
            "verdict": f"[Error: {e}]",
            "confidence": 0.0,
            "dimensions": [],
            "complexity": complexity,
        }
