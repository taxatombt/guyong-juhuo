# judgment/verdict_collector.py — Shim
# 真实实现在 subsystems/judgment/closed_loop.py 和 judgment_db.py
from subsystems.judgment.judgment_db import (
    get_overall_accuracy,
    get_verdict_history,
)
from subsystems.judgment.closed_loop import receive_verdict

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


def mark_verdict_correct(chain_id: str, notes: str = "") -> bool:
    """标记某条判断为正确"""
    return receive_verdict(chain_id=chain_id, correct=True, notes=notes)


def mark_verdict_wrong(chain_id: str, notes: str = "") -> bool:
    """标记某条判断为错误"""
    return receive_verdict(chain_id=chain_id, correct=False, notes=notes)


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



def receive_actual_choice(chain_id, actual_action):
    """用户决策后调用：写入 verdict_outcomes + 更新 judgment_snapshots.outcome_score"""
    import sqlite3, re
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT task_text, verdict, predicted_action, prediction_confidence FROM judgment_snapshots WHERE chain_id=?",
        (chain_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "Chain not found"}
    task_text, verdict, predicted_action, prediction_confidence = row
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
    try:
        c.execute(
            "INSERT INTO verdict_outcomes (chain_id, task_text, correct, predicted_action, actual_action, outcome_score, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chain_id, (task_text or "")[:300], 1 if hit else 0,
             predicted_action[:200], (actual_action or "")[:200], score, "actual_choice"))
    except Exception as ex:
        print(f"verdict_outcomes insert error: {ex}")
    c.execute("UPDATE judgment_snapshots SET outcome_score=? WHERE chain_id=?",
              (score, chain_id))
    c.execute(
        "UPDATE experiences SET actual_action=?, outcome_score=?, updated_at=datetime('now') "
        "WHERE task_text=? AND (actual_action IS NULL OR actual_action='')",
        ((actual_action or "")[:200], score, (task_text or "")[:300]))
    n_exp = c.rowcount
    conn.commit()
    conn.close()
    return {
        "ok": True,
        "chain_id": chain_id,
        "predicted_action": predicted_action,
        "actual_action": actual_action,
        "outcome_score": score,
        "hit": hit,
        "experiences_updated": n_exp,
    }


