#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shadow_mode.py — 影子判断系统

来源：Markfans/CryptoQuant-AI 的 Shadow Mode 理念

核心理念：
- 对每个判断，同时生成一个"影子判断"（shadow verdict）
- 影子判断用保守/悲观参数，记录但不执行
- 积累够多后，自动跑胜率统计 → 验证 judgment 质量
- 比 benchmark 更快积累数据（不需要人工标注）

与 benchmark 的区别：
- benchmark   → 人工标注 ground truth → 慢但准
- shadow mode → 影子账户被动积累 → 快但需后期分析
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from paths import PATHS
except ImportError:
    import os
    PATHS = {"DATA": os.path.join(os.path.dirname(__file__), "..", "data")}


SHADOW_DIR = Path(PATHS["DATA"]) / "shadow"
SHADOW_DIR.mkdir(parents=True, exist_ok=True)

# 影子判断配置（保守参数）
SHADOW_CONFIG = {
    "confidence_threshold": 0.80,      # 只记录置信度 >= 80% 的影子判断
    "max_position_pct": 0.10,          # 影子仓位上限 10%（比真实更保守）
    "shadow_only": True,               # True = 只记录不执行
    "tag": "shadow",
}


def shadow_record(verdict: str, confidence: float, dimensions: List[Dict],
                  task: str, outcome_actual: Optional[str] = None) -> Dict[str, Any]:
    """
    记录一个影子判断。

    调用时机：
    1. 判断发生时 → shadow_record(task, verdict, confidence, dimensions)
    2. outcome 已知后 → shadow_update(chain_id, outcome_actual)

    返回：影子判断记录
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    ts = now.isoformat()

    # 只记录高置信度判断（降低噪音）
    if confidence < SHADOW_CONFIG["confidence_threshold"]:
        return {"skipped": True, "reason": f"confidence {confidence} < {SHADOW_CONFIG['confidence_threshold']}"}

    shadow_id = f"sh_{now.strftime('%Y%m%d%H%M%S')}_{hash(task) % 100000:05d}"

    record = {
        "shadow_id": shadow_id,
        "task": task[:200],           # 截断避免过长
        "verdict": verdict,
        "confidence": confidence,
        "position_pct": SHADOW_CONFIG["max_position_pct"],  # 影子仓位固定 10%
        "dimensions": {d.get("id", d.get("name", "?")): d.get("score", 0)
                       for d in dimensions},
        "timestamp": ts,
        "date": date_str,
        "outcome": outcome_actual,    # None = 未结算
        "outcome_correct": None,       # None = 待验证
        "verdict_category": _categorize_verdict(verdict),
    }

    _write_shadow(date_str, record)
    return record


def shadow_update(shadow_id: str, outcome: str) -> bool:
    """
    给影子判断打 outcome，结算胜率。

    调用：outcome 已知后（用户反馈 / 结果揭晓）
    """
    # 在今日文件中查找
    today = datetime.now().strftime("%Y-%m-%d")
    records = _read_shadows(today)
    updated = False

    for rec in records:
        if rec.get("shadow_id") == shadow_id:
            rec["outcome"] = outcome
            rec["outcome_correct"] = _score_outcome(rec["verdict"], outcome)
            rec["settled_at"] = datetime.now().isoformat()
            updated = True
            break

    if updated:
        _write_shadow(today, records)
    return updated


def shadow_stats(days: int = 30) -> Dict[str, Any]:
    """
    统计影子判断胜率（近 N 天）。

    返回：
    - total: 总影子判断数
    - settled: 已结算数
    - win_rate: 胜率
    - by_confidence_band: 按置信度分档的胜率
    - by_category: 按类别统计
    """
    import os
    cutoff = datetime.now().timestamp() - days * 86400
    all_records = []

    for f in SHADOW_DIR.glob("shadows_*.jsonl"):
        if f.stat().st_mtime < cutoff:
            continue
        for line in f.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            try:
                all_records.append(json.loads(line))
            except Exception:
                pass

    settled = [r for r in all_records if r.get("outcome_correct") is not None]
    total = len(all_records)
    settled_n = len(settled)

    if settled_n == 0:
        return {
            "total": total,
            "settled": 0,
            "win_rate": None,
            "message": "尚无结算数据，继续积累",
            "by_confidence_band": {},
            "by_category": {},
        }

    win_count = sum(1 for r in settled if r["outcome_correct"])
    win_rate = win_count / settled_n

    # 按置信度分档
    bands = {"high": [], "mid": [], "low": []}
    for r in settled:
        c = r["confidence"]
        band = "high" if c >= 0.80 else "mid" if c >= 0.65 else "low"
        bands[band].append(r["outcome_correct"])

    by_band = {}
    for band, recs in bands.items():
        if recs:
            by_band[band] = {
                "n": len(recs),
                "win_rate": sum(recs) / len(recs),
            }

    # 按类别统计
    by_cat = {}
    for r in settled:
        cat = r.get("verdict_category", "unknown")
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(r["outcome_correct"])
    for cat, recs in by_cat.items():
        by_cat[cat] = {
            "n": len(recs),
            "win_rate": sum(recs) / len(recs),
        }

    return {
        "total": total,
        "settled": settled_n,
        "win_rate": round(win_rate, 4),
        "win_count": win_count,
        "by_confidence_band": by_band,
        "by_category": by_cat,
        "message": f"近{days}天 {settled_n}笔结算，胜率 {win_rate:.1%}",
    }


def shadow_recent(n: int = 10) -> List[Dict]:
    """最近 N 条影子判断"""
    records = []
    for f in sorted(SHADOW_DIR.glob("shadows_*.jsonl"), reverse=True):
        for line in reversed(f.read_text(encoding="utf-8").strip().split("\n")):
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                pass
            if len(records) >= n:
                return records
    return records


# ── 内部函数 ─────────────────────────────────────────────────────

def _write_shadow(date_str: str, records):
    """追加写影子判断到当日文件"""
    file = SHADOW_DIR / f"shadows_{date_str}.jsonl"
    mode = "a" if file.exists() else "w"
    if isinstance(records, list):
        with open(file, mode, encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    else:
        with open(file, "a", encoding="utf-8") as f:
            f.write(json.dumps(records, ensure_ascii=False) + "\n")


def _read_shadows(date_str: str) -> List[Dict]:
    """读当日所有影子判断"""
    file = SHADOW_DIR / f"shadows_{date_str}.jsonl"
    if not file.exists():
        return []
    records = []
    for line in file.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            pass
    return records


def _categorize_verdict(verdict: str) -> str:
    """把 verdict 归类（简单关键词匹配）"""
    v = verdict.lower()
    if any(k in v for k in ["建议", "推荐", "可以", "做", "执行"]):
        return "action"
    if any(k in v for k in ["不建", "暂缓", "不要", "反对", "拒绝"]):
        return "caution"
    if any(k in v for k in ["中立", "平衡", "两面", "均可"]):
        return "neutral"
    return "unknown"


def _score_outcome(verdict: str, outcome: str) -> Optional[bool]:
    """
    简单 outcome 评分。

    逻辑：
    - verdict 含"建议/推荐/可以" 且 outcome 含"成功/正确/好/正" → True
    - verdict 含"不建/暂缓/不要" 且 outcome 含"失败/错误/坏/负" → True
    - verdict 含"建议/推荐" 且 outcome 含"失败/错误" → False
    - verdict 含"不建/暂缓" 且 outcome 含"成功/正确" → False
    """
    if not outcome:
        return None
    v = verdict.lower()
    o = outcome.lower()

    # 正面关键词
    positive = any(k in o for k in ["成功", "正确", "好", "正", "达", "赚", "涨", "对"])
    negative = any(k in o for k in ["失败", "错误", "坏", "负", "亏", "跌", "错", "赔"])

    action_kw = any(k in v for k in ["建议", "推荐", "可以", "做", "执行", "进行"])
    caution_kw = any(k in v for k in ["不建", "暂缓", "不要", "反对", "拒绝", "不建议"])

    if action_kw:
        return positive and not negative
    if caution_kw:
        return negative and not positive
    return None  # 中立判决无法自动评分
