#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
goal_system.py — 聚活目标系统
**独特核心技术（聚活独有）：洋葱时间锚定法**

普通目标管理都是从上到下拆解，容易"上有政策下有对策"，跑偏了自己不知道。
聚活独创**洋葱时间锚定法**：从五年锚定到今日，每一层都锚定在上一层关键词上：

1. **五年洋葱（核心）**：人生终极方向，关键词锁定（身份锁，很少变）
2. **年度洋葱**：今年要解决的核心问题，关键词必须对齐五年关键词
3. **月度洋葱**：本月要完成的里程碑，主题对齐年度目标
4. **周洋葱**：本周可执行任务，对齐月度里程碑
5. **今日洋葱**：今日优先级，对齐本周任务

**独特验证机制：洋葱一致性检查**
- 每个层级自动检查关键词对齐率 → 计算一致性得分
- 如果低一致性得分 → 自动提醒「你的当前任务可能偏离五年方向了」
- 从五年到今日，层层锚定，永远不跑偏

核心输出：给好奇心引擎提供对齐得分 → 影响探索优先级排序
核心问题：**我的五年方向是什么？当前任务对齐吗？**
"""

# 核心区别：不是只拆解，还要**自动一致性检查** → 提醒跑偏

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

_log = logging.getLogger("goal_system")
from pathlib import Path

# 文件路径
GOALS_FILE = Path(__file__).parent.parent / "goal_system" / "goals.json"


@dataclass
class FiveYearGoal:
    """五年目标"""
    description: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class AnnualGoal:
    """年度目标"""
    description: str
    keywords: List[str] = field(default_factory=list)
    progress: int = 0  # 0-100


@dataclass
class MonthlyMilestone:
    """月度里程碑"""
    description: str
    completed: bool = False


@dataclass
class WeeklyTask:
    """本周任务"""
    description: str
    completed: bool = False


@dataclass
class DailyPriority:
    """今日优先级"""
    description: str
    priority: int  # 1-5


@dataclass
class GoalSystem:
    """目标系统主类"""
    five_year: FiveYearGoal = None
    annual: AnnualGoal = None
    monthly: List[MonthlyMilestone] = field(default_factory=list)
    weekly: List[WeeklyTask] = field(default_factory=list)
    daily: List[DailyPriority] = field(default_factory=list)

    @classmethod
    def load_from_file(cls, path: Path = None) -> "GoalSystem":
        """从文件加载目标"""
        if path is None:
            path = GOALS_FILE
        
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        
        gs = cls()
        gs.five_year = FiveYearGoal(**data.get("five_year", {}))
        gs.annual = AnnualGoal(**data.get("annual", {}))
        gs.monthly = [MonthlyMilestone(**m) for m in data.get("monthly", [])]
        gs.weekly = [WeeklyTask(**t) for t in data.get("weekly", [])]
        gs.daily = [DailyPriority(**p) for p in data.get("daily", [])]
        return gs

    def save_to_file(self, path: Path = None):
        """保存到文件"""
        if path is None:
            path = GOALS_FILE
        
        data = {
            "five_year": {
                "description": self.five_year.description,
                "keywords": self.five_year.keywords,
            },
            "annual": {
                "description": self.annual.description,
                "keywords": self.annual.keywords,
                "progress": self.annual.progress,
            },
            "monthly": [
                {"description": m.description, "completed": m.completed}
                for m in self.monthly
            ],
            "weekly": [
                {"description": t.description, "completed": t.completed}
                for t in self.weekly
            ],
            "daily": [
                {"description": p.description, "priority": p.priority}
                for p in self.daily
            ],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def calculate_alignment_score(self, topic: str) -> float:
        """
        聚活独特：计算话题和长期目标的对齐得分（0-1）
        按洋葱层级加权：五年(50%) + 年度(30%) + 月度(15%) + 周/日(5%)
        """
        score = 0.0
        topic_lower = topic.lower()
        import difflib

        # 五年目标关键词匹配（权重最高，50%）
        if self.five_year and self.five_year.keywords:
            max_sim = max(
                difflib.SequenceMatcher(None, topic_lower, kw.lower()).ratio()
                for kw in self.five_year.keywords
            )
            score += 0.5 * max_sim

        # 年度目标关键词匹配（30%）
        if self.annual and self.annual.keywords:
            max_sim = max(
                difflib.SequenceMatcher(None, topic_lower, kw.lower()).ratio()
                for kw in self.annual.keywords
            )
            score += 0.3 * max_sim

        # 检查月度是否在做相关事情（15%）
        if self.monthly:
            max_sim = max(
                difflib.SequenceMatcher(None, topic_lower, m.description.lower()).ratio()
                for m in self.monthly if not m.completed
            ) if self.monthly else 0
            score += 0.15 * max_sim

        return min(score, 1.0)


    def check_onion_consistency(self) -> Dict:
        """
        聚活独特技术：洋葱一致性检查 → 检查所有层级关键词是否对上
        返回 {
            "consistency_score": 0-1 总体一致性,
            "warnings": [str] 不一致警告列表,
            "level_scores": {level: score}
        }
        """
        level_scores = {}
        warnings = []

        # 第一层：五年目标 → 关键词必须存在（五年都没关键词，锚定失效）
        if not self.five_year or not self.five_year.keywords or len(self.five_year.keywords) == 0:
            warnings.append("⚠️ 五年目标没有定义关键词，无法锚定方向")
            level_scores["five_year"] = 0.0
        else:
            level_scores["five_year"] = 1.0

        # 第二层：年度关键词对齐五年关键词 → 至少一个匹配
        if self.annual and self.annual.keywords and self.five_year and self.five_year.keywords:
            matched = False
            for a_kw in self.annual.keywords:
                a_lower = a_kw.lower()
                for f_kw in self.five_year.keywords:
                    f_lower = f_kw.lower()
                    sim = difflib.SequenceMatcher(None, a_lower, f_lower).ratio()
                    if sim > 0.3 or a_lower in f_lower or f_lower in a_lower:
                        matched = True
                        break
            if not matched:
                warnings.append("⚠️ 年度目标关键词没有匹配到五年目标关键词，可能偏离方向")
            level_scores["annual"] = 1.0 if matched else 0.5
        else:
            level_scores["annual"] = 0.5

        # 第三层：月度里程碑对齐年度关键词 → 至少一个匹配
        if self.annual and self.annual.keywords and self.monthly:
            mismatched_count = 0
            for m in self.monthly:
                matched = False
                m_lower = m.description.lower()
                for a_kw in self.annual.keywords:
                    a_lower = a_kw.lower()
                    sim = difflib.SequenceMatcher(None, m_lower, a_lower).ratio()
                    if sim > 0.2 or a_lower in m_lower or m_lower in a_lower:
                        matched = True
                        break
                if not matched:
                    mismatched_count += 1
            if mismatched_count > len(self.monthly) / 2:
                warnings.append(f"⚠️ {mismatched_count}/{len(self.monthly)} 个月度里程碑不匹配年度目标，可能跑偏")
            level_scores["monthly"] = 1.0 - (mismatched_count / max(1, len(self.monthly))) / 2
        else:
            level_scores["monthly"] = 1.0

        # 计算总分
        weights = {"five_year": 0.5, "annual": 0.3, "monthly": 0.2}
        total_score = sum(
            level_scores[level] * weights[level]
            for level in weights
        )

        return {
            "consistency_score": total_score,
            "level_scores": level_scores,
            "warnings": warnings,
        }

    def get_daily_priorities(self) -> List[DailyPriority]:
        """获取今日优先级排序"""
        return sorted(self.daily, key=lambda x: -x.priority)

    def mark_weekly_completed(self, index: int) -> bool:
        """标记周任务完成"""
        if 0 <= index < len(self.weekly):
            self.weekly[index].completed = True
            self.save_to_file()
            return True
        return False

    def format_goals(self) -> str:
        """格式化输出目标结构，人类可读"""
        lines = ["=== 目标系统 ===\n"]

        lines.append(f"📌 五年目标：{self.five_year.description}")
        if self.five_year.keywords:
            lines.append(f"关键词：{', '.join(self.five_year.keywords)}\n")

        lines.append(f"🎯 年度目标：{self.annual.description}")
        lines.append(f"进度：{self.annual.progress}%")
        if self.annual.keywords:
            lines.append(f"关键词：{', '.join(self.annual.keywords)}\n")

        if self.monthly:
            lines.append("🗓️  月度里程碑：")
            for idx, m in enumerate(self.monthly, 1):
                check = "✅" if m.completed else "⬜"
                lines.append(f"  {check} {idx}. {m.description}")
            lines.append("")

        if self.weekly:
            lines.append("📋 本周任务：")
            for idx, t in enumerate(self.weekly, 1):
                check = "✅" if t.completed else "⬜"
                lines.append(f"  {check} {idx}. {t.description}")
            lines.append("")

        if self.daily:
            lines.append("🔝 今日优先级：")
            daily_sorted = self.get_daily_priorities()
            for idx, p in enumerate(daily_sorted, 1):
                stars = "⭐" * p.priority
                lines.append(f"  {stars} {idx}. {p.description}")

        return "\n".join(lines)


def format_hierarchy(gs: GoalSystem) -> str:
    """格式化输出完整目标层级，供网页控制台使用"""
    return gs.format_goals()


# 单例
_goal_system_instance = None


def notify_self_model_update(bias_dimension: str, bias_description: str, confidence: float, is_new: bool = True):
    """
    空链修复：Self-Model → Goal System
    当自我模型发现新偏差或高置信度偏差时，通知目标系统建议调整目标。
    
    例如：发现"temporal"维度频繁失误 → 建议添加"改善时间管理"的目标
    """
    try:
        gs = get_goal_system()
        # 高置信度偏差（>=0.6）→ 建议添加对齐目标
        if confidence >= 0.6:
            suggestion = _build_bias_goal_suggestion(bias_dimension, bias_description)
            if suggestion:
                _log.info(f"[GoalSystem] 收到自我模型偏差通知: {bias_dimension} (置信度={confidence:.2f})")
                # 将建议追加到目标文件（人工确认后可激活）
                _append_goal_suggestion(suggestion)
    except Exception as e:
        _log.debug(f"[GoalSystem] 自我模型通知跳过: {e}")


def _build_bias_goal_suggestion(dim: str, desc: str) -> Optional[dict]:
    """根据偏差维度生成目标建议"""
    goal_templates = {
        "temporal": {
            "description": f"改善时间管理能力（{desc}）",
            "keywords": ["时间管理", "deadline", "长期规划"],
            "type": "annual",
        },
        "emotional": {
            "description": f"提升情绪管理能力（{desc}）",
            "keywords": ["情绪", "压力", "心态"],
            "type": "annual",
        },
        "cognitive": {
            "description": f"增强认知分析能力（{desc}）",
            "keywords": ["认知", "分析", "信息处理"],
            "type": "annual",
        },
        "moral": {
            "description": f"完善价值观判断（{desc}）",
            "keywords": ["道德", "价值观", "伦理"],
            "type": "five_year",
        },
    }
    template = goal_templates.get(dim)
    if not template:
        template = {
            "description": f"改善{dim}维度判断能力（{desc}）",
            "keywords": [dim, "判断力", "能力提升"],
            "type": "annual",
        }
    return template


def _append_goal_suggestion(suggestion: dict):
    """将目标建议追加到待确认列表"""
    suggestions_file = Path(__file__).parent / "goal_suggestions.json"
    suggestions = []
    if suggestions_file.exists():
        try:
            suggestions = json.loads(suggestions_file.read_text(encoding="utf-8"))
        except Exception:
            suggestions = []
    # 去重
    for s in suggestions:
        if s.get("description") == suggestion.get("description"):
            return
    suggestions.append(suggestion)
    suggestions_file.write_text(json.dumps(suggestions, ensure_ascii=False, indent=2), encoding="utf-8")

    # 空链修复：Goal System → Curiosity
    # 新目标建议 → 触发好奇心引擎探索实现路径
    try:
        from curiosity.curiosity_engine import trigger_from_goal
        goal_desc = suggestion.get("description", "")
        trigger_from_goal(goal_desc, suggestion.get("keywords"))
        _log.info(f"[GoalSystem] 触发好奇心探索: {goal_desc[:50]}")
    except Exception as e:
        _log.debug(f"[GoalSystem] 好奇心触发跳过: {e}")


def get_goal_system() -> GoalSystem:
    """获取目标系统单例"""
    global _goal_system_instance
    if _goal_system_instance is None:
        _goal_system_instance = GoalSystem.load_from_file()
    return _goal_system_instance


if __name__ == "__main__":
    gs = get_goal_system()
    print(gs.format_goals())
