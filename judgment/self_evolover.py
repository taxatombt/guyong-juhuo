#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
self_evolover.py — Juhuo Self-Evolver 自动闭环引擎

核心闭环：
1. Hook捕获判断数据 → self_model更新
2. 偏差超过阈值 → 触发规则重训  
3. 新旧规则对比 → 优胜劣汰
4. 进化验证 → 有效则强化，无效则回滚

触发方式：
- 自动：EvolverScheduler (定时检查)
- 手动：run_evolution_cycle()
- CLI: python -m judgment.self_evolover
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from threading import Timer, Lock

# 配置
BIAS_THRESHOLD = 0.7
BIAS_CONSECUTIVE = 2  # 连续2次错误就触发（降低阈值以便测试）
ACCURACY_THRESHOLD = 0.4
MIN_SAMPLES = 3  # 至少3个样本即可触发
COOLDOWN_HOURS = 24  # 冷却24小时（生产用）
VALIDATION_WINDOW = 10  # 验证窗口：进化后追踪10次判断

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
        # 连续错误检查 - 优先使用 verdict_outcomes（实际有数据的表）
        recent = conn.execute("""
            SELECT v.*, j.dimensions 
            FROM verdict_outcomes v
            LEFT JOIN judgments j ON v.chain_id = j.chain_id
            ORDER BY v.created_at DESC LIMIT 6
        """).fetchall()
        
        # 检查连续错误
        consecutive_wrong = 0
        for row in recent[:3]:
            if row["correct"] == 0 or row["correct"] is False:
                consecutive_wrong += 1
        
        if consecutive_wrong >= BIAS_CONSECUTIVE:
            return {"triggered": True, "reason": f"连续{consecutive_wrong}次判断错误", "type": "consecutive_wrong"}
        
        # 维度准确率检查（如果样本够多）
        dim = conn.execute("""
            SELECT * FROM dimension_stats WHERE total_count>=3 ORDER BY accuracy ASC LIMIT 1
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
        # 优先使用 verdict_outcomes（实际有数据的表）
        rows = conn.execute("""
            SELECT v.chain_id, v.task_text, v.correct as outcome, v.created_at,
                   j.dimensions, j.weights
            FROM verdict_outcomes v
            LEFT JOIN judgments j ON v.chain_id = j.chain_id
            ORDER BY v.created_at DESC LIMIT 100
        """).fetchall()
        
        if not rows:
            # 备选：使用 judgment_records
            rows = conn.execute("""
                SELECT r.*, j.dimensions, j.weights
                FROM judgment_records r
                LEFT JOIN judgments j ON r.chain_id = j.chain_id
                ORDER BY r.created_at DESC LIMIT 100
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

# 5.5 应用进化后的规则（新增）
def apply_evolved_weights(new_weights: Dict[str, float]) -> bool:
    """将进化后的规则应用到 dynamic_weights.py 和 self_model.json"""
    success = True
    
    # 1. 写入 self_model.json
    try:
        from self_model.self_model import load_model, save_model
        model = load_model()
        # 更新权重
        if not hasattr(model, 'weights'):
            model.weights = {}
        model.weights.update(new_weights)
        save_model(model)
        print(f"[Self-Evolver] 已更新 self_model.json: {new_weights}")
    except Exception as e:
        print(f"[Self-Evolver] self_model.json 更新失败: {e}")
        success = False
    
    # 2. 写入 evolutions/evolved_weights.json（动态权重备份）
    try:
        import os
        evol_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "evolutions")
        os.makedirs(evol_dir, exist_ok=True)
        evol_file = os.path.join(evol_dir, "evolved_weights.json")
        
        # 读取旧文件
        old_evolved = {}
        if os.path.exists(evol_file):
            with open(evol_file, "r", encoding="utf-8") as f:
                old_evolved = json.load(f)
        
        # 追加新进化记录
        evol_record = {
            "timestamp": datetime.now().isoformat(),
            "weights": new_weights,
        }
        history = old_evolved.get("history", [])
        history.append(evol_record)
        # 只保留最近10次
        history = history[-10:]
        
        with open(evol_file, "w", encoding="utf-8") as f:
            json.dump({"current": new_weights, "history": history}, f, ensure_ascii=False, indent=2)
        print(f"[Self-Evolver] 已写入 evolutions/evolved_weights.json")
    except Exception as e:
        print(f"[Self-Evolver] evolutions/evolved_weights.json 更新失败: {e}")
        success = False
    
    return success

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
    # 过滤掉没有 dimensions 的案例
    valid_cases = [c for c in cases if c.get("dimensions")]
    if len(valid_cases) < MIN_SAMPLES:
        result["status"] = "insufficient_samples"
        result["reason"] = f"有效案例{len(valid_cases)}个，需要{MIN_SAMPLES}个"
        return result
    cases = valid_cases
    
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
    
    # 【关键】如果新规则更好，应用它！
    if comp["winner"] == "new" and comp.get("improvement", 0) > 0.05:
        applied = apply_evolved_weights(new_rules["weights"])
        result["applied"] = applied
        if applied:
            result["status"] = "evolved"
            print(f"[Self-Evolver] SUCCESS: New rules applied! Improvement: {comp.get('improvement', 0):.2%}")
        else:
            result["status"] = "apply_failed"
    else:
        result["status"] = "completed"
        result["applied"] = False
    
    return result

