"""
execution_analyzer.py —— 执行日志分析 → 生成进化建议

基于 OpenSpace 设计：从 action_log 读取执行记录 → 分析技能成功率 → 生成进化建议
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from openspace_evolution import (
    EvolutionType,
    SkillLineage,
    SkillMetrics,
    load_skill_db,
    suggest_evolution,
    SKILL_DB_PATH,
)


@dataclass
class ExecutionRecord:
    """Single execution record from action_log"""
    timestamp: str
    skill_id: str
    skill_name: str
    success: bool
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: Optional[dict] = None


class ExecutionAnalyzer:
    """
    Analyze execution logs and update skill metrics → generate evolution suggestions
    """

    def __init__(
        self,
        action_log_path: Path = None,
        skill_db_path: Path = SKILL_DB_PATH,
        success_rate_threshold: float = 0.5,
        min_applications: int = 3,
    ):
        self.action_log_path = action_log_path or Path(__file__).parent / "action_log.jsonl"
        self.skill_db_path = skill_db_path
        self.success_rate_threshold = success_rate_threshold
        self.min_applications = min_applications

    def load_execution_records(self) -> List[ExecutionRecord]:
        """Load all execution records from action_log.jsonl"""
        records = []
        if not self.action_log_path.exists():
            return records

        with open(self.action_log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    rec = ExecutionRecord(
                        timestamp=data.get("timestamp", ""),
                        skill_id=data.get("skill_id", ""),
                        skill_name=data.get("skill_name", ""),
                        success=data.get("success", False),
                        error=data.get("error"),
                        duration_ms=data.get("duration_ms"),
                        metadata=data.get("metadata"),
                    )
                    records.append(rec)
                except json.JSONDecodeError:
                    continue
        return records

    def aggregate_by_skill(self, records: List[ExecutionRecord]) -> Dict[str, Tuple[int, int]]:
        """Aggregate (total, success) by skill_id"""
        agg = {}
        for rec in records:
            sid = rec.skill_id
            if sid not in agg:
                agg[sid] = (0, 0)
            total, success = agg[sid]
            total += 1
            if rec.success:
                success += 1
            agg[sid] = (total, success)
        return agg

    def update_skill_metrics(self) -> int:
        """
        Update skill metrics from execution records
        Returns number of updated skills
        """
        records = self.load_execution_records()
        if not records:
            return 0

        agg = self.aggregate_by_skill(records)
        db = load_skill_db(self.skill_db_path)
        updated = 0

        for sid, (total, success) in agg.items():
            if sid in db:
                node = db[sid]
                # Add to existing metrics
                # We add the delta from log since last update
                # Simple approach: just overwrite with aggregated from log
                # More advanced: incremental update
                node.metrics.applied_count = total
                node.metrics.success_count = success
                node.metrics.failed_count = total - success
                updated += 1

        if updated > 0:
            from .openspace_evolution import save_skill_db
            save_skill_db(self.skill_db_path, db)

        return updated

    def get_low_success_skills(self) -> List[Tuple[SkillLineage, float]]:
        """Find skills with success_rate below threshold"""
        db = load_skill_db(self.skill_db_path)
        result = []
        for node in db.values():
            if not node.is_active:
                continue
            if node.metrics.applied_count >= self.min_applications:
                rate = node.metrics.success_rate
                if rate < self.success_rate_threshold:
                    result.append((node, rate))
        return sorted(result, key=lambda x: x[1])

    def generate_evolution_suggestions(self) -> str:
        """Generate human-readable evolution suggestions"""
        self.update_skill_metrics()
        low_success = self.get_low_success_skills()
        suggestions = suggest_evolution(load_skill_db(self.skill_db_path))

        lines = ["# 执行分析进化建议", ""]
        lines.append(f"分析了 {len(low_success) + len([s for s in suggestions if s['depends_on_changed']])} 待改进技能")
        lines.append("")

        if low_success:
            lines.append("## 低成功率技能（需要 FIX 进化）")
            lines.append("")
            for node, rate in low_success:
                lines.append(f"- **{node.skill_id}**: {rate:.1%} 成功 ({node.metrics.success_count}/{node.metrics.applied_count})")
                lines.append(f"  → 建议: {EvolutionType.FIX.value} 就地修正")
            lines.append("")

        cascade = [s for s in suggestions if s["depends_on_changed"]]
        if cascade:
            lines.append("## 依赖变更需要重新验证")
            lines.append("")
            for s in cascade:
                lines.append(f"- **{s['skill_id']}**: 基础技能已改变，需要重新验证")
                lines.append(f"  → 建议: {s['evolution_type'].value}")
            lines.append("")

        if not low_success and not cascade:
            lines.append("✅ 所有技能成功率正常，没有待进化项目")
            lines.append("")

        return "\n".join(lines)

    def print_summary(self):
        """Print summary to console"""
        records = self.load_execution_records()
        agg = self.aggregate_by_skill(records)
        print(f"Loaded {len(records)} execution records")
        print(f"Aggregated to {len(agg)} skills")
        low = self.get_low_success_skills()
        print(f"Found {len(low)} skills below {self.success_rate_threshold:.0%} threshold")
        for node, rate in low[:10]:
            print(f"  {node.skill_id}: {rate:.1%}")
        if len(low) > 10:
            print(f"  ... and {len(low) - 10} more")
