#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
self_evolver.py — Self-Evolver 自动闭环

定时/手动运行，从实际任务中学习，形成进化闭环。

数据流：
    外部触发（cron/手动）
        ↓
    Phase 1: 收集 — 从 judgment memory / diff_tracker 拉取近期记录
        ↓
    Phase 2: 分析 — 识别成功/失败模式（调用 judgment 十维分析结果）
        ↓
    Phase 3: 进化 — 更新 evolver lessons，更新 fitness_baseline
        ↓
    Phase 4: 输出 — 生成学习报告，写入 evolutions/

使用方式：
    from evolver.self_evolver import SelfEvolver
    evo = SelfEvolver()
    evo.run_full_cycle()        # 完整闭环
    evo.summarize()             # 输出摘要
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime


EVOLVER_DIR = Path(__file__).parent.parent / "data" / "evolutions"
LESSONS_FILE = EVOLVER_DIR / "self_lessons.jsonl"
PATTERNS_FILE = EVOLVER_DIR / "patterns.json"
METRICS_FILE = EVOLVER_DIR / "self_metrics.json"


@dataclass
class DecisionRecord:
    """单次决策记录"""
    decision_id: str
    timestamp: float
    task: str
    path: str  # P/A/B/C
    dimensions: Dict[str, float]  # 各维度得分
    outcome: str  # "success" / "failure" / "partial"
    outcome_detail: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvolutionResult:
    """单次进化结果"""
    timestamp: float
    phase: str  # "collect" / "analyze" / "evolve" / "output"
    records_processed: int
    new_patterns: int
    lessons_added: int
    summary: str


