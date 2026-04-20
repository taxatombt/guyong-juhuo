# judgment/pipeline.py — check10d_full 入口
# Phase 5: 直接 import from judgment.router，避免循环
from dataclasses import dataclass, field
from typing import Dict, Optional, List


@dataclass
class PipelineConfig:
    """check10d_full 的配置选项"""
    agent_profile_name: Optional[str] = None
    enable_adversarial: bool = False
    enable_qiushi: bool = False
    enable_embedding: bool = False
    enable_lessons: bool = False
    confidence_threshold: float = 0.5
    emotion_state: Optional[Dict[str, float]] = None  # PAD: {P, A, D}


def check10d_full(
    task_text: str,
    agent_profile: Optional[Dict] = None,
    complexity: str = "auto",
    config: Optional[PipelineConfig] = None,
) -> Dict:
    """
    完整判断流水线

    直接调用 judgment.router 中的核心函数。
    benchmark 用这个来跑所有案例。
    """
    from judgment.router import check10d, check10d_run

    # 从 config 提取参数
    emotion_state = None
    if config is not None:
        if config.emotion_state:
            emotion_state = config.emotion_state
        if config.agent_profile_name and agent_profile is None:
            agent_profile = {"name": config.agent_profile_name}

    try:
        result = check10d_run(task_text, agent_profile, emotion_state=emotion_state)
        if result is None:
            result = check10d(task_text, agent_profile, complexity)
        return result
    except Exception as e:
        return {
            "task": task_text,
            "verdict": f"[Error: {e}]",
            "confidence": 0.0,
            "dimensions": [],
            "complexity": complexity,
        }


def format_full_report(result: Dict) -> str:
    """格式化完整报告"""
    lines = []
    lines.append(f"=== Judgment Report: {result.get('task', '')} ===")
    verdict = result.get("verdict", "N/A")
    confidence = result.get("confidence", 0.0)
    lines.append(f"Verdict: {verdict}")
    lines.append(f"Confidence: {confidence:.2f}")

    dims = result.get("dimensions", [])
    for dim in dims:
        name = dim.get("name", dim.get("dimension", "?"))
        score = dim.get("score", dim.get("value", 0.0))
        reason = dim.get("reason", dim.get("notes", ""))
        bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
        lines.append(f"  {name:<18} {bar} {score:.2f}")
        if reason:
            lines.append(f"    {reason[:60]}")

    meta = result.get("meta", {})
    if meta:
        lines.append(f"\nComplexity: {meta.get('complexity', 'N/A')}")
        skipped = meta.get("skipped", [])
        if skipped:
            lines.append(f"Skipped: {', '.join(skipped)}")

    return "\n".join(lines)
