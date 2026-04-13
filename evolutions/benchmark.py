#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GDPVal Benchmark — Phase 1 vs Phase 2 效果衡量

衡量 Skill 进化带来的实际收益：
- Token 节省率
- 完成率变化
- 速度变化

用于判断进化是否有数据支撑，避免玄学进化。
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any


PROJECT_ROOT = Path(__file__).parent.parent
METRICS_DIR = PROJECT_ROOT / "data" / "metrics"


# ─── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class PhaseResult:
    """单次运行结果。"""
    task_id: str
    tokens: int
    completion_rate: float       # 0.0 ~ 1.0
    duration_ms: int
    success: bool
    error: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Benchmark 对比结果。"""
    task_set_name: str
    p1: PhaseResult          # 冷启动（无 skill）
    p2: PhaseResult          # 热启动（有 skill）

    @property
    def token_savings_pct(self) -> float:
        if self.p1.tokens == 0:
            return 0.0
        return (self.p1.tokens - self.p2.tokens) / self.p1.tokens

    @property
    def completion_rate_change(self) -> float:
        return self.p2.completion_rate - self.p1.completion_rate

    @property
    def speed_change_pct(self) -> float:
        if self.p1.duration_ms == 0:
            return 0.0
        return (self.p1.duration_ms - self.p2.duration_ms) / self.p1.duration_ms

    def to_dict(self) -> dict:
        return {
            "task_set_name": self.task_set_name,
            "p1": asdict(self.p1),
            "p2": asdict(self.p2),
            "token_savings_pct": round(self.token_savings_pct, 4),
            "completion_rate_change": round(self.completion_rate_change, 4),
            "speed_change_pct": round(self.speed_change_pct, 4),
            "judgment": self._judgment(),
        }

    def _judgment(self) -> str:
        savings = self.token_savings_pct
        completion = self.completion_rate_change
        speed = self.speed_change_pct

        if completion < 0:
            return "退步：完成率下降，不建议使用"
        if completion == 0 and savings < 0.05 and speed < 0.05:
            return "无效：收益不明显"
        if savings > 0.1 or speed > 0.2:
            return "有效：Skill 带来明显收益"
        return "有效：Skill 带来一定收益"


# ─── Task Runner ─────────────────────────────────────────────────────────────

class BaseRunner:
    """任务运行器基类。子类化实现真实 Agent 调用。"""

    def run(self, task_id: str, task_text: str, skills: List[str]) -> PhaseResult:
        raise NotImplementedError


class SimulatedRunner(BaseRunner):
    """
    模拟运行器（用于测试/演示）。
    真实使用时子类化 BaseRunner 实现真实 Agent 调用。
    """

    def run(self, task_id: str, task_text: str, skills: List[str]) -> PhaseResult:
        has_skill = len(skills) > 0

        if has_skill:
            tokens = 800
            completion = 0.92
            duration_ms = 3200
        else:
            tokens = 1200
            completion = 0.75
            duration_ms = 5500

        time.sleep(0.05)
        return PhaseResult(
            task_id=task_id,
            tokens=tokens,
            completion_rate=completion,
            duration_ms=duration_ms,
            success=completion > 0.5,
        )


# ─── Benchmark 主类 ──────────────────────────────────────────────────────────

class EvolutionMetrics:
    """
    GDPVal Benchmark 核心类。

    用法：
        bm = EvolutionMetrics(runner=MyRunner())

        # 方式1：直接对比两个 phase
        result = bm.compare(
            task_id="flutter_app",
            task_text="做一个九九乘法表 Flutter App",
            skills_p1=[],           # 冷启动
            skills_p2=["flutter"],  # 热启动
        )
        print(result.token_savings_pct)

        # 方式2：运行任务集
        results = bm.run_task_set(
            name="my_tasks",
            tasks=[{"id": "t1", "text": "..."}],
        )
        bm.save_results(results)
    """

    def __init__(
        self,
        runner: Optional[BaseRunner] = None,
        output_dir: Path = METRICS_DIR,
    ):
        self.runner = runner or SimulatedRunner()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── 核心方法 ─────────────────────────────────────────────────────────

    def compare(
        self,
        task_id: str,
        task_text: str,
        skills_p1: List[str],
        skills_p2: List[str],
    ) -> BenchmarkResult:
        """
        对比同一个任务在两个 phase 下的表现。
        """
        p1_result = self.runner.run(task_id, task_text, skills_p1)
        p2_result = self.runner.run(task_id, task_text, skills_p2)

        return BenchmarkResult(
            task_set_name=task_id,
            p1=p1_result,
            p2=p2_result,
        )

    def run_task_set(
        self,
        name: str,
        tasks: List[Dict[str, str]],
        skills_p1: List[str] = [],
        skills_p2: List[str] = [],
    ) -> List[BenchmarkResult]:
        """
        运行一组任务，对比 Phase 1 vs Phase 2。
        """
        results: List[BenchmarkResult] = []

        for task in tasks:
            result = self.compare(
                task_id=task["id"],
                task_text=task["text"],
                skills_p1=skills_p1,
                skills_p2=skills_p2,
            )
            results.append(result)

        return results

    # ── 汇总报告 ─────────────────────────────────────────────────────────

    def aggregate(self, results: List[BenchmarkResult]) -> Dict[str, Any]:
        """将多次结果汇总为统计报告。"""
        if not results:
            return {}

        n = len(results)
        total_token_savings = sum(r.token_savings_pct for r in results)
        total_completion_change = sum(r.completion_rate_change for r in results)
        total_speed_change = sum(r.speed_change_pct for r in results)

        # 统计有效/退步/无效
        judgments = [r._judgment() for r in results]
        effective = sum(1 for j in judgments if "有效" in j)
        regressed = sum(1 for j in judgments if "退步" in j)
        neutral = sum(1 for j in judgments if "无效" in j)

        avg_token_savings = total_token_savings / n
        avg_completion = total_completion_change / n
        avg_speed = total_speed_change / n

        return {
            "task_count": n,
            "avg_token_savings_pct": round(avg_token_savings, 4),
            "avg_completion_rate_change": round(avg_completion, 4),
            "avg_speed_change_pct": round(avg_speed, 4),
            "effective": effective,
            "regressed": regressed,
            "neutral": neutral,
            "overall": (
                "推荐" if effective > regressed and avg_token_savings > 0
                else "不推荐" if regressed > effective
                else "待观察"
            ),
            "per_task": [r.to_dict() for r in results],
        }

    # ── 持久化 ───────────────────────────────────────────────────────────

    def save_results(
        self,
        results: List[BenchmarkResult],
        filename: Optional[str] = None,
    ) -> Path:
        """保存结果到 JSON 文件。"""
        if filename is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_{ts}.json"

        output_path = self.output_dir / filename
        agg = self.aggregate(results)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(agg, f, ensure_ascii=False, indent=2)

        return output_path

    def load_results(self, filename: str) -> Dict[str, Any]:
        """加载之前保存的结果。"""
        path = self.output_dir / filename
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# ─── 演示 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bm = EvolutionMetrics()

    tasks = [
        {"id": "flutter_multiply", "text": "做一个九九乘法表 Flutter App"},
        {"id": "api_backend", "text": "用 FastAPI 写一个 Todo API"},
        {"id": "react_kanban", "text": "用 React 写一个看板前端"},
        {"id": "golang_cli", "text": "用 Go 写一个文件压缩 CLI"},
    ]

    # Phase 1: 无 skill | Phase 2: 有 skill
    results = bm.run_task_set(
        name="phase1_vs_phase2",
        tasks=tasks,
        skills_p1=[],             # 冷启动
        skills_p2=["flutter", "fastapi", "react", "golang"],  # 热启动
    )

    # 打印汇总
    report = bm.aggregate(results)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # 保存
    saved = bm.save_results(results)
    print(f"\n结果已保存: {saved}")