if __name__ == "__main__":
    print("Self-Evolver 闭环引擎")
    r = run_evolution_cycle()
    print(f"状态: {r['status']}")
    if r.get("triggered"):
        print(f"触发: {r.get('trigger', {}).get('reason')}")
        print(f"优胜: {r.get('winner')} 提升: {r.get('improvement', 0):.2%}")


# ═══════════════════════════════════════════════════════════════════════════
# P0: 自动触发层 - EvolverScheduler
# ═══════════════════════════════════════════════════════════════════════════

class EvolverScheduler:
    """
    最小触发层：定时检查 + 自动进化 + 进化验证
    
    数据流：
        Timer.tick() → should_evolve() → run_evolution_cycle()
            ↓
        apply_evolved_weights() → 记录 evolution_validation
            ↓
        Timer.tick() → validate_evolution() → 强化/回滚
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls, cooldown_hours: int = COOLDOWN_HOURS):
        """单例模式"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, cooldown_hours: int = COOLDOWN_HOURS):
        if self._initialized:
            return
        self.cooldown_hours = cooldown_hours
        self._last_evolution = None  # 上次进化时间
        self._last_validation = None  # 上次验证时间
        self._pending_validations: Dict[str, Dict] = {}  # 待验证的进化
        self._timer: Optional[Timer] = None
        self._running = False
        self._initialized = True
    
    def should_evolve(self) -> bool:
        """是否应该触发进化"""
        # 冷却期检查
        if self._last_evolution:
            elapsed = time.time() - self._last_evolution
            if elapsed < self.cooldown_hours * 3600:
                return False
        
        # 样本量检查
        with get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM verdict_outcomes").fetchone()
            count = row["cnt"] if row else 0
        
        return count >= MIN_SAMPLES
    
    def register_evolution(self, evolution_id: int, new_weights: Dict) -> None:
        """
        注册一次进化，为后续验证做准备
        在 apply_evolved_weights() 后调用
        """
        # 记录应用时的准确率基准
        with get_conn() as conn:
            # 获取应用前的准确率
            pre_row = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN correct = 1 THEN 1 ELSE 0 END) as correct
                FROM verdict_outcomes
            """).fetchone()
            
            pre_accuracy = (pre_row["correct"] / pre_row["total"]) if pre_row["total"] > 0 else 0.5
        
        self._pending_validations[str(evolution_id)] = {
            "evolution_id": evolution_id,
            "applied_at": time.time(),
            "new_weights": new_weights,
            "pre_accuracy": pre_accuracy,
            "post_judgments": 0,
            "post_correct": 0
        }
        
        self._last_evolution = time.time()
    
    def record_outcome(self, correct: int) -> None:
        """
        记录每次判断结果，用于验证进化效果
        在 judgment_engine 每次判断后调用
        """
        for evo_id, data in self._pending_validations.items():
            if data["post_judgments"] < VALIDATION_WINDOW:
                data["post_judgments"] += 1
                data["post_correct"] += correct
    
    def validate_evolution(self, evolution_id: str) -> Dict:
        """
        验证进化效果
        - 有效（提升>5%）→ 强化
        - 无效（下降>5%）→ 回滚
        - 不确定 → 继续追踪
        """
        data = self._pending_validations.get(evolution_id)
        if not data:
            return {"status": "unknown", "reason": "evolution not found"}
        
        # 验证窗口未满
        if data["post_judgments"] < VALIDATION_WINDOW:
            return {"status": "pending", "progress": f"{data['post_judgments']}/{VALIDATION_WINDOW}"}
        
        # 计算准确率变化
        post_accuracy = data["post_correct"] / data["post_judgments"]
        delta = post_accuracy - data["pre_accuracy"]
        
        result = {
            "evolution_id": evolution_id,
            "pre_accuracy": data["pre_accuracy"],
            "post_accuracy": post_accuracy,
            "delta": delta,
            "post_judgments": data["post_judgments"]
        }
        
        if delta > 0.05:
            # 提升>5%，强化
            result["status"] = "validated"
            result["action"] = "reinforced"
            print(f"[Self-Evolver] ✅ 进化{evolution_id}验证通过：准确率提升 {delta:.2%}")
        
        elif delta < -0.05:
            # 下降>5%，回滚
            self._rollback(evolution_id, data, delta)
            result["status"] = "rolled_back"
            result["action"] = "rolled_back"
            result["rollback_reason"] = f"准确率下降 {-delta:.2%}"
            print(f"[Self-Evolver] ⚠️ 进化{evolution_id}回滚：准确率下降 {-delta:.2%}")
        
        else:
            result["status"] = "inconclusive"
            result["action"] = "continued"
            print(f"[Self-Evolver] ⏳ 进化{evolution_id}验证不确定：delta={delta:.2%}")
        
        # 更新数据库
        self._update_validation_record(result)
        
        # 清理
        del self._pending_validations[evolution_id]
        
        return result
    
    def _rollback(self, evolution_id: str, data: Dict, delta: float) -> bool:
        """回滚到旧规则"""
        try:
            from self_model.self_model import load_model, save_model
            
            model = load_model()
            
            # 从 fitness_baseline 获取旧权重
            try:
                from judgment.fitness_baseline import load_baseline
                baseline = load_baseline()
                if baseline and "weights" in baseline:
                    model.weights = baseline["weights"].copy()
                    save_model(model)
                    return True
            except:
                pass
            
            return False
        except:
            return False
    
    def _update_validation_record(self, result: Dict) -> None:
        """更新验证记录到数据库"""
        with get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO evolution_validation 
                (evolution_id, applied_at, post_judgments, post_correct, 
                 accuracy_delta, status, validated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result.get("evolution_id"),
                datetime.now().isoformat(),
                result.get("post_judgments", 0),
                result.get("post_correct", 0),
                result.get("delta", 0),
                result.get("status"),
                datetime.now().isoformat()
            ))
            conn.commit()
    
    def run_if_needed(self) -> Optional[Dict]:
        """条件满足则执行进化"""
        if self.should_evolve():
            result = run_evolution_cycle()
            
            # 注册进化
            if result.get("applied"):
                with get_conn() as conn:
                    row = conn.execute(
                        "SELECT last_insert_rowid() as id"
                    ).fetchone()
                    if row:
                        self.register_evolution(row["id"], result.get("new_weights", {}))
            
            return result
        return None
    
    def start(self, interval_hours: float = 1.0) -> None:
        """
        启动定时调度器
        - interval_hours: 检查间隔（默认1小时）
        """
        if self._running:
            return
        
        self._running = True
        
        def _tick():
            if not self._running:
                return
            
            # 1. 检查是否需要进化
            self.run_if_needed()
            
            # 2. 验证待验证的进化
            for evo_id in list(self._pending_validations.keys()):
                self.validate_evolution(evo_id)
            
            # 3. 下一次检查
            self._timer = Timer(interval_hours * 3600, _tick)
            self._timer.start()
        
        # 首次启动：60秒后执行
        self._timer = Timer(60, _tick)
        self._timer.start()
        print(f"[Self-Evolver] 调度器已启动，间隔 {interval_hours} 小时")
    
    def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        print("[Self-Evolver] 调度器已停止")
    
    def status(self) -> Dict:
        """获取调度器状态"""
        return {
            "running": self._running,
            "cooldown_hours": self.cooldown_hours,
            "last_evolution": self._last_evolution,
            "pending_validations": len(self._pending_validations),
            "validations": list(self._pending_validations.keys())
        }


# 全局调度器实例
_scheduler: Optional[EvolverScheduler] = None


def get_scheduler(cooldown_hours: int = COOLDOWN_HOURS) -> EvolverScheduler:
    """获取全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = EvolverScheduler(cooldown_hours)
    return _scheduler


