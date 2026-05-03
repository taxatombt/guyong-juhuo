# judgment/verdict_collector.py — Shim
# 真实实现在 subsystems/judgment/closed_loop.py 和 judgment_db.py
from subsystems.judgment.judgment_db import (
    get_overall_accuracy,
    get_verdict_history,
)
from subsystems.judgment.closed_loop import receive_verdict
from judgment.lessons import extract_and_save_from_case

import json
from pathlib import Path

DB_PATH = r"E:\juhuo\data\juhuo.db"

_DATA_DIR = Path(__file__).parent.parent / "data" / "judgment_data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_verdict_stats() -> dict:
    """CLI 用的 verdict 统计"""
    history = get_verdict_history(limit=9999)
    verdicts = [r for r in history if r.get("verdict")]
    correct = sum(1 for r in verdicts if r.get("correct") == 1)
    return {
        "total": len(verdicts),
        "correct": correct,
        "wrong": len(verdicts) - correct,
        "accuracy": get_overall_accuracy(),
    }


def _update_experience_quality(chain_id: str, correct: bool, user_id: str) -> dict:
    """根据 verdict correct/wrong 更新 experiences.quality_score"""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 找 task_text
    c.execute("SELECT task_text FROM judgment_snapshots WHERE chain_id=?", (chain_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"ok": False, "reason": "chain_id not found"}
    task_text = (row[0] or "")[:300]

    # 找对应 experience
    c.execute(
        "SELECT id, quality_score FROM experiences "
        "WHERE task_text=? AND user_id=? AND (actual_action IS NULL OR actual_action='') "
        "ORDER BY created_at DESC LIMIT 1",
        (task_text, user_id))
    exp = c.fetchone()
    if not exp:
        conn.close()
        return {"ok": False, "reason": "no matching experience"}

    old_qs = exp[1] if exp[1] is not None else 50.0
    # correct=True → +15；correct=False → -20（错误代价更高）
    delta = 15.0 if correct else -20.0
    new_qs = max(0.0, min(100.0, (old_qs or 50.0) + delta))
    c.execute("UPDATE experiences SET quality_score=?, updated_at=datetime('now') WHERE id=?", (new_qs, exp[0]))
    conn.commit()
    conn.close()
    return {"ok": True, "old_qs": old_qs, "new_qs": new_qs, "delta": delta}


def mark_verdict_correct(chain_id: str, notes: str = "", user_id: str = "default") -> bool:
    """标记某条判断为正确（同时更新 experiences.quality_score）"""
    # 更新 quality_score
    qs_result = _update_experience_quality(chain_id, correct=True, user_id=user_id)
    # 触发 belief 更新
    ok = receive_verdict(chain_id=chain_id, correct=True, notes=notes, user_id=user_id)
    return ok


def mark_verdict_wrong(chain_id: str, notes: str = "", user_id: str = "default") -> bool:
    """标记某条判断为错误（同时更新 experiences.quality_score）"""
    # 更新 quality_score
    qs_result = _update_experience_quality(chain_id, correct=False, user_id=user_id)
    # 触发 belief 更新
    ok = receive_verdict(chain_id=chain_id, correct=False, notes=notes, user_id=user_id)
    return ok


def remove_verdict(chain_id: str) -> bool:
    """删除 verdict 记录（清除 outcome_auto = NULL）"""
    from subsystems.judgment.judgment_db import _get_db_conn
    conn = _get_db_conn()
    try:
        conn.execute("UPDATE judgment_snapshots SET outcome_auto=NULL,corrected=0 WHERE chain_id=?", (chain_id,))
        conn.execute("DELETE FROM verdict_outcomes WHERE chain_id=?", (chain_id,))
        conn.commit()
        return True
    except Exception:
        return False


# ── 以下为 verdict_collector 原有接口的空壳（CLI 不直接用）─────────────────
def VerdictRecord(*args, **kwargs):
    from dataclasses import dataclass, field
    @dataclass
    class VR:
        chain_id: str = ""
        task: str = ""
        verdict: str = ""
        correct: bool = False
        notes: str = ""
    return VR(*args, **kwargs)


def auto_collect(*args, **kwargs): pass
def count_verdicts(*args, **kwargs): return get_verdict_stats()["total"]
def ensure_dir(*args, **kwargs): pass
def get_collection_status(*args, **kwargs): return {"status": "ok"}
def import_from_chats(*args, **kwargs): pass
def import_from_jsonl(*args, **kwargs): pass
def import_from_judgment_db(*args, **kwargs): pass
def is_ready_for_evolution(*args, **kwargs): return True
def load_verdicts(*args, **kwargs): return []
def run_full_collection(*args, **kwargs): pass
def save_verdict(*args, **kwargs): pass



def receive_actual_choice(chain_id, actual_action, user_id: str = "default"):
    """用户决策后调用：写入 verdict_outcomes + 更新 judgment_snapshots.outcome_score"""
    import sqlite3, re
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT task_text, verdict, predicted_action, prediction_confidence, dimensions FROM judgment_snapshots WHERE chain_id=?",
        (chain_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "Chain not found"}
    task_text, verdict, predicted_action, prediction_confidence, dimensions_json = row
    predicted_action = (predicted_action or "").strip()
    def norm(s):
        _p = r"[\s，。！？；：\u201c\u201d\u2018\u2019\u300c\u300d\u300e\u300f\u2014\u2026\u00a0-\u00ff]+"
        return re.sub(_p, "", s or "").lower()
    np_ = norm(predicted_action)
    na_ = norm(actual_action or "")
    hit = bool(
        np_ and na_ and (
            np_ in na_ or na_ in np_ or
            (len(set(np_) & set(na_)) / max(len(set(np_)), len(set(na_))) >= 0.5
            if np_ and na_ else False)))
    score = 1.0 if hit else 0.0

    # 因果链教训提取（从判断结果自动生成教训）
    dims_list = []
    if dimensions_json:
        try:
            dims_list = json.loads(dimensions_json)
        except Exception:
            pass
    lesson_ids = []
    try:
        lesson_ids = extract_and_save_from_case(
            task_text=task_text or "",
            verdict=verdict or "",
            predicted_action=predicted_action,
            actual_action=actual_action,
            outcome_score=score,
            dimensions=dims_list,
            chain_id=chain_id,
            user_id=user_id,
        )
    except Exception as _e:
        import sys; print(f"extract_and_save_from_case failed: {_e}", file=sys.stderr)

    try:
        c.execute(
            "INSERT INTO verdict_outcomes (chain_id, task_text, correct, predicted_action, actual_action, outcome_score, notes, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (chain_id, (task_text or "")[:300], 1 if hit else 0,
             predicted_action[:200], (actual_action or "")[:200], score, "actual_choice", user_id))
    except Exception as ex:
        print(f"verdict_outcomes insert error: {ex}")
    c.execute("UPDATE judgment_snapshots SET outcome_score=? WHERE chain_id=?",
              (score, chain_id))
    c.execute(
        "UPDATE experiences SET actual_action=?, outcome_score=?, updated_at=datetime('now') "
        "WHERE task_text=? AND (actual_action IS NULL OR actual_action='') AND user_id=?",
        ((actual_action or "")[:200], score, (task_text or "")[:300], user_id))
    n_exp = c.rowcount
    conn.commit()
    conn.close()

    # ── 4. Update quality_score for matched experiences ─────────────────────
    if n_exp > 0 and score is not None:
        # ZeusHammer SkillLearner: quality_score = outcome_delta(±30) + verified_delta(+15) + consistency_delta(±5)
        # Base = 50, outcome_score 1.0→+30, 0.0→-30, verified(+actual_action)→+15
        outcome_delta = (score - 0.5) * 40       # 1.0→+20, 0.0→-20
        verified_delta = 15.0 if (actual_action and len(actual_action.strip()) > 0) else 0.0
        # Consistency: look at nearby experiences with same situation_type
        type_bonus = 0.0
        try:
            matched = c.execute(
                "SELECT quality_score, outcome_score, user_rating FROM experiences "
                "WHERE task_text=? AND user_id=? AND actual_action IS NOT NULL "
                "ORDER BY updated_at DESC LIMIT 3",
                ((task_text or "")[:300], user_id)).fetchall()
            if len(matched) >= 2:
                consistent = sum(1 for r in matched
                                 if (r["outcome_score"] or 0.5) >= 0.5) / len(matched)
                if consistent >= 0.8:
                    type_bonus = 5.0
                elif consistent <= 0.2:
                    type_bonus = -5.0
        except Exception:
            type_bonus = 0.0
        # Hermes P0: user_rating delta in quality_score formula
        user_rating_delta = 0.0
        try:
            row_ur = c.execute(
                "SELECT user_rating FROM experiences WHERE task_text=? AND user_id=? LIMIT 1",
                ((task_text or "")[:300], user_id)).fetchone()
            if row_ur and row_ur[0] and row_ur[0] > 0:
                ur = row_ur[0]
                user_rating_delta = ((ur - 3.0) / 2.0) * 15.0  # 1→-15, 3→0, 5→+15
        except Exception:
            user_rating_delta = 0.0
        new_qs = max(0.0, min(100.0, 50.0 + outcome_delta + verified_delta + type_bonus + user_rating_delta))
        c.execute(
            "UPDATE experiences SET quality_score=? "
            "WHERE task_text=? AND user_id=?",
            (new_qs, (task_text or "")[:300], user_id))

    # Trigger belief update via receive_verdict (uses outcome_score to drive dimension beliefs)
    # receive_verdict is already imported at module top
    try:
        _correct = bool(score >= 0.5)
        receive_verdict(
            chain_id=chain_id,
            correct=_correct,
            outcome_score=score,
            notes=f"actual_choice: predicted={predicted_action[:50]} actual={actual_action[:50]}",
            user_id=user_id,
        )
    except Exception as _e:
        import sys; print(f"receive_verdict call failed: {_e}", file=sys.stderr)

    return {
        "ok": True,
        "chain_id": chain_id,
        "predicted_action": predicted_action,
        "actual_action": actual_action,
        "outcome_score": score,
        "hit": hit,
        "experiences_updated": n_exp,
        "lessons_extracted": lesson_ids,
        "quality_score_delta": round(new_qs - 50.0, 1) if n_exp > 0 else 0.0,
    }


