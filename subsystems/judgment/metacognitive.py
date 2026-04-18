# metacognitive.py - #2 metacognitive self-awareness agent
from datetime import datetime as _dt

BIAS_CHECKLIST = [
    ("confirmation_bias", "我是否只找了支持自己观点的证据？"),
    ("availability_bias", "我是否被最近的例子过度影响？"),
    ("sunk_cost", "我是否因为已经投入而不愿改变？"),
    ("anchoring", "我是否过度依赖第一个信息？"),
    ("overconfidence", "我是否高估了自己的判断能力？"),
    ("status_quo", "我是否只是因为习惯了而选择维持现状？"),
    ("affect_heuristic", "情绪是否过度影响了我的判断？"),
    ("bandwagon", "我是否因为别人都这样做所以跟随？"),
]

def metacognitive_review(judgment_result: dict, task_text: str) -> dict:
    """
    Self-review agent: monitor own judgment process.
    Returns: {"flags": [...], "warnings": [...], "confidence_adjustment": float, "meta_verdict": str}
    """
    scores = judgment_result.get("scores", {})
    weights = judgment_result.get("weights", {})
    flags = []
    warnings = []

    overall = sum(scores.values()) / len(scores) if scores else 0.5
    score_variance = _variance(list(scores.values())) if scores else 0

    if overall > 0.8 and weights.get("d7_morality", 0.5) < 0.3:
        flags.append({"type": "overconfidence", "description": "High overall score but morality not considered"})
        warnings.append("Overall confidence may be inflated - re-examine assumptions")

    if score_variance > 0.15:
        flags.append({"type": "inconsistent", "description": "High variance across dimensions - check for bias"})
        warnings.append("Inconsistent scores may indicate selective attention")

    extreme_dims = [d for d, s in scores.items() if s < 0.2 or s > 0.9]
    if len(extreme_dims) > 3:
        flags.append({"type": "extremity_bias", "description": "Too many extreme scores - may be emotionally driven"})
        warnings.append("Multiple extreme scores suggest possible emotional override")

    if weights.get("d5_emotion", 0.5) > 0.6 and overall > 0.6:
        flags.append({"type": "affect_heuristic", "description": "High emotion weight + positive verdict - check if feeling is fact"})

    if not weights or sum(weights.values()) == 0:
        flags.append({"type": "no_weights", "description": "No dimension weights applied - using uniform weights"})
        warnings.append("Consider whether some dimensions are more relevant than others")

    confidence_adj = 0.0
    if flags:
        confidence_adj = -0.05 * len(flags)
    if warnings:
        confidence_adj -= 0.02 * len(warnings)

    meta_verdict = "HOLD" if len(flags) >= 3 or confidence_adj < -0.1 else \
                   "REVIEW" if flags else "PROCEED"

    return {
        "flags": flags,
        "warnings": warnings,
        "confidence_adjustment": round(confidence_adj, 3),
        "meta_verdict": meta_verdict,
        "flag_count": len(flags),
        "warning_count": len(warnings),
    }

def _variance(values):
    if not values:
        return 0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)

def get_bias_checklist():
    """Return the bias checklist for self-review"""
    return [{"id": b[0], "question": b[1]} for b in BIAS_CHECKLIST]

def metacognitive_self_check(task_text: str) -> dict:
    """
    Simple self-check: ask the metacognitive questions.
    Returns: {"biases_to_check": [...], "recommended_verdict": str}
    """
    return {
        "biases_to_check": BIAS_CHECKLIST,
        "recommended_verdict": "REVIEW",
        "self_check_questions": [
            "我最不确定的地方在哪里？",
            "如果我错了，可能是因为什么？",
            "别人会如何评估这个情况？",
            "我的情绪在多大程度上影响了判断？",
            "这个判断1个月后再看还站得住脚吗？",
        ],
    }

def format_meta_report(meta_result):
    lines = ["=== Metacognitive Self-Review ===", ""]
    verdict_icon = {"PROCEED": "GO", "REVIEW": "CHECK", "HOLD": "STOP"}.get(
        meta_result.get("meta_verdict", ""), "??")
    lines.append("Meta Verdict: [%s] (adjustment: %+.0f%%)" % (
        verdict_icon, meta_result.get("confidence_adjustment", 0) * 100))
    if meta_result.get("flags"):
        lines.append("")
        lines.append("Flags (%d):" % meta_result["flag_count"])
        for f in meta_result["flags"]:
            lines.append("  ! [%s] %s" % (f["type"], f["description"]))
    if meta_result.get("warnings"):
        lines.append("")
        lines.append("Warnings (%d):" % meta_result["warning_count"])
        for w in meta_result["warnings"]:
            lines.append("  ? %s" % w)
    return "\n".join(lines)