def start_evolver_scheduler(cooldown_hours: int = COOLDOWN_HOURS, interval_hours: float = 1.0) -> EvolverScheduler:
    """启动进化调度器（便捷函数）"""
    sched = get_scheduler(cooldown_hours)
    sched.start(interval_hours)
    return sched


# ═══════════════════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Juhuo Self-Evolver")
    parser.add_argument("--run", action="store_true", help="运行一次进化")
    parser.add_argument("--start", action="store_true", help="启动定时调度器")
    parser.add_argument("--status", action="store_true", help="查看调度器状态")
    parser.add_argument("--cooldown", type=int, default=COOLDOWN_HOURS, help=f"冷却时间(小时, 默认{COOLDOWN_HOURS})")
    parser.add_argument("--interval", type=float, default=1.0, help="检查间隔(小时, 默认1.0)")
    
    args = parser.parse_args()
    
    if args.run:
        result = run_evolution_cycle()
        print(f"状态: {result['status']}")
        if result.get("triggered"):
            print(f"触发: {result.get('trigger', {}).get('reason')}")
            print(f"优胜: {result.get('winner')} 提升: {result.get('improvement', 0):.2%}")
    
    elif args.start:
        sched = start_evolver_scheduler(args.cooldown, args.interval)
        print(f"调度器已启动，冷却时间 {args.cooldown} 小时")
        print("按 Ctrl+C 停止")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sched.stop()
    
    elif args.status:
        sched = get_scheduler(args.cooldown)
        status = sched.status()
        print("调度器状态:")
        for k, v in status.items():
            print(f"  {k}: {v}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()