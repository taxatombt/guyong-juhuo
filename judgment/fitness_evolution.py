#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fitness_evolution.py — Juhuo 判断Fitness反馈循环

P1改进: judgment评分根据outcome动态进化

核心机制:
1. 每次receive_verdict → 更新维度准确率
2. 准确率 → 动态权重调整
3. 权重 → 下次判断优先级

公式:
  dimension_accuracy[dim] = (correct_count / total_count) * 0.9 + base
  boosted_weight = base_weight * (1 + accuracy_bonus)
  accuracy_bonus = (accuracy - 0.5) * 0.4  # ±20%
"""

import json, time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

# 路径
_JD = Path(__file__).parent.parent / "data" / "judgment_data"
_EV = _JD / "fitness_evolution.json"
_ACC = _JD / "dimension_accuracy.json"
_JD.mkdir(parents=True, exist_ok=True)


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


@dataclass
class JudgmentOutcome:
    chain_id: str
    task_text: str
    dimensions: List[str]
    weights: Dict[str, float]
    correct: bool
    timestamp: str


class FitnessEvolution:
    """判断Fitness反馈循环"""

    def __init__(self):
        if _EV.exists():
            try:
                data = json.loads(_EV.read_text(encoding="utf-8"))
                self.accuracy: Dict[str, DimensionAccuracy] = {
                    k: DimensionAccuracy(**v) for k, v in data.get("accuracy", {}).items()
                }
                self.history: List[JudgmentOutcome] = [
                    JudgmentOutcome(**h) for h in data.get("history", [])
                ]
                self.total_judgments = data.get("total_judgments", 0)
            except Exception:
                self._init_empty()
        else:
            self._init_empty()

    def _init_empty(self):
        self.accuracy = {}
        self.history = []
        self.total_judgments = 0

    def _save(self):
        data = {
            "accuracy": {k: asdict(v) for k, v in self.accuracy.items()},
            "history": [asdict(h) for h in self.history[-1000:]],  # 保留最近1000条
            "total_judgments": self.total_judgments,
            "last_updated": datetime.now().isoformat(),
        }
        _EV.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_outcome(
        self,
        chain_id: str,
        task_text: str,
        dimensions: List[str],
        weights: Dict[str, float],
        correct: bool,
    ) -> Dict:
        """记录判断结果，更新维度准确率"""
        self.total_judgments += 1
        outcome = JudgmentOutcome(
            chain_id=chain_id,
            task_text=task_text[:200],
            dimensions=dimensions,
            weights=weights,
            correct=correct,
            timestamp=datetime.now().isoformat(),
        )
        self.history.append(outcome)

        # 更新每个维度的准确率
        for dim in dimensions:
            if dim not in self.accuracy:
                self.accuracy[dim] = DimensionAccuracy(dimension=dim)
            self.accuracy[dim].update(correct)

        self._save()

        return self.get_stats()

    def get_boosted_weights(self, base_weights: Dict[str, float]) -> Dict[str, float]:
        """返回加成后的权重"""
        boosted = {}
        for dim, base_w in base_weights.items():
            acc = self.accuracy.get(dim)
            if acc and acc.total >= 3:  # 至少3次才启用
                boosted[dim] = round(acc.weight_bonus(base_w), 4)
            else:
                boosted[dim] = base_w
        return boosted

    def get_stats(self) -> Dict:
        """获取进化统计"""
        dim_stats = {}
        for dim, acc in self.accuracy.items():
            dim_stats[dim] = {
                "accuracy": round(acc.accuracy, 3),
                "correct": acc.correct,
                "total": acc.total,
                "weight_bonus": round((acc.accuracy - 0.5) * 0.4, 3),
            }

        # 整体准确率
        total_correct = sum(a.correct for a in self.accuracy.values())
        total_all = sum(a.total for a in self.accuracy.values())
        overall_accuracy = total_correct / total_all if total_all > 0 else 0.5

        return {
            "total_judgments": self.total_judgments,
            "dimensions_tracked": len(self.accuracy),
            "overall_accuracy": round(overall_accuracy, 3),
            "dimension_stats": dim_stats,
        }

    def get_low_confidence_dims(self, threshold: float = 0.4) -> List[str]:
        """获取低置信度维度（需要更多关注）"""
        return [
            dim for dim, acc in self.accuracy.items()
            if acc.accuracy < threshold and acc.total >= 3
        ]

    def get_high_confidence_dims(self, threshold: float = 0.6) -> List[str]:
        """获取高置信度维度（可以信赖）"""
        return [
            dim for dim, acc in self.accuracy.items()
            if acc.accuracy >= threshold and acc.total >= 5
        ]


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
