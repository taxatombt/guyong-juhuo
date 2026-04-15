# outcome_tracker.py - #5 post-outcome tracking闭环
import json as _j, uuid as _u
from pathlib import Path
from datetime import datetime as _dt, timedelta as _td
DATA_DIR = Path(__file__).parent / "data"
OUTCOMES_FILE = DATA_DIR / "outcomes.jsonl"

def _e():
    DATA_DIR.mkdir(exist_ok=True)

def _l():
    _e()
    if not OUTCOMES_FILE.exists():
        return []
    with open(OUTCOMES_FILE, encoding="utf-8") as f:
        return [_j.loads(l) for l in f if l.strip()]

def _s(r):
    _e()
    with open(OUTCOMES_FILE, "w", encoding="utf-8") as f:
        for o in r:
            f.write(_j.dumps(o, ensure_ascii=False) + "\n")

def start_tracking(task_text, initial_verdict, initial_reason, initial_scores=None, follow_up_days=7, tags=None):
    _e()
    outcomes = _l()
    record_id = str(_u.uuid4())[:8]
    outcomes.append({"record_id": record_id, "task_text": task_text, "initial_verdict": initial_verdict, "initial_reason": initial_reason, "initial_scores": initial_scores or {}, "created_at": _dt.now().isoformat(), "outcome": None, "outcome_recorded_at": None, "follow_up_days": follow_up_days, "tags": tags or [], "resolved": False, "lessons": []})
    _s(outcomes)
    return record_id

def record_outcome(record_id, outcome_type, outcome_data, lessons=None):
    outcomes = _l()
    for o in outcomes:
        if o.get("record_id") == record_id:
            o["outcome"] = {"type": outcome_type, "data": outcome_data, "recorded_at": _dt.now().isoformat()}
            o["outcome_recorded_at"] = _dt.now().isoformat()
            o["resolved"] = True
            if lessons:
                o["lessons"] = lessons
            break
    _s(outcomes)
    return outcome_type

def get_unresolved(days=30):
    outcomes = _l()
    cutoff = _dt.now() - _td(days=days)
    return [o for o in outcomes if not o.get("resolved") and _dt.fromisoformat(o["created_at"]) >= cutoff if o.get("created_at")]

def get_accuracy_report(days=90):
    outcomes = _l()
    cutoff = _dt.now() - _td(days=days)
    recent = [o for o in outcomes if o.get("created_at") and _dt.fromisoformat(o["created_at"]) >= cutoff]
    if not recent:
        return {"total": 0, "accuracy": None, "avg_score": None, "by_type": {}, "recent_outcomes": [], "message": "No data"}
    total = len(recent)
    resolved = [o for o in recent if o.get("resolved")]
    correct = sum(1 for o in resolved if o.get("outcome", {}).get("type") == "SUCCESS")
    scores = [o.get("outcome", {}).get("data", {}).get("score", 0.5) for o in resolved if o.get("outcome")]
    accuracy = correct / total if total > 0 else 0.0
    avg_score = sum(scores) / len(scores) if scores else 0.0
    by_type = {}
    for o in resolved:
        t = o.get("outcome", {}).get("type", "?")
        by_type.setdefault(t, {"count": 0, "total": 0.0})
        by_type[t]["count"] += 1
        by_type[t]["total"] += o.get("outcome", {}).get("data", {}).get("score", 0.5)
    for k in by_type:
        by_type[k]["avg"] = round(by_type[k]["total"] / by_type[k]["count"], 2)
    return {"total": total, "resolved": len(resolved), "unresolved": total - len(resolved), "accuracy": round(accuracy, 3), "avg_score": round(avg_score, 3), "by_type": {k: {"count": v["count"], "avg": v["avg"]} for k, v in by_type.items()}, "recent_outcomes": [{"record_id": o.get("record_id"), "task": o.get("task_text", "")[:50], "initial_verdict": o.get("initial_verdict"), "outcome_type": o.get("outcome", {}).get("type"), "created_at": o.get("created_at", "")[:10]} for o in recent[-10:]]}

def format_accuracy_report(report):
    lines = ["=== Outcome Accuracy Report ===", ""]
    lines.append("Total: %d | Resolved: %d | Unresolved: %d" % (report["total"], report["resolved"], report["unresolved"]))
    if report.get("accuracy") is not None:
        lines.append("Accuracy: %d%% | Avg Score: %.2f" % (int(report["accuracy"] * 100), report["avg_score"]))
    else:
        lines.append("No data yet")
    for k, v in report.get("by_type", {}).items():
        lines.append("  %s: %d times (avg %.0f%%)" % (k, v["count"], v["avg"] * 100))
    for o in report.get("recent_outcomes", []):
        ot = o.get("outcome_type") or "??"
        lines.append("  [%s] %s => %s (%s)" % (o.get("initial_verdict", "")[:8], o.get("task", ""), ot, o.get("created_at", "")))
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# 反馈回路集成（聚活项目设计）
# record_outcome 后自动更新维度权重
# ─────────────────────────────────────────────────────────────────

def _import_dynamic():
    try:
        from dynamic_weights import update_weights_from_outcome as _uwfo
        return _uwfo
    except ImportError:
        try:
            from dynamic_weights import update_weights_from_outcome as _uwfo
            return _uwfo
        except ImportError:
            return None


def record_outcome_with_feedback(record_id, outcome_type, outcome_data, dims_checked=None, lessons=None):
    """
    增强?record_outcome：同时触发权重更新?

    参数?
        record_id: start_tracking 返回的记录ID
        outcome_type: "SUCCESS" | "FAILURE" | "NEUTRAL"
        outcome_data: 额外结果数据
        dims_checked: 本次决策参与了的维度列表
        lessons: 从本次决策中学到的教?
    """
    record_outcome(record_id, outcome_type, outcome_data, lessons)

    if dims_checked:
        outcomes = _l()
        record = next((o for o in outcomes if o.get("record_id") == record_id), None)
        if record:
            task_text = record.get("task_text", "")
            outcome_map = {"SUCCESS": "good", "FAILURE": "bad", "NEUTRAL": "neutral"}
            feedback_outcome = outcome_map.get(outcome_type, "neutral")
            uwfo = _import_dynamic()
            if uwfo:
                try:
                    uwfo(task_text, dims_checked, feedback_outcome)
                except Exception:
                    pass

    return outcome_type

# ── Auto闭环接口 ─────────────────────────────────────────────────────
# 写入 verdict_signal，供 closed_loop.verdict_listener 自动消费
# 格式：{task_text, outcome, chain_id, verdict_recorded=False}

def record_judgment_outcome(chain_id, task_text, outcome):
    """
    记录判断结果到 outcomes.jsonl，触发 auto闭环监听器。
    outcome: True(正确) / False(错误) / 1.0/0.0
    """  
    _e()
    outcomes=_l()
    correct_bool=bool(outcome) if isinstance(outcome,bool) else (float(outcome)>0.5)
    record={
        "record_id": chain_id,
        "task_text": task_text,
        "outcome": correct_bool,
        "chain_id": chain_id,
        "verdict_recorded": False,
        "created_at": _dt.now().isoformat(),
        "resolved": True,
    }
    # 避免重复 chain_id
    outcomes=[o for o in outcomes if o.get("chain_id")!=chain_id]
    outcomes.append(record)
    _s(outcomes)
    return correct_bool
