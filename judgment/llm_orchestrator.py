"""
llm_orchestrator.py — LLM 编排层（从 router.py 提取）

职责：
- 快速响应函数（IntentRouter 旁路，无需 LLM）
- Profile 追问注入
- LLM 调用编排（同步包装）

被 router.py import 使用，保持 router.py 可测试性。
"""

from typing import Optional


def _inject_profile_questions(profile, task_text):
    """根据 agent_profile 注入个性化追问"""
    if not profile:
        return []
    extra = []
    name = profile.get("name", "")
    values = profile.get("values", [])
    biases = profile.get("biases", [])

    if name:
        extra.append(f"【{name}会怎么想这个问题？】")
    if biases:
        for b in biases:
            extra.append(f"【{name}容易在{b}上犯错，我有没有犯同样的错？】")
    if values:
        val_str = " > ".join(values[:3])
        extra.append(f"【{name}的价值排序是{val_str}，这个判断符合吗？】")

    return extra


# ──────────────────────────────────────────────
# P1 IntentRouter：快速响应函数（ZeusHammer LocalBrain 启发）
# ──────────────────────────────────────────────


def _quick_status_response(task_text):
    """STATUS_QUERY：直接返回状态，无需LLM调用"""
    try:
        from subsystems.judgment.judgment_db import get_recent_judgments
        recent = get_recent_judgments(limit=5) or []
        chains = [r for r in recent if isinstance(r, dict)]
        verdict_count = len(chains)
        confidence_avg = sum(r.get("confidence", 0) for r in chains) / max(len(chains), 1)
        verdict = f"判断系统正常运行。近期判断{verdict_count}次，平均置信度{confidence_avg:.0%}。"
    except Exception:
        verdict = "判断系统正常运行。"
    return {
        "task": task_text,
        "verdict": verdict,
        "confidence": 1.0,
        "dimensions": [],
        "intent": "status_query",
        "skipped_llm": True,
        "chain_id": None,
    }


def _quick_answer_response(task_text):
    """SHORT_ANSWER：简单问答，不走完整十维"""
    return {
        "task": task_text,
        "verdict": "这是一个简单问题，但我需要更多信息才能给出有价值的回答。请描述更多背景。",
        "confidence": 0.4,
        "dimensions": [],
        "intent": "short_answer",
        "skipped_llm": True,
        "chain_id": None,
    }


def _quick_confirm_response(task_text):
    """CONFIRM：确认类（是不是/要不要），走轻量路径"""
    return {
        "task": task_text,
        "verdict": "这是一个确认类问题，建议用更详细的描述来获取准确判断。请补充更多背景信息。",
        "confidence": 0.5,
        "dimensions": [],
        "intent": "confirm",
        "skipped_llm": True,
        "chain_id": None,
    }
