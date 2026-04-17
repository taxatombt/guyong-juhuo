#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark.py — Juhuo Benchmark 系统

评估判断质量：
- GDPVal: 与人类判断对比（20+案例）
- 维度准确率: 各维度单独评估
- 自我一致性: 相似问题判断一致
- 反馈闭环: verdict 准确率

GDPVal 评分标准（TODO之四）：
  - A (>=85%): 超越人类基准
  - B (>=70%): 接近人类水平
  - C (>=50%): 初步可用
  - D (<50%): 需继续进化
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import re
from pathlib import Path

from judgment.logging_config import get_logger
try:
    from judgment.pipeline import check10d_full
except ImportError:
    check10d_full = None  # graceful degradation

log = get_logger("juhuo.benchmark")


# ═══════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class BenchmarkCase:
    id: str
    task: str
    expected: str
    difficulty: str  # simple / complex / critical / high
    categories: List[str]
    key_dims: List[str] = field(default_factory=list)  # 需要重点分析的维度


@dataclass
class BenchmarkResult:
    case_id: str
    verdict: str
    confidence: float
    dimensions: Dict[str, float]
    match_score: float
    dimension_coverage: float
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
    avg_coverage: float
    dimension_accuracy: Dict[str, float]
    weakest_dimensions: List[str]
    strongest_dimensions: List[str]
    gdval_grade: str
    gdval_score: float
    cases: List[BenchmarkResult]


# ═══════════════════════════════════════════════════════════════════════════
# GDPVal Benchmark 案例集（20+场景）
# 覆盖 9 大领域：career/finance/relationship/education/health/family/investment/migration/life
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_CASES: List[BenchmarkCase] = [
    # Career 职业类
    BenchmarkCase("b001", "要不要辞职创业？", "谨慎考虑，需评估财务风险", "critical", ["career", "risk"], ["economic", "game_theory", "cognitive"]),
    BenchmarkCase("b006", "要不要读研究生？", "看职业规划，权衡机会成本", "complex", ["education", "career"], ["economic", "temporal"]),
    BenchmarkCase("b008", "要不要换城市工作？", "权衡机会和生活质量", "complex", ["career", "lifestyle"], ["economic", "social"]),
    BenchmarkCase("b009", "要不要接受降薪但有股权的offer？", "看股权价值和公司前景", "complex", ["career", "investment"], ["economic", "cognitive"]),
    BenchmarkCase("b016", "要不要考公务员？", "取决于价值观和风险偏好", "complex", ["career", "life"], ["moral", "social"]),

    # Finance 财务类
    BenchmarkCase("b002", "朋友借5万要不要借？", "考虑关系亲疏和还款能力", "complex", ["relationship", "finance"], ["emotional", "game_theory"]),
    BenchmarkCase("b003", "买郊区大房子还是市区小房子？", "取决于生活阶段和通勤成本", "complex", ["finance", "lifestyle"], ["economic", "temporal"]),
    BenchmarkCase("b007", "要不要投资数字货币？", "高风险投资，控制仓位", "high", ["finance", "risk"], ["cognitive", "emotional"]),
    BenchmarkCase("b010", "要不要提前还房贷？", "比较贷款利率和投资收益", "simple", ["finance"], ["economic", "cognitive"]),
    BenchmarkCase("b017", "要不要买商业保险？", "看家庭风险敞口和财务状况", "complex", ["finance", "health"], ["economic"]),

    # Relationship 关系类
    BenchmarkCase("b005", "周末加班还是陪家人？", "取决于紧急程度和家庭阶段", "simple", ["work", "family"], ["emotional", "moral"]),
    BenchmarkCase("b011", "要不要和女朋友分手？", "评估感情质量和成长空间", "critical", ["relationship"], ["emotional", "moral", "metacognitive"]),
    BenchmarkCase("b012", "朋友得罪了我要不要原谅？", "看动机和长期关系价值", "complex", ["relationship", "moral"], ["emotional", "social"]),

    # Education 教育类
    BenchmarkCase("b013", "要不要让孩子学编程？", "看兴趣和未来趋势", "simple", ["education"], ["cognitive", "temporal"]),

    # Health 健康类
    BenchmarkCase("b014", "要不要辞职休息一段时间？", "评估身心健康和财务压力", "complex", ["health", "career"], ["emotional", "economic"]),

    # Family 家庭类
    BenchmarkCase("b015", "要不要把父母接来同住？", "权衡代际关系和个人空间", "complex", ["family", "relationship"], ["social", "emotional"]),

    # Investment 投资类
    BenchmarkCase("b018", "要不要现在买房？", "看房价走势和贷款利率", "complex", ["investment", "finance"], ["economic", "temporal", "cognitive"]),
    BenchmarkCase("b019", "要不要all in 一只股票？", "极高风险，应该分散", "critical", ["investment", "risk"], ["cognitive", "emotional", "economic"]),

    # Migration 移民类
    BenchmarkCase("b004", "要不要移民加拿大？", "多维度权衡，政策风险", "critical", ["life", "career"], ["economic", "social", "game_theory"]),

    # Life 生活方式类
    BenchmarkCase("b020", "要不要开始健身？", "值得投入，但需坚持", "simple", ["health"], ["temporal", "cognitive"]),
    BenchmarkCase("b021", "要不要断舍离精简生活？", "值得尝试，适合焦虑人群", "simple", ["lifestyle"], ["cognitive", "emotional"]),
    BenchmarkCase("b022", "要不要领养一只猫？", "评估生活方式和经济能力", "simple", ["life"], ["emotional", "social"]),
]


