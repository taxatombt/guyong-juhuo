#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_evolver.py — Skill 自我进化

核心闭环：
1. 追踪 Skill 使用 → 记录成功率
2. 识别低效 Skill → 调整触发条件
3. 合并相似 Skill → 减少冗余
4. 生成进化建议 → 人工确认后应用
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict

from judgment.logging_config import get_logger
log = get_logger("juhuo.skill_evolver")


# 配置
ANALYTICS_FILE = Path(__file__).parent.parent / "data" / "skills" / "skill_analytics.jsonl"
SKILL_SUGGESTIONS_FILE = Path(__file__).parent.parent / "data" / "skills" / "evolution_suggestions.json"
MIN_USAGE_FOR_EVOLUTION = 10
SUCCESS_RATE_THRESHOLD = 0.3


@dataclass
class SkillExecution:
    skill_name: str
    timestamp: str
    task: str
    triggered_by: str
    success: bool
    error: str = ""


@dataclass
class SkillStats:
    name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    success_rate: float = 0.0
    last_used: str = ""


@dataclass
class EvolutionSuggestion:
    skill_name: str
    suggestion_type: str
    reason: str
    current_value: str
    suggested_value: str
    confidence: float
    created_at: str
    status: str = "pending"


def record_execution(skill_name: str, task: str, triggered_by: str, success: bool, error: str = "") -> None:
    """记录一次 Skill 执行"""
    ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = SkillExecution(
        skill_name=skill_name,
        timestamp=datetime.now().isoformat(),
        task=task,
        triggered_by=triggered_by,
        success=success,
        error=error
    )
    with open(ANALYTICS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    log.info(f"Recorded: {skill_name} -> {success}")


def get_skill_stats(skill_name: str) -> SkillStats:
    """获取单个 Skill 的统计"""
    stats = SkillStats(name=skill_name)
    if not ANALYTICS_FILE.exists():
        return stats
    executions = []
    with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    if data["skill_name"] == skill_name:
                        executions.append(data)
                except:
                    continue
    if not executions:
        return stats
    stats.total_executions = len(executions)
    stats.successful_executions = sum(1 for e in executions if e["success"])
    stats.failed_executions = sum(1 for e in executions if not e["success"])
    stats.success_rate = stats.successful_executions / stats.total_executions
    stats.last_used = executions[-1]["timestamp"]
    return stats


def get_all_stats() -> Dict[str, SkillStats]:
    """获取所有 Skill 的统计"""
    all_stats = {}
    if not ANALYTICS_FILE.exists():
        return all_stats
    skill_data = defaultdict(list)
    with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    skill_data[data["skill_name"]].append(data)
                except:
                    continue
    for skill_name, executions in skill_data.items():
        stats = SkillStats(name=skill_name)
        stats.total_executions = len(executions)
        stats.successful_executions = sum(1 for e in executions if e["success"])
        stats.failed_executions = sum(1 for e in executions if not e["success"])
        stats.success_rate = stats.successful_executions / stats.total_executions if executions else 0
        stats.last_used = executions[-1]["timestamp"] if executions else ""
        all_stats[skill_name] = stats
    return all_stats


def analyze_skill(skill_name: str) -> List[EvolutionSuggestion]:
    """分析单个 Skill，生成进化建议"""
    from skills.skill_registry import SkillRegistry
    suggestions = []
    stats = get_skill_stats(skill_name)
    if stats.total_executions < MIN_USAGE_FOR_EVOLUTION:
        return suggestions
    registry = SkillRegistry()
    skill_def = registry.get(skill_name)
    if not skill_def:
        return suggestions
    if stats.success_rate < SUCCESS_RATE_THRESHOLD:
        suggestions.append(EvolutionSuggestion(
            skill_name=skill_name,
            suggestion_type="adjust_trigger",
            reason=f"成功率 {stats.success_rate:.0%} 低于阈值 {SUCCESS_RATE_THRESHOLD:.0%}",
            current_value=skill_def.get("when_to_use", ""),
            suggested_value=f"Review: {skill_def.get('when_to_use', '')}",
            confidence=0.7,
            created_at=datetime.now().isoformat()
        ))
    return suggestions


def find_similar_skills() -> List[Tuple[str, str, float]]:
    """找出可以合并的相似 Skill"""
    from skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    skills = registry.list_all()
    similar = []
    for i, s1 in enumerate(skills):
        for s2 in skills[i+1:]:
            desc1 = s1.get("description", "").lower()
            desc2 = s2.get("description", "").lower()
            words1 = set(desc1.split())
            words2 = set(desc2.split())
            if words1 and words2:
                overlap = len(words1 & words2) / len(words1 | words2)
                if overlap > 0.5:
                    similar.append((s1["name"], s2["name"], overlap))
    return similar


def generate_suggestions() -> List[EvolutionSuggestion]:
    """分析所有 Skill，生成进化建议"""
    log.info("Starting skill evolution analysis")
    suggestions = []
    all_stats = get_all_stats()
    for skill_name in all_stats:
        suggestions.extend(analyze_skill(skill_name))
    similar = find_similar_skills()
    for s1, s2, overlap in similar:
        suggestions.append(EvolutionSuggestion(
            skill_name=f"{s1} <-> {s2}",
            suggestion_type="merge",
            reason=f"相似度 {overlap:.0%}，建议合并",
            current_value=f"{s1}, {s2}",
            suggested_value=f"merged_{s1}",
            confidence=overlap,
            created_at=datetime.now().isoformat()
        ))
    SKILL_SUGGESTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SKILL_SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump([asdict(s) for s in suggestions], f, ensure_ascii=False, indent=2)
    log.info(f"Generated {len(suggestions)} suggestions")
    return suggestions


def apply_suggestion(suggestion: EvolutionSuggestion) -> bool:
    """应用进化建议"""
    from skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    if suggestion.suggestion_type == "adjust_trigger":
        skill = registry.get(suggestion.skill_name)
        if skill:
            skill["when_to_use"] = suggestion.suggested_value
            registry.update(suggestion.skill_name, skill)
            log.info(f"Updated trigger for {suggestion.skill_name}")
            return True
    return False


def format_suggestions_report() -> str:
    """生成进化报告"""
    suggestions = []
    if SKILL_SUGGESTIONS_FILE.exists():
        with open(SKILL_SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
            suggestions = [EvolutionSuggestion(**s) for s in json.load(f)]
    if not suggestions:
        return "✅ 没有进化建议，Skill 系统运行良好"
    lines = [f"## Skill 进化建议（共 {len(suggestions)} 条）\n"]
    for s in suggestions:
        emoji = {"adjust_trigger": "🎯", "merge": "🔀", "deprecate": "🗑️"}.get(s.suggestion_type, "📝")
        lines.append(f"\n### {emoji} {s.skill_name}")
        lines.append(f"- 类型: {s.suggestion_type}")
        lines.append(f"- 原因: {s.reason}")
        lines.append(f"- 置信度: {s.confidence:.0%}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--analyze":
            suggestions = generate_suggestions