class SelfEvolver:
    """
    Self-Evolver 闭环。

    通过 4 个 Phase 完成自动进化：
    1. Collect — 从 judgment memory / diff_tracker 收集近期记录
    2. Analyze — 调用 judgment 十维分析识别模式
    3. Evolve — 更新 evolver lessons + fitness_baseline
    4. Output — 写报告到 evolutions/
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or EVOLVER_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._metrics = self._load_metrics()

    # ── Phase 1: 收集 ───────────────────────────────────────────────────────

    def collect_recent_decisions(self, limit: int = 50) -> List[DecisionRecord]:
        """
        从 judgment memory（如果可用）收集近期决策。
        如果 judgment.memory 不可用，返回空列表（优雅降级）。
        """
        records = []
        try:
            from judgment.memory import get_decisions
            raw = get_decisions(limit)
            for d in raw:
                records.append(DecisionRecord(
                    decision_id=d.get("id", str(d.get("timestamp", ""))),
                    timestamp=d.get("timestamp", time.time()),
                    task=d.get("task", ""),
                    path=d.get("decision", "unknown"),
                    dimensions=d.get("dimensions", {}),
                    outcome=d.get("feedback", "unknown"),
                ))
        except ImportError:
            pass  # judgment.memory 不可用，优雅降级

        # 也尝试从 causal_memory/diff_tracker 补充
        try:
            from causal_memory.diff_tracker import TurnDiffTracker
            tracker = TurnDiffTracker()
            for turn_id, diff in list(tracker._turn_diffs.items())[:limit]:
                # 如果已经在 records 中，跳过
                if any(r.decision_id == turn_id for r in records):
                    continue
                records.append(DecisionRecord(
                    decision_id=turn_id,
                    timestamp=diff.timestamp,
                    task=diff.decision_summary,
                    path="unknown",
                    dimensions={},
                    outcome="unknown",
                ))
        except ImportError:
            pass

        return records

    def collect_diffs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """从 TurnDiffTracker 收集近期文件变更。"""
        diffs = []
        try:
            from causal_memory.diff_tracker import TurnDiffTracker
            tracker = TurnDiffTracker()
            for turn_id, diff in list(tracker._turn_diffs.items())[:limit]:
                diffs.append({
                    "turn_id": turn_id,
                    "timestamp": diff.timestamp,
                    "summary": diff.decision_summary,
                    "changes_count": len(diff.changes),
                    "changes": [c.path for c in diff.changes],
                })
        except ImportError:
            pass
        return diffs

    # ── Phase 2: 分析 ───────────────────────────────────────────────────────

    def analyze_patterns(self, records: List[DecisionRecord]) -> List[Dict[str, Any]]:
        """
        分析决策模式：
        - 哪些路径（P/A/B/C）成功率更高？
        - 哪些维度得分低但outcome好？
        - 哪些维度得分高但outcome差？
        """
        patterns = []

        if not records:
            return patterns

        # 按路径分组统计
        path_stats: Dict[str, Dict[str, int]] = {}
        for r in records:
            if r.path not in path_stats:
                path_stats[r.path] = {"total": 0, "success": 0, "failure": 0}
            path_stats[r.path]["total"] += 1
            if r.outcome in ("success", "correct"):
                path_stats[r.path]["success"] += 1
            elif r.outcome in ("failure", "wrong"):
                path_stats[r.path]["failure"] += 1

        for path, stats in path_stats.items():
            if stats["total"] >= 2:  # 至少2个样本
                rate = stats["success"] / stats["total"]
                patterns.append({
                    "type": "path_success_rate",
                    "path": path,
                    "rate": rate,
                    "total": stats["total"],
                    "confidence": "low" if stats["total"] < 5 else "medium",
                })

        # 维度分析（如果有维度数据）
        dim_records = [r for r in records if r.dimensions]
        if len(dim_records) >= 3:
            for dim_name in dim_records[0].dimensions.keys():
                scores = [r.dimensions.get(dim_name, 0) for r in dim_records]
                avg_score = sum(scores) / len(scores)
                outcomes = [r.outcome for r in dim_records]
                if "success" in outcomes or "failure" in outcomes:
                    patterns.append({
                        "type": "dimension_correlation",
                        "dimension": dim_name,
                        "avg_score": round(avg_score, 3),
                        "sample_size": len(dim_records),
                    })

        return patterns

    # ── Phase 3: 进化 ───────────────────────────────────────────────────────

    def evolve(self, patterns: List[Dict[str, Any]]) -> int:
        """
        将分析出的模式写入 evolver lessons。

        返回新增的 lessons 数量。
        """
        lessons_added = 0

        for pattern in patterns:
            lesson = {
                "id": f"self_evo_{int(time.time())}_{lessons_added}",
                "timestamp": time.time(),
                "source": "self_evolver",
                "pattern": pattern,
            }
            if self._append_lesson(lesson):
                lessons_added += 1

        # 更新 fitness_baseline
        self._update_fitness(patterns)

        return lessons_added

    def _append_lesson(self, lesson: dict) -> bool:
        """追加单条 lesson 到 LESSONS_FILE。"""
        try:
            LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LESSONS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(lesson, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False

    def _update_fitness(self, patterns: List[Dict[str, Any]]) -> None:
        """更新 fitness_baseline。"""
        try:
            metrics = self._metrics
            metrics["last_update"] = time.time()
            metrics["cycles_run"] = metrics.get("cycles_run", 0) + 1
            metrics["total_patterns"] = metrics.get("total_patterns", 0) + len(patterns)
            self._save_metrics()
        except Exception:
            pass

    def _load_metrics(self) -> dict:
        """加载 metrics。"""
        if METRICS_FILE.exists():
            try:
                return json.loads(METRICS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"cycles_run": 0, "total_patterns": 0, "last_update": None}

    def _save_metrics(self) -> None:
        """保存 metrics。"""
        try:
            METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
            METRICS_FILE.write_text(json.dumps(self._metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ── Phase 4: 输出 ───────────────────────────────────────────────────────

    def summarize(self) -> str:
        """
        生成学习摘要。
        """
        metrics = self._metrics
        lessons_count = 0
        if LESSONS_FILE.exists():
            lessons_count = sum(1 for _ in open(LESSONS_FILE, encoding="utf-8"))

        lines = [
            "=== Self-Evolver 学习摘要 ===",
            f"运行周期数: {metrics.get('cycles_run', 0)}",
            f"累计模式数: {metrics.get('total_patterns', 0)}",
            f"Lessons 文件: {LESSONS_FILE}",
            f"Patterns 文件: {PATTERNS_FILE}",
        ]
        return "\n".join(lines)

    # ── 完整闭环 ─────────────────────────────────────────────────────────────

    def run_full_cycle(self) -> EvolutionResult:
        """
        运行完整的 Self-Evolver 闭环。

        1. Collect — 收集近期决策和 diffs
        2. Analyze — 分析模式
        3. Evolve — 写入 lessons
        4. Output — 生成摘要
        """
        # Phase 1: 收集
        records = self.collect_recent_decisions(limit=50)
        diffs = self.collect_diffs(limit=20)

        # Phase 2: 分析
        patterns = self.analyze_patterns(records)

        # 保存 patterns
        if patterns:
            try:
                PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
                existing = []
                if PATTERNS_FILE.exists():
                    try:
                        existing = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
                    except Exception:
                        existing = []
                all_patterns = existing + [{"timestamp": time.time(), **p} for p in patterns]
                PATTERNS_FILE.write_text(json.dumps(all_patterns[-100:], ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        # Phase 3: 进化
        lessons_added = self.evolve(patterns)

        # Phase 4: 输出
        summary = self.summarize()

        return EvolutionResult(
            timestamp=time.time(),
            phase="complete",
            records_processed=len(records),
            new_patterns=len(patterns),
            lessons_added=lessons_added,
            summary=summary,
        )

    def run_cron_cycle(self) -> str:
        """
        供 cron 调用的简化版本，返回摘要字符串。
        """
        try:
            result = self.run_full_cycle()
            return result.summary
        except Exception as e:
            return f"[ERROR] SelfEvolver 失败: {e}"


def main():
    """CLI 入口：python -m evolver.self_evolver"""
    import argparse
    parser = argparse.ArgumentParser(description="juhuo Self-Evolver")
    parser.add_argument("--cron", action="store_true", help="cron 模式（简化输出）")
    args = parser.parse_args()

    evo = SelfEvolver()
    if args.cron:
        result = evo.run_cron_cycle()
        print(result)
    else:
        result = evo.run_full_cycle()
        print(f"=== SelfEvolver 完成 ===")
        print(f"records_processed: {result.records_processed}")
        print(f"new_patterns: {result.new_patterns}")
        print(f"lessons_added: {result.lessons_added}")
        print(f"\n{result.summary}")


if __name__ == "__main__":
    main()