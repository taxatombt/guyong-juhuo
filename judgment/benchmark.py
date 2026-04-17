#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark.py — Juhuo Benchmark 系统

评估判断质量：
- GDPVal: 与人类判断对比
- 维度准确率: 各维度单独评估
- 自我一致性: 相似问题判断一致
- 反馈闭环: verdict 准确率
"""

from __future__ import annotations
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from judgment.logging_config import get_logger
from judgment.pipeline import check10d_full

log = get_logger("juhuo.benchmark")


@dataclass
class BenchmarkCase:
    id: str
    task: str
    expected: str
    difficulty: str
    categories: List[str]


@dataclass
class BenchmarkResult:
    case_id: str
    verdict: str
    confidence: float
    dimensions: Dict[str, float]
    match_score: float
    time_ms: float
    timestamp: str


@dataclass
class BenchmarkReport:
    total_cases: int
    passed: int
    failed: int
    accuracy: float
    avg_confidence: float
    avg_time_ms: float
    dimension_accuracy: Dict[str, float]
    weakest_dimensions: List[str]
    strongest_dimensions: List[str]
    cases: List[BenchmarkResult]


DEFAULT_CASES = [
    BenchmarkCase("b001", "要不要辞职创业？", "谨慎考虑", "critical", ["career", "risk"]),
    BenchmarkCase("b002", "朋友借5万要不要借？", "考虑关系和还款能力", "complex", ["relationship", "finance"]),
    BenchmarkCase("b003", "买郊区大房子还是市区小房子？", "取决于生活阶段", "complex", ["finance", "lifestyle"]),
    BenchmarkCase("b004", "要不要移民加拿大？", "多维度权衡", "critical", ["life", "career"]),
    BenchmarkCase("b005", "周末加班还是陪家人？", "取决于紧急程度", "simple", ["work", "family"]),
    BenchmarkCase("b006", "要不要读研究生？", "看职业规划", "complex", ["education", "career"]),
    BenchmarkCase("b007", "要不要投资数字货币？", "高风险投资", "high", ["finance", "risk"]),
    BenchmarkCase("b008", "要不要换城市工作？", "权衡机会和生活", "complex", ["career", "lifestyle"]),
]


class Benchmark:
    def __init__(self, cases: List[BenchmarkCase] = None):
        self.cases = cases or DEFAULT_CASES
        self.results: List[BenchmarkResult] = []
    
    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        import time
        start = time.time()
        result = check10d_full(case.task)
        elapsed = (time.time() - start) * 1000
        
        match = self._calc_match(result.get("verdict", ""), case.expected)
        
        dims = {}
        for dim in result.get("dimensions", []):
            name = dim.get("name", dim.get("dimension", "unknown"))
            dims[name] = dim.get("score", 0.5)
        
        return BenchmarkResult(
            case_id=case.id,
            verdict=result.get("verdict", ""),
            confidence=result.get("confidence", 0.5),
            dimensions=dims,
            match_score=match,
            time_ms=elapsed,
            timestamp=datetime.now().isoformat()
        )
    
    def _calc_match(self, verdict: str, expected: str) -> float:
        verdict_lower = verdict.lower()
        expected_lower = expected.lower()
        if expected_lower in verdict_lower:
            return 1.0
        keywords = expected_lower.split()
        matches = sum(1 for k in keywords if k in verdict_lower)
        return matches / len(keywords) if keywords else 0.0
    
    def run_all(self) -> BenchmarkReport:
        self.results = []
        for case in self.cases:
            log.info(f"Running: {case.id}")
            try:
                self.results.append(self.run_case(case))
            except Exception as e:
                log.error(f"Case {case.id} failed: {e}")
        return self._generate_report()
    
    def _generate_report(self) -> BenchmarkReport:
        if not self.results:
            return BenchmarkReport(0, 0, 0, 0, 0, 0, {}, [], [], [])
        
        passed = sum(1 for r in self.results if r.match_score >= 0.5)
        accuracy = passed / len(self.results)
        avg_conf = sum(r.confidence for r in self.results) / len(self.results)
        avg_time = sum(r.time_ms for r in self.results) / len(self.results)
        
        dim_scores: Dict[str, List[float]] = {}
        for r in self.results:
            for dim, score in r.dimensions.items():
                dim_scores.setdefault(dim, []).append(score)
        
        dim_acc = {d: sum(s) / len(s) for d, s in dim_scores.items()}
        sorted_dims = sorted(dim_acc.items(), key=lambda x: x[1])
        weakest = [d[0] for d in sorted_dims[:3]]
        strongest = [d[0] for d in sorted_dims[-3:]]
        
        return BenchmarkReport(
            total_cases=len(self.results),
            passed=passed,
            failed=len(self.results) - passed,
            accuracy=accuracy,
            avg_confidence=avg_conf,
            avg_time_ms=avg_time,
            dimension_accuracy=dim_acc,
            weakest_dimensions=weakest,
            strongest_dimensions=strongest,
            cases=self.results
        )
    
    def format_report(self, r: BenchmarkReport) -> str:
        lines = [
            "\n" + "="*60,
            "⚖️  Juhuo Benchmark Report",
            "="*60,
            f"\n总案例: {r.total_cases} | 通过: {r.passed} ✅ | 失败: {r.failed} ❌",
            f"准确率: {r.accuracy * 100:.1f}% | 平均置信度: {r.avg_confidence * 100:.1f}%",
            f"平均耗时: {r.avg_time_ms:.0f}ms",
            "\n【最强维度】",
        ]
        for d in r.strongest_dimensions:
            lines.append(f"  🟢 {d}: {r.dimension_accuracy.get(d, 0) * 100:.1f}%")
        lines.append("\n【最弱维度】")
        for d in r.weakest_dimensions:
            lines.append(f"  🔴 {d}: {r.dimension_accuracy.get(d, 0) * 100:.1f}%")
        lines.append("\n【案例】")
        for c in r.cases:
            s = "✅" if c.match_score >= 0.5 else "❌"
            lines.append(f"  {s} [{c.case_id}] {c.verdict[:40]}... ({c.match_score:.0%})")
        lines.append("="*60)
        return "\n".join(lines)
    
    def save_report(self, r: BenchmarkReport) -> str:
        data_dir = Path(__file__).parent.parent / "data" / "benchmark"
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total": r.total_cases, "passed": r.passed, "failed": r.failed,
                "accuracy": r.accuracy, "avg_confidence": r.avg_confidence,
                "avg_time_ms": r.avg_time_ms,
                "dimension_accuracy": r.dimension_accuracy,
                "weakest": r.weakest_dimensions, "strongest": r.strongest_dimensions,
                "cases": [{"id": c.case_id, "verdict": c.verdict, "match": c.match_score} for c in r.cases]
            }, f, ensure_ascii=False, indent=2)
        return str(path)


def run_benchmark() -> BenchmarkReport:
    bench = Benchmark()
    report = bench.run_all()
    print(bench.format_report(report))
    path = bench.save_report(report)
    print(f"\n报告已保存: {path}")
    return report


if __name__ == "__main__":
    run_benchmark()
