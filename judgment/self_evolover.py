#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
self_evolover.py — Juhuo Self-Evolver 自动闭环引擎

核心闭环：
1. Hook捕获判断数据 → self_model更新
2. 偏差超过阈值 → 触发规则重训  
3. 新旧规则对比 → 优胜劣汰
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 配置
BIAS_THRESHOLD = 0.7
BIAS_CONSECUTIVE = 3
ACCURACY_THRESHOLD = 0.4
MIN_SAMPLES = 5
COOLDOWN_HOURS = 24

# 数据库
DB_PATH = Path(__file__).parent.parent / "data" / "judgment_data" / "juhuo_judgment.db"

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evolution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_type TEXT, trigger_reason TEXT,
            old_rules TEXT, new_rules TEXT,
            comparison_result TEXT, winner TEXT, improvement REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

# 1. 同步到self_model
def sync_to_self_model(chain_id: str) -> Optional[Dict]:
    """Hook捕获的判断数据写入self_model"""
    try:
        from self_model.self_model import update_from_feedback, load_model
        with get_conn() as conn:
            # 尝试从judgment_records获取
            row = conn.execute(
                "SELECT * FROM judgment_records WHERE chain_id=?", (chain_id,)
            ).fetchone()
            
            if not row:
                # 尝试从judgments获取
                row = conn.execute(
                    "SELECT * FROM judgments WHERE chain_id=?", (chain_id,)
                ).fetchone()
            
            if not row:
                return None
            
            # 判断outcome: outcome列或result列
            outcome = row["outcome"] if "outcome" in row.keys() else (row["result"] if "result" in row.keys() else "")
            
            # 获取dimensions和weights
            dims = json.loads(row["dimensions"]) if row["dimensions"] else []
            weights = json.loads(row["weights"]) if row["weights"] else {}
            
            task = row["task_text"] if "task_text" in row.keys() else (row["task"] if "task" in row.keys() else "")
            ts = row["created_at"] if "created_at" in row.keys() else datetime.now().isoformat()
            
            event = {
                "chain_id": chain_id,
                "task": task,
                "feedback": outcome,
                "timestamp": ts,
                "dimensions": dims,
                "weights": weights,
            }
            
            updated = update_from_feedback(event)
            return {"success": True, "bias_updated": updated is not None}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

