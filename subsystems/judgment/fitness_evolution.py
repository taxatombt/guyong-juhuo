#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fitness_evolution.py — Juhuo 判断Fitness反馈循环 (SQLite版)

P1改进: judgment评分根据outcome动态进化
P2改进: 使用SQLite替代JSON存储
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from .judgment_db import get_conn, save_verdict, update_dimension_stats


@dataclass
class DimensionAccuracy:
    dimension: str
    correct: int = 0
    total: int = 0
    accuracy: float = 0.5
    last_updated: str = ""

    def update(self, correct: bool):
        self.total += 1
        if correct:
            self.correct += 1
        self.accuracy = self.correct / self.total if self.total > 0 else 0.5
        self.last_updated = datetime.now().isoformat()

    def weight_bonus(self, base_weight: float) -> float:
        """accuracy → 权重加成"""
        bonus = (self.accuracy - 0.5) * 0.4  # ±20%
        return base_weight * (1 + bonus)


class FitnessEvolution:
    """判断Fitness反馈循环（SQLite版）"""

    def record_outcome(
        self,
        chain_id: str,
        task_text: str,
        dimensions: List[str],
        weights: Dict[str, float],
        correct: bool,
    ) -> Dict:
        """记录判断结果，更新维度准确率，并触发Self-Evolver闭环"""
        # 写入verdict表
        save_verdict(chain_id, task_text, correct, "fitness_evolution")
        
        # 更新每个维度的准确率
        for dim in dimensions:
            update_dimension_stats(dim, correct)

        # Self-Evolver: 同步到self_model
        try:
            from .self_evolover import sync_to_self_model, run_evolution_cycle
            sync_to_self_model(chain_id)  # Hook数据写入self_model
            # 运行进化闭环（检查是否需要重训规则）
            evo_result = run_evolution_cycle()
            # 如果触发进化，把结果带上
            if evo_result.get("triggered"):
                print(f"[Self-Evolver] 触发: {evo_result.get('trigger', {}).get('reason')}, 优胜: {evo_result.get('winner')}")
        except Exception as e:
            print(f"[Self-Evolver] 闭环异常: {e}")

        return self.get_stats()

    def get_boosted_weights(self, base_weights: Dict[str, float]) -> Dict[str, float]:
        """返回加成后的权重"""
        boosted = {}
        with get_conn() as c:
            for dim, base_w in base_weights.items():
                row = c.execute(
                    "SELECT accuracy, total_count FROM dimension_stats WHERE dimension=?",
                    (dim,)
                ).fetchone()
                
                if row and row["total_count"] >= 3:
                    acc = row["accuracy"]
                    bonus = (acc - 0.5) * 0.4
                    boosted[dim] = round(base_w * (1 + bonus), 4)
                else:
                    boosted[dim] = base_w
        return boosted

    def get_stats(self) -> Dict:
        """获取进化统计"""
        dim_stats = {}
        with get_conn() as c:
            rows = c.execute("SELECT * FROM dimension_stats").fetchall()
            for row in rows:
                dim = row["dimension"]
                dim_stats[dim] = {
                    "accuracy": round(row["accuracy"], 3),
                    "correct": row["correct_count"],
                    "total": row["total_count"],
                    "weight_bonus": round((row["accuracy"] - 0.5) * 0.4, 3),
                }

            # 整体统计
            verdict_row = c.execute("""
                SELECT COUNT(*) as total, SUM(correct) as correct
                FROM verdict_outcomes
            """).fetchone()
            
            total = verdict_row["total"] or 0
            correct = verdict_row["correct"] or 0
            overall_accuracy = correct / total if total > 0 else 0.5

        return {
            "total_judgments": total,
            "dimensions_tracked": len(dim_stats),
            "overall_accuracy": round(overall_accuracy, 3),
            "dimension_stats": dim_stats,
        }

    def get_low_confidence_dims(self, threshold: float = 0.4) -> List[str]:
        """获取低置信度维度"""
        dims = []
        with get_conn() as c:
            rows = c.execute(
                "SELECT dimension FROM dimension_stats WHERE accuracy < ? AND total_count >= 3",
                (threshold,)
            ).fetchall()
            dims = [r["dimension"] for r in rows]
        return dims

    def get_high_confidence_dims(self, threshold: float = 0.6) -> List[str]:
        """获取高置信度维度"""
        dims = []
        with get_conn() as c:
            rows = c.execute(
                "SELECT dimension FROM dimension_stats WHERE accuracy >= ? AND total_count >= 5",
                (threshold,)
            ).fetchall()
            dims = [r["dimension"] for r in rows]
        return dims


# 全局实例
_fitness: Optional[FitnessEvolution] = None


def get_fitness() -> FitnessEvolution:
    global _fitness
    if _fitness is None:
        _fitness = FitnessEvolution()
    return _fitness


def record_judgment_outcome(
    chain_id: str,
    task_text: str,
    dimensions: List[str],
    weights: Dict[str, float],
    correct: bool,
) -> Dict:
    """快捷函数：记录判断结果"""
    return get_fitness().record_outcome(chain_id, task_text, dimensions, weights, correct)


def get_boosted_weights(base_weights: Dict[str, float]) -> Dict[str, float]:
    """快捷函数：获取加成后权重"""
    return get_fitness().get_boosted_weights(base_weights)


def get_fitness_stats() -> Dict:
    """快捷函数：获取进化统计"""
    return get_fitness().get_stats()