# ═══════════════════════════════════════════════════════════════════════════
# 匹配算法（改进版：语义关键词 + 否定检测）
# ═══════════════════════════════════════════════════════════════════════════

# 语义关键词同义词簇
_SYNONYMS = {
    "谨慎": ["谨慎", "小心", "稳妥", "保守", "风险", "评估", "三思"],
    "创业": ["创业", "辞职", "冒险", "自由职业"],
    "关系": ["关系", "感情", "友谊", "亲密", "朋友"],
    "经济": ["经济", "金钱", "财务", "收入", "成本", "机会成本", "收益"],
    "风险": ["风险", "危险", "不确定性", "波动"],
    "规划": ["规划", "计划", "目标", "长期"],
    "权衡": ["权衡", "取舍", "平衡", "取舍", "取舍"],
    "值得": ["值得", "应该", "建议", "推荐"],
    "不": ["不", "别", "不要", "不建议", "反对", "反对"],
    "移民": ["移民", "出国", "海外", "定居"],
    "买房": ["买房", "购房", "房产", "地产"],
    "分手": ["分手", "离婚", "结束", "分开"],
    "降薪": ["降薪", "减薪", "股权", "期权"],
    "健身": ["健身", "运动", "锻炼", "健康"],
}


class Benchmark:
    def __init__(self, cases: List[BenchmarkCase] = None):
        self.cases = cases or DEFAULT_CASES
        self.results: List[BenchmarkResult] = []
        # 统计覆盖
        self._case_by_id = {c.id: c for c in self.cases}

    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        import time
        start = time.time()

        if check10d_full is None:
            return BenchmarkResult(
                case_id=case.id,
                verdict="[check10d_full unavailable]",
                confidence=0.0,
                dimensions={},
                match_score=0.0,
                dimension_coverage=0.0,
                time_ms=0.0,
                timestamp=datetime.now().isoformat()
            )

        result = check10d_full(case.task)
        elapsed = (time.time() - start)

        match = self._calc_match(result.get("verdict", ""), case.expected)

        dims = {}
        for dim in result.get("dimensions", []):
            name = dim.get("name", dim.get("dimension", "unknown"))
            dims[name] = dim.get("score", 0.5)

        # 维度覆盖率：case.key_dims 中有多少在 result 中出现
        covered = sum(1 for kd in case.key_dims if kd in dims)
        coverage = covered / len(case.key_dims) if case.key_dims else 0.0

        return BenchmarkResult(
            case_id=case.id,
            verdict=result.get("verdict", ""),
            confidence=result.get("confidence", 0.5),
            dimensions=dims,
            match_score=match,
            dimension_coverage=coverage,
            time_ms=elapsed * 1000,
            timestamp=datetime.now().isoformat(),
        )

    def _calc_match(self, verdict: str, expected: str) -> float:
        """
        改进的语义匹配：
        1. 精确包含 → 1.0
        2. 语义关键词簇匹配 → 0.6-0.9
        3. 否定关系检测 → 0.0-0.3
        4. 关键词覆盖率 → 比例分
        """
        v = verdict.lower()
        e = expected.lower()

        # 精确包含
        if e in v:
            return 1.0

        # 否定关系检测
        verd_lower = verdict.lower()
        neg_phrases = ["不建议", "不要", "反对", "慎重", "谨慎", "风险", "不应该", "不值得"]
        pos_phrases = ["建议", "值得", "应该", "鼓励", "可以"]
        verdict_is_negative = any(p in verd_lower for p in neg_phrases)
        verdict_is_positive = any(p in verd_lower for p in pos_phrases)

        expected_is_negative = any(p in e for p in ["风险", "谨慎", "慎重", "评估", "权衡"])
        expected_is_positive = any(p in e for p in ["值得", "建议", "应该", "鼓励"])

        # 完全相反
        if verdict_is_negative and expected_is_positive:
            return 0.1
        if verdict_is_positive and expected_is_negative:
            return 0.1

        # 语义关键词匹配
        score = 0.0
        matched_kw = 0
        total_kw = 0
        for category, keywords in _SYNONYMS.items():
            for kw in keywords:
                if kw in e:
                    total_kw += 1
                    if kw in v:
                        matched_kw += 1
                        # 同义词簇贡献分
                        score += 1.0 / len(keywords)

        if total_kw > 0:
            kw_score = matched_kw / total_kw
            score = max(score, kw_score * 0.8)

        return min(score, 1.0)

    def run_all(self) -> BenchmarkReport:
        self.results = []
        for case in self.cases:
            log.info(f"[Benchmark] Running: {case.id} — {case.task[:30]}...")
            try:
                self.results.append(self.run_case(case))
            except Exception as e:
                log.error(f"[Benchmark] Case {case.id} failed: {e}")
        return self._generate_report()

    def _generate_report(self) -> BenchmarkReport:
        if not self.results:
            return BenchmarkReport(0, 0, 0, 0, 0, 0, 0, {}, [], [], "N/A", 0, [])

        passed = sum(1 for r in self.results if r.match_score >= 0.5)
        accuracy = passed / len(self.results)
        avg_conf = sum(r.confidence for r in self.results) / len(self.results)
        avg_time = sum(r.time_ms for r in self.results) / len(self.results)
        avg_cov = sum(r.dimension_coverage for r in self.results) / len(self.results)

        # 维度准确率
        dim_scores: Dict[str, List[float]] = {}
        for r in self.results:
            for dim, score in r.dimensions.items():
                dim_scores.setdefault(dim, []).append(score)
        dim_acc = {d: sum(s) / len(s) for d, s in dim_scores.items()}
        sorted_dims = sorted(dim_acc.items(), key=lambda x: x[1])
        weakest = [d[0] for d in sorted_dims[:3]]
        strongest = [d[0] for d in sorted_dims[-3:]]

        # GDPVal 评分
        gdval_score = accuracy * 100
        if gdval_score >= 85:
            grade = "A"
        elif gdval_score >= 70:
            grade = "B"
        elif gdval_score >= 50:
            grade = "C"
        else:
            grade = "D"

        return BenchmarkReport(
            total_cases=len(self.results),
            passed=passed,
            failed=len(self.results) - passed,
            accuracy=accuracy,
            avg_confidence=avg_conf,
            avg_time_ms=avg_time,
            avg_coverage=avg_cov,
            dimension_accuracy=dim_acc,
            weakest_dimensions=weakest,
            strongest_dimensions=strongest,
            gdval_grade=grade,
            gdval_score=gdval_score,
            cases=self.results,
        )

    def format_report(self, r: BenchmarkReport) -> str:
        lines = [
            "\n" + "=" * 64,
            "⚖️  Juhuo GDPVal Benchmark Report",
            "=" * 64,
            f"  总案例: {r.total_cases} | 通过: {r.passed} ✅ | 失败: {r.failed} ❌",
            f"  准确率: {r.accuracy * 100:.1f}% | GDPVal: {r.gdval_grade} ({r.gdval_score:.1f})",
            f"  平均置信度: {r.avg_confidence * 100:.1f}% | 维度覆盖: {r.avg_coverage * 100:.1f}%",
            f"  平均耗时: {r.avg_time_ms:.0f}ms",
            "",
            "【最强维度】",
        ]
        for d in r.strongest_dimensions:
            lines.append(f"  🟢 {d}: {r.dimension_accuracy.get(d, 0) * 100:.1f}%")
        lines.append("\n【最弱维度】")
        for d in r.weakest_dimensions:
            lines.append(f"  🔴 {d}: {r.dimension_accuracy.get(d, 0) * 100:.1f}%")
        lines.append("\n【案例详情】")
        for c in r.cases:
            s = "✅" if c.match_score >= 0.5 else "❌"
            cov = f"⚠cov{c.dimension_coverage:.0%}" if c.dimension_coverage < 0.5 else ""
            lines.append(f"  {s} [{c.case_id}] {c.task[:25]}... | {c.verdict[:30]} ({c.match_score:.1f}) {cov}")
        lines.append("=" * 64)
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# CLI / 导入接口
# ═══════════════════════════════════════════════════════════════════════════

def run_benchmark() -> BenchmarkReport:
    """运行完整 benchmark，返回报告"""
    bm = Benchmark()
    report = bm.run_all()
    print(bm.format_report(report))
    return report


if __name__ == "__main__":
    run_benchmark()
