# -*- coding: utf-8 -*-
"""
judgment/perception.py — 感知层
===============================
给 Hermes（或其他 channel）用的感知接口。
不依赖复杂感知子系统，只做一件事：
从用户自然语言中识别决策场景，触发 feedback 收集。

用户感知：极简（系统自动识别，无需手动开启）
后台逻辑：intent_router 模式匹配 + 因果记忆记录
"""

from typing import Optional, Dict, Any, List
from .intent_router import IntentRouter, IntentType

# ── 感知层单例 ────────────────────────────────────────────
_intent_router: Optional[IntentRouter] = None

def _get_router() -> IntentRouter:
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouter()
    return _intent_router


# ── 决策识别 API ───────────────────────────────────────────

def is_decision(text: str) -> bool:
    """
    判断一段文本是否包含决策意图。
    被 Hermes 等 channel 调用，在对话中自动识别决策场景。

    Returns:
        True = 是决策场景，应该触发 feedback 收集
    """
    if not text or len(text.strip()) < 3:
        return False
    intent = _get_router().route(text.strip())
    return intent in {
        IntentType.CAREER_JUDGE,
        IntentType.INVEST_JUDGE,
        IntentType.RELATION_JUDGE,
        IntentType.LIFE_OS_JUDGE,
        IntentType.COMPLEX_JUDGE,
    }


def detect_decision(text: str) -> Dict[str, Any]:
    """
    完整感知结果。
    Hermes 调用此函数，获取感知决策场景的完整信息。

    Returns:
        {
            "is_decision": bool,
            "type": str,          # career/invest/relation/life_os/complex/unknown
            "confidence": float,  # 0.0~1.0
            "suggestion": str,    # 建议采取的行动
        }
    """
    if not text or len(text.strip()) < 3:
        return {"is_decision": False, "type": "unknown", "confidence": 0.0, "suggestion": ""}

    intent = _get_router().route(text.strip())

    INTENT_LABELS = {
        IntentType.CAREER_JUDGE: "career",
        IntentType.INVEST_JUDGE: "invest",
        IntentType.RELATION_JUDGE: "relation",
        IntentType.LIFE_OS_JUDGE: "life_os",
        IntentType.COMPLEX_JUDGE: "complex",
    }

    is_judge = intent in INTENT_LABELS

    suggestions = {
        IntentType.CAREER_JUDGE: "记录这个职业决策，系统会跟踪结果并学习你的判断模式",
        IntentType.INVEST_JUDGE: "记录这个投资决策，系统会帮你跟踪结果并优化风险判断",
        IntentType.RELATION_JUDGE: "记录这个人际决策，系统会学习你在关系中的判断倾向",
        IntentType.LIFE_OS_JUDGE: "记录这个日常决策，积累数据后系统能给你更准的建议",
        IntentType.COMPLEX_JUDGE: "记录这个复杂决策，系统会从多维度分析你的判断",
    }

    return {
        "is_decision": is_judge,
        "type": INTENT_LABELS.get(intent, "unknown"),
        "confidence": 1.0 if is_judge else 0.0,
        "suggestion": suggestions.get(intent, ""),
    }


# ── 决策上下文记录 API ────────────────────────────────────

def record_decision_context(
    text: str,
    user_id: str = "default",
    channel: str = "hermes",
) -> Optional[str]:
    """
    记录一个决策场景到因果记忆。
    被 Hermes 在识别到决策意图后调用（用户同意时）。

    Returns:
        chain_id: 用于后续关联 verdict
    """
    from .closed_loop import snapshot_judgment
    import uuid

    chain_id = f"hermes_{channel}_{uuid.uuid4().hex[:12]}"

    try:
        snapshot_judgment(
            chain_id=chain_id,
            task_text=text,
            dimensions=["cognitive", "game_theory", "economic",
                        "dialectical", "emotional", "intuitive",
                        "moral", "social", "temporal", "metacognitive"],
            weights={},
            result={"answers": {}, "emotion": {}, "curiosity": {}},
            complexity="perception",
            user_id=user_id,
        )
    except Exception:
        pass

    return chain_id


def record_outcome(
    chain_id: str,
    correct: bool,
    outcome_score: Optional[float] = None,
    notes: str = "",
    user_id: str = "default",
) -> Dict[str, Any]:
    """
    记录决策结果，触发 beliefs 更新。
    用户告知结果后调用。

    Returns:
        {"updated": bool, "chain_id": str, "changes": dict}
    """
    from .closed_loop import receive_verdict

    try:
        return receive_verdict(
            chain_id=chain_id,
            correct=correct,
            outcome_score=outcome_score,
            notes=notes,
            user_id=user_id,
        )
    except Exception as e:
        return {"updated": False, "chain_id": chain_id, "error": str(e)}


# ── 进化阶段 API ──────────────────────────────────────────

# 进化阶段门槛（常量）
EVOLUTION_STAGES = {
    "learning": {
        "min_decisions": 0,
        "max_decisions": 50,
        "description": "学习期 — 被动记录，不主动建议",
        "can_predict": False,
        "can_recommend": False,
    },
    "simulation": {
        "min_decisions": 50,
        "max_decisions": 200,
        "description": "模拟期 — 开始预测你的选择，标记 verdicts 准确率",
        "can_predict": True,
        "can_recommend": False,
    },
    "transcendence": {
        "min_decisions": 200,
        "max_decisions": float("inf"),
        "description": "超越期 — 预测准确率 > 85%，主动给出建议",
        "can_predict": True,
        "can_recommend": True,
    },
}

# 超越期置信度门槛
TRANSCENDENCE_ACCURACY_THRESHOLD = 0.85


def get_evolution_stage(user_id: str = "default") -> Dict[str, Any]:
    """
    返回当前用户处于哪个进化阶段。
    基于 verdict 记录数量判断。
    """
    from .closed_loop import _get_db_conn

    c = _get_db_conn()
    # 统计有 verdict 的决策数量
    n = c.execute(
        "SELECT COUNT(*) FROM verdict_outcomes WHERE user_id=?",
        (user_id,)
    ).fetchone()[0]

    for stage_id, info in EVOLUTION_STAGES.items():
        if info["min_decisions"] <= n < info["max_decisions"]:
            return {
                "stage": stage_id,
                "decision_count": n,
                "next_stage": _next_stage(stage_id),
                "decisions_to_next": info["max_decisions"] - n if info["max_decisions"] != float("inf") else None,
                **info,
            }
    return {
        "stage": "transcendence",
        "decision_count": n,
        "next_stage": None,
        "decisions_to_next": None,
        **EVOLUTION_STAGES["transcendence"],
    }


def _next_stage(current: str) -> Optional[str]:
    order = ["learning", "simulation", "transcendence"]
    try:
        idx = order.index(current)
        return order[idx + 1] if idx + 1 < len(order) else None
    except ValueError:
        return None


def can_recommend(user_id: str = "default") -> bool:
    """当前是否已达到主动建议阶段"""
    stage = get_evolution_stage(user_id)
    return stage.get("can_recommend", False)