# 2. 检查触发条件
def check_trigger() -> Dict:
    """检查是否触发进化"""
    with get_conn() as conn:
        # 连续高偏差检查 - 使用judgment_records
        recent = conn.execute("""
            SELECT * FROM judgment_records WHERE outcome IN ('坏','错','wrong','bad','')
            ORDER BY created_at DESC LIMIT 6
        """).fetchall()
        
        consecutive = 0
        for row in recent[:3]:
            # 从verdict表获取deviation
            v = conn.execute(
                "SELECT deviation FROM verdict WHERE chain_id=?", (row["chain_id"],)
            ).fetchone()
            if v and v["deviation"] and v["deviation"] >= BIAS_THRESHOLD:
                consecutive += 1
        
        if consecutive >= 3:
            return {"triggered": True, "reason": "连续3次偏差超过0.7", "type": "consecutive_bias"}
        
        # 维度准确率检查
        dim = conn.execute("""
            SELECT * FROM dimension_stats WHERE total_count>=5 ORDER BY accuracy ASC LIMIT 1
        """).fetchone()
        
        if dim and dim["accuracy"] <= ACCURACY_THRESHOLD:
            return {
                "triggered": True,
                "reason": f"维度{dim['dimension']}准确率{dim['accuracy']:.0%}过低",
                "type": "low_accuracy"
            }
        
        # 冷却检查
        last = conn.execute(
            "SELECT created_at FROM evolution_log ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if last:
            dt = datetime.fromisoformat(last["created_at"])
            if datetime.now() - dt < timedelta(hours=COOLDOWN_HOURS):
                return {"triggered": False, "reason": f"冷却中({COOLDOWN_HOURS}h内)"}
        
        return {"triggered": False, "reason": "未达到触发条件"}

# 3. 获取历史案例
def get_cases() -> List[Dict]:
    """获取历史案例用于规则训练"""
    with get_conn() as conn:
        # 优先使用judgment_records
        rows = conn.execute("""
            SELECT r.*, v.deviation, v.accuracy as verdict_accuracy
            FROM judgment_records r
            LEFT JOIN verdict v ON r.chain_id = v.chain_id
            WHERE r.outcome IS NOT NULL
            ORDER BY r.created_at DESC LIMIT 100
        """).fetchall()
        
        if not rows:
            # 备选：使用judgments + verdict_outcomes
            rows = conn.execute("""
                SELECT j.*, vo.correct as outcome, v.deviation
                FROM judgments j
                LEFT JOIN verdict_outcomes vo ON j.chain_id = vo.chain_id
                LEFT JOIN verdict v ON j.chain_id = v.chain_id
                ORDER BY j.created_at DESC LIMIT 100
            """).fetchall()
        
        return [dict(row) for row in rows]

# 4. 计算新权重
def compute_new_weights(cases: List[Dict]) -> Dict:
    """基于案例计算新权重"""
    perf = {}
    for c in cases:
        dims = json.loads(c.get("dimensions", "[]")) if c.get("dimensions") else []
        
        # 判断是否正确：outcome列或correct列
        outcome = c.get("outcome")
        if outcome is None:
            correct = c.get("correct", 0)
        else:
            correct = outcome not in ["坏", "错", "wrong", "bad", "", None]
        
        for d in dims:
            if d not in perf:
                perf[d] = [0, 0]
            perf[d][1] += 1
            if correct:
                perf[d][0] += 1
    
    weights = {}
    for d, (ok_cnt, total) in perf.items():
        acc = ok_cnt / total if total > 0 else 0.5
        weights[d] = round(0.5 + (acc - 0.5) * 0.5, 3)
    
    return weights

# 5. 对比新旧规则
def compare(old_rules: Dict, new_rules: Dict, cases: List[Dict]) -> Dict:
    """新旧规则对比"""
    def score(rules):
        if not cases:
            return 0
        w = rules.get("weights", {})
        ok_cnt = 0
        for c in cases:
            dims = json.loads(c.get("dimensions", "[]")) if c.get("dimensions") else []
            
            outcome = c.get("outcome")
            if outcome is None:
                correct = bool(c.get("correct", 0))
            else:
                correct = outcome not in ["坏", "错", "wrong", "bad", "", None]
            
            if dims and w:
                predicted = sum(w.get(d, 0.1) for d in dims) / len(dims) > 0.5
                if predicted == correct:
                    ok_cnt += 1
        return ok_cnt / len(cases) if cases else 0
    
    old_s = score(old_rules)
    new_s = score(new_rules)
    return {
        "old_score": old_s,
        "new_score": new_s,
        "winner": "new" if new_s > old_s else "old",
        "improvement": new_s - old_s
    }

# 6. 主闭环
def run_evolution_cycle() -> Dict:
    """执行完整的Self-Evolver闭环"""
    result = {
        "timestamp": datetime.now().isoformat(),
        "status": "ok",
        "triggered": False
    }
    
    trigger = check_trigger()
    result["trigger"] = trigger
    
    if not trigger.get("triggered"):
        result["status"] = "no_trigger"
        return result
    
    result["triggered"] = True
    
    cases = get_cases()
    if len(cases) < 5:
        result["status"] = "insufficient_samples"
        return result
    
    try:
        from self_model.self_model import load_model
        old_model = load_model()
        old_rules = {
            "weights": getattr(old_model, "weights", {}),
            "biases": list(old_model.biases.keys())
        }
    except Exception:
        old_rules = {"weights": {}, "biases": []}
    
    new_rules = {"weights": compute_new_weights(cases)}
    comp = compare(old_rules, new_rules, cases)
    
    result["winner"] = comp["winner"]
    result["improvement"] = comp.get("improvement", 0)
    
    # 记录到数据库
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO evolution_log (trigger_type, trigger_reason, old_rules, new_rules, comparison_result, winner, improvement) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trigger.get("type"), trigger.get("reason"), json.dumps(old_rules), json.dumps(new_rules), json.dumps(comp), comp["winner"], comp.get("improvement", 0))
        )
        conn.commit()
    
    result["status"] = "completed"
    return result

if __name__ == "__main__":
    print("Self-Evolver 闭环引擎")
    r = run_evolution_cycle()
    print(f"状态: {r['status']}")
    if r.get("triggered"):
        print(f"触发: {r.get('trigger', {}).get('reason')}")
        print(f"优胜: {r.get('winner')} 提升: {r.get('improvement', 0):.2%}")