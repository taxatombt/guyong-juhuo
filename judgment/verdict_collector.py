# judgment/verdict_collector.py — Shim
# 真实实现在 subsystems/judgment/closed_loop.py 和 judgment_db.py
from subsystems.judgment.judgment_db import (
    get_overall_accuracy,
    get_verdict_history,
)
from subsystems.judgment.closed_loop import receive_verdict

import json
from pathlib import Path

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
