#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_evolver.py — Juhuo 全模块自我进化闭环

让所有模块都能自我进化：
1. Compaction → 根据压缩效果调整阈值
2. Multi-Agent → Agent 协作效率进化
3. TUI → 根据使用习惯优化布局
4. Exec Policy → 从误报/漏报中学习
5. Session → 合并相似 session

核心：每个模块的进化触发条件不同，但都有"追踪→分析→调整→验证"的闭环
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict

from judgment.logging_config import get_logger
log = get_logger("juhuo.auto_evolver")


# 配置
EVOLUTION_DIR = Path(__file__).parent.parent / "data" / "auto_evolutions"
ANALYTICS_DIR = Path(__file__).parent.parent / "data" / "analytics"
MIN_DATA_POINTS = 5


@dataclass
class EvolutionRecord:
    module: str
    action: str
    old_value: str
    new_value: str
    reason: str
    confidence: float
    timestamp: str
    verified: bool = False
    result: str = ""


def track(module: str, metric: str, value: float, **extra) -> None:
    """追踪模块指标"""
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    file = ANALYTICS_DIR / f"{module}.jsonl"
    record = {"metric": metric, "value": value, "timestamp": datetime.now().isoformat(), **extra}
    with open(file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_metrics(module: str, metric: str = None, hours: int = 24) -> List[Dict]:
    """获取模块指标"""
    file = ANALYTICS_DIR / f"{module}.jsonl"
    if not file.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=hours)
    results = []
    with open(file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    if datetime.fromisoformat(data["timestamp"]) > cutoff:
                        if metric is None or data["metric"] == metric:
                            results.append(data)
                except:
                    continue
    return results


class CompactionEvolver:
    """Compaction 模块进化"""
    def evolve(self) -> List[EvolutionRecord]:
        records = []
        ratios = get_metrics("compactor", "compress_ratio")
        if len(ratios) < MIN_DATA_POINTS:
            return records
        avg_ratio = sum(r["value"] for r in ratios) / len(ratios)
        preserved = get_metrics("compactor", "preserved_ratio")
        if len(preserved) >= MIN_DATA_POINTS:
            preserved_avg = sum(r["value"] for r in preserved) / len(preserved)
            if preserved_avg < 0.7:
                records.append(EvolutionRecord(
                    module="compactor", action="increase_preserve",
                    old_value="MAX_HISTORY=100", new_value="MAX_HISTORY=150",
                    reason=f"保留率 {preserved_avg:.0%} < 70%", confidence=0.7,
                    timestamp=datetime.now().isoformat()))
        return records


class MultiAgentEvolver:
    """Multi-Agent 模块进化"""
    def evolve(self) -> List[EvolutionRecord]:
        records = []
        successes = get_metrics("multi_agent", "success")
        if len(successes) < MIN_DATA_POINTS:
            return records
        success_rate = sum(1 for s in successes if s["value"] == 1) / len(successes)
        if success_rate < 0.8:
            records.append(EvolutionRecord(
                module="multi_agent", action="increase_timeout",
                old_value="TIMEOUT=30", new_value="TIMEOUT=60",
                reason=f"成功率 {success_rate:.0%} < 80%", confidence=0.6,
                timestamp=datetime.now().isoformat()))
        return records


class ExecPolicyEvolver:
    """Exec Policy 模块进化"""
    def evolve(self) -> List[EvolutionRecord]:
        records = []
        fps = get_metrics("exec_policy", "false_positive")
        blocked = get_metrics("exec_policy", "blocked")
        if len(fps) >= MIN_DATA_POINTS and blocked:
            fp_rate = len(fps) / len(blocked)
            if fp_rate > 0.3:
                records.append(EvolutionRecord(
                    module="exec_policy", action="relax_patterns",
                    old_value=f"误报率 {fp_rate:.0%}", new_value="调整模式",
                    reason="误报过多，放宽限制", confidence=0.6,
                    timestamp=datetime.now().isoformat()))
        return records


class TUIEvolver:
    """TUI 模块进化"""
    def evolve(self) -> List[EvolutionRecord]:
        records = []
        errors = get_metrics("tui", "error")
        if len(errors) >= MIN_DATA_POINTS:
            error_rate = len(errors) / max(1, len(get_metrics("tui", "interaction")))
            if error_rate > 0.1:
                records.append(EvolutionRecord(
                    module="tui", action="simplify_ui",
                    old_value="复杂UI", new_value="简化布局",
                    reason=f"错误率 {error_rate:.0%} > 10%", confidence=0.5,
                    timestamp=datetime.now().isoformat()))
        return records


class SessionEvolver:
    """Session 模块进化"""
    def evolve(self) -> List[EvolutionRecord]:
        records = []
        sessions = get_metrics("session", "similarity")
        if len(sessions) >= MIN_DATA_POINTS:
            high_sim = [s for s in sessions if s["value"] > 0.8]
            if len(high_sim) >= 3:
                records.append(EvolutionRecord(
                    module="session", action="merge_similar",
                    old_value="独立session", new_value="合并高相似",
                    reason=f"发现 {len(high_sim)} 个高相似session", confidence=0.7,
                    timestamp=datetime.now().isoformat()))
        return records


# 主进化器
class AutoEvolver:
    """全模块自我进化"""
    
    def __init__(self):
        self.evolvers = {
            "compactor": CompactionEvolver(),
            "multi_agent": MultiAgentEvolver(),
            "exec_policy": ExecPolicyEvolver(),
            "tui": TUIEvolver(),
            "session": SessionEvolver(),
        }
    
    def run_all(self) -> List[EvolutionRecord]:
        """运行所有模块进化"""
        log.info("Starting auto evolution for all modules")
        all_records = []
        for name, evolver in self.evolvers.items():
            try:
                records = evolver.evolve()
                all_records.extend(records)
                if records:
                    log.info(f"[{name}] {len(records)} suggestions")
            except Exception as e:
                log.error(f"[{name}] Evolution failed: {e}")
        if all_records:
            self._save_records(all_records)
        return all_records
    
    def _save_records(self, records: List[EvolutionRecord]) -> None:
        EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)
        file = EVOLUTION_DIR / f"evolution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(file, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)


def run_evolution() -> List[EvolutionRecord]:
    """运行全模块进化"""
    evolver = AutoEvolver()
    return evolver.run_all()


if __name__ == "__main__":
    records = run_evolution()
    print(f"\n进化完成：{len(records)} 条建议")
    for r in records:
        print(f"  [{r.module}] {r.action}: {r.reason}")
