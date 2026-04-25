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

from .logging_config import get_logger
try:
    from .pipeline import check10d_full
except ImportError as e:
    import sys, os
    print(f"[benchmark] check10d_full import failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
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
    task: str             # 诊断用，format_report 需要
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
                task=case.task,
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

        # ── 闭环Step3：benchmark结果自动反馈进 evolver ──────────────
        # match_score → outcome_score：≥0.5=判断正确，<0.5=判断错误
        # receive_verdict() 会：
        #   1. 更新 judgment_snapshots.outcome_auto + corrected
        #   2. 触发 evolver.record_outcome()
        #   3. 触发 dimension_beliefs 更新
        chain_id = result.get("meta", {}).get("chain_id", "")
        try:
            from .closed_loop import receive_verdict
            receive_verdict(
                chain_id=chain_id,
                task_text=case.task if not chain_id else None,
                correct=(match >= 0.5),
                notes=f"benchmark:{case.id}",
                outcome_score=match,
                actual_action=case.expected,
                verifier="benchmark",
            )
        except Exception as e:
            log.warning(f"[benchmark] receive_verdict failed for {case.id}: {e}")

        return BenchmarkResult(
            case_id=case.id,
            task=case.task,
            verdict=result.get("verdict", ""),
            confidence=result.get("confidence", 0.5),
            dimensions=dims,
            match_score=match,
            dimension_coverage=coverage,
            time_ms=elapsed * 1000,
            timestamp=datetime.now().isoformat(),
        )

    def _calc_match(self, verdict: str, expected: str, rep_penalty_val: float = None) -> float:
        """
        语义方向匹配（v3 — MiniMind GRPO 增强版）：
        1. 精确包含 → 1.0
        2. 字符重叠 >= 60% → 0.8
        3. 方向分(0~0.6) + 可操作性分(0~0.2) + 主题重叠分(0~0.2)
        4. [GRPO] Repetition Penalty 扣分：verbose/循环输出降低得分

        GRPO Repetition Penalty 公式（MiniMind train_grpo.py 启发）：
          penalty = -alpha * rep_penalty_val
          其中 alpha 是超参（默认 0.3），rep_penalty_val ∈ [0.0, 0.5]
          最终分数 = min(max(raw_score + penalty, 0.0), 1.0)
        """
        from judgment.lessons import rep_penalty  # 懒加载避免循环

        v, e = verdict.strip(), expected.strip()
        if not v or not e:
            return 0.0

        # [GRPO] Repetition Penalty（先计算，后用于最终扣分）
        _rp = rep_penalty(v) if rep_penalty_val is None else rep_penalty_val
        _alpha = 0.3  # 惩罚强度超参（GRPO alpha）

        # 精确包含
        if e in v or v in e:
            return 1.0

        # 字符重叠 >= 60% → 高相似度
        if len(v) >= 4 and len(e) >= 4:
            common = sum(1 for c in v if c in e)
            if common / max(len(v), len(e)) >= 0.6:
                return 0.8

        # — 语义方向关键词 —
        cautious = {"谨慎", "慎重", "小心", "评估", "权衡", "考虑", "三思", "风险",
                    "谨慎考虑", "需评估", "不一定", "看情况", "取决于", "控制仓位",
                    "评估财务", "先", "先调研", "先了解", "先调查", "先评估", "先判断",
                    "先明确", "先确认", "先搞清楚", "不一定", "根据情况", "审慎",
                    "权衡后", "多维权衡", "不建议", "不建议做", "建议先", "可以先"}
        encourage = {"值得", "应该", "鼓励", "推荐", "支持", "值得做", "推荐做",
                     "可考虑", "可以"}
        discourage = {"不建议", "不要", "反对", "不应该", "不值得", "别", "不要做",
                     "不值得做"}

        def has_cautious(s):
            return any(p in s for p in cautious)

        def has_encourage(s):
            return any(p in s for p in encourage)

        def has_discourage(s):
            return any(p in s for p in discourage)

        def has_actionable(s):
            """有具体可操作建议（不只是模糊陈述）"""
            action_words = {
                "先", "再", "后", "应该", "可以", "不建议", "要", "不要",
                "控制", "分散", "比较", "衡量", "评估", "考虑", "权衡",
                "调研", "调查", "辞职", "创业", "借", "买房", "移民", "读研",
                "分手", "提前还", "买保险", "all in", "炒股", "考证",
                "考公", "健身", "断舍离", "领养", "换城市",
            }
            return any(p in s for p in action_words) or len(s) >= 10

        v_cautious = has_cautious(v)
        v_encourage = has_encourage(v) and not v_cautious
        v_discourage = has_discourage(v)
        e_cautious = has_cautious(e)
        e_encourage = has_encourage(e)
        e_discourage = has_discourage(e)

        # 方向分（最高 0.6）
        if v_cautious and e_cautious:
            direction_score = 0.6
        elif v_encourage and e_encourage:
            direction_score = 0.6
        elif v_discourage and e_discourage:
            direction_score = 0.5
        elif v_encourage and e_cautious:
            direction_score = 0.3
        elif v_cautious and e_encourage:
            direction_score = 0.3
        else:
            direction_score = 0.0

        # 可操作性分（0 or 0.2）
        actionable_score = 0.2 if has_actionable(v) else 0.0

        # 主题重叠分（2-gram + 3-gram，最高 0.2）
        def ngrams(s, n):
            return set(s[i:i+n] for i in range(len(s)-n+1))
        shared_2g = len(ngrams(v, 2) & ngrams(e, 2))
        shared_3g = len(ngrams(v, 3) & ngrams(e, 3))
        e_total = len(ngrams(e, 2)) + len(ngrams(e, 3))
        overlap_ratio = (shared_2g + shared_3g) / max(e_total, 1)
        topic_score = min(overlap_ratio * 0.2, 0.2)

        total = direction_score + actionable_score + topic_score
        # [GRPO] Repetition Penalty 扣分：verbose 判决降低得分
        penalized = total - _alpha * _rp
        return min(round(max(penalized, 0.0), 3), 1.0)

    def run_cases(self, case_ids: List[str]) -> BenchmarkReport:
        """运行指定 ID 的案例"""
        self.results = []
        for cid in case_ids:
            case = self._case_by_id.get(cid)
            if case:
                try:
                    self.results.append(self.run_case(case))
                except Exception as e:
                    log.error(f"[Benchmark] Case {cid} failed: {e}")
            else:
                log.warning(f"[Benchmark] Case not found: {cid}")
        return self._generate_report()

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
