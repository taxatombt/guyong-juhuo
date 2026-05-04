#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
action_system.py — 聚活行动规划系统
**独特核心技术（聚活独有）：四象限时间压强排序**

普通行动规划只是拆解任务，分分类就完了。聚活不是：

把所有行动放到 **时间 × 重要性** 四象限，然后计算**时间压强得分**：
1. **重要 × 紧急（第一象限）** → 得分 = 重要性得分 × (1 + 1/days_to_deadline)
   → 越紧急压强越大，排第一
2. **重要 × 不紧急（第二象限）** → 得分 = 重要性得分 × 0.5（但接近deadline压强也会涨）
   → 这才是真正决定长期成长的象限，聚活保证它不被遗忘
3. **不重要 × 紧急（第三象限）** → 得分 = 重要性得分低，但紧急涨分 → 提示是否可以委托
4. **不重要 × 不紧急（第四象限）** → 直接放最后，或者建议删掉

**独特设计：时间压强公式**：
```
score = importance × (1 + 1 / max(days_to_deadline, 1)) × 100
```
- deadline越近 → 1/days越大 → 压强越大 → 排越前
- 重要性越高 → 基础分越高 → 即使不紧急也排在不重要紧急前面
- 自动计算，不用手动排，省得你纠结"先做哪个"

核心问题：**决定了之后，怎么变成实际行动？下一步先做哪个？**
- 不只拆解，还给你**算出来先做什么**，不用你纠结优先级
- 完成后自动回流因果记忆 → 下次判断更准
"""

# 核心区别：不只拆解，还帮你用「时间压强」自动排序 → 解决"先做哪个"的选择困难

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

# 文件路径
ACTION_LOG_FILE = Path(__file__).parent.parent / "action_log.jsonl"


@dataclass
class NextAction:
    """一条下一步行动"""
    action_id: int
    description: str
    importance: int  # 1-5，重要性：5最重要，1最不重要
    related_question: str  # 来自判断里的哪个问题
    created_at: str
    deadline: Optional[str] = None  # 截止日期 ISO 格式，None 代表没有硬截止
    completed: bool = False
    result: str = ""  # 完成后的结果

    def to_dict(self):
        return {
            "action_id": self.action_id,
            "description": self.description,
            "importance": self.importance,
            "deadline": self.deadline,
            "related_question": self.related_question,
            "created_at": self.created_at,
            "completed": self.completed,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

    def calculate_time_pressure_score(self) -> float:
        """
        聚活独特技术：计算时间压强得分
        score = importance × (1 + 1 / max(days_to_deadline, 1)) × 100
        - importance: 1-5，越高越重要
        - days_to_deadline: 截止日期距离今天的天数，越近分数越高
        - 没有截止日期 → days = 30 → 1/30 ≈ 0.03 → 得分就是 importance × 1.03
        - 得分越高越先做
        """
        if self.deadline is None:
            days = 30  # 没有截止默认按一个月算，压强最低
        else:
            try:
                deadline_dt = datetime.fromisoformat(self.deadline)
                days = (deadline_dt - datetime.now()).days
                if days <= 0:
                    days = 1  # 今天截止，压强最大，1/1 = 1
            except:
                days = 30
        
        pressure_multiplier = 1 + 1 / max(days, 1)
        score = self.importance * pressure_multiplier * 100
        return score

    def get_quadrant(self) -> str:
        """
        聚活四象限分类：
        返回 "I" / "II" / "III" / "IV"
        - I: 重要 (≥4) × 紧急 (≤7天) → 立即做
        - II: 重要 (≥4) × 不紧急 (>7天) → 计划做，长期成长关键
        - III: 不重要 (<4) × 紧急 (≤7天) → 考虑委托
        - IV: 不重要 (<4) × 不紧急 (>7天) → 最后做或删掉
        """
        is_important = self.importance >= 4
        if self.deadline is None:
            is_urgent = False
        else:
            try:
                deadline_dt = datetime.fromisoformat(self.deadline)
                days = (deadline_dt - datetime.now()).days
                is_urgent = days <= 7
            except:
                is_urgent = False
        
        if is_important and is_urgent:
            return "I"
        elif is_important and not is_urgent:
            return "II"
        elif not is_important and is_urgent:
            return "III"
        else:
            return "IV"


@dataclass
class ActionPlan:
    """完整行动计划"""
    judgment_task: str          # 关联的判断任务
    judgment_id: str            # 关联判断ID（时间戳）
    actions: List[NextAction]    # 下一步行动列表
    created_at: str
    completed_count: int = 0
    total_count: int = 0

    def to_dict(self):
        return {
            "judgment_task": self.judgment_task,
            "judgment_id": self.judgment_id,
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at,
            "completed_count": self.completed_count,
            "total_count": self.total_count,
        }


def _next_action_id() -> int:
    """生成下一个行动ID"""
    plans = load_all_plans()
    if not plans:
        return 1
    max_id = 0
    for plan in plans:
        for action in plan.get("actions", []):
            if action.get("action_id", 0) > max_id:
                max_id = action["action_id"]
    return max_id + 1


def load_all_plans() -> List[Dict]:
    """加载所有行动计划"""
    if not ACTION_LOG_FILE.exists():
        return []
    
    plans = []
    with open(ACTION_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    item = json.loads(line)
                    plans.append(item)
                except:
                    continue
    return plans


def load_all_actions() -> List[Dict]:
    """加载所有行动（展开所有计划）"""
    plans = load_all_plans()
    actions = []
    for plan in plans:
        for action in plan.get("actions", []):
            action["judgment_task"] = plan["judgment_task"]
            actions.append(action)
    return actions


def sort_actions_by_time_pressure(actions: List[NextAction]) -> List[NextAction]:
    """
    聚活独特技术：按时间压强得分排序 → 越高越先做
    同时保留四象限分组信息
    """
    # 计算每个行动的得分
    for action in actions:
        action.time_pressure_score = action.calculate_time_pressure_score()
    
    # 按得分降序
    actions.sort(key=lambda a: -getattr(a, 'time_pressure_score', 0))
    return actions


def generate_action_plan(judgment_result: Dict, importance_default: int = 3) -> ActionPlan:
    """
    从判断结果生成行动计划：
    - 从每个必须检查维度的回答里提取行动
    - 自动分配重要性（默认3，可以手动调整）
    - 按时间压强自动排序
    """
    task = judgment_result["original_task"]
    jid = datetime.now().strftime("%Y%m%d%H%M")
    actions = []
    aid = _next_action_id()
    
    # 遍历所有必须检查的维度
    must_check = judgment_result.get("must_check", [])
    questions = judgment_result.get("questions", {})
    answers = judgment_result.get("answers", {})
    
    for dim_id in must_check:
        dim_questions = questions.get(dim_id, [])
        for q in dim_questions:
            # 如果已经回答，从回答提取行动
            answer = answers.get(dim_id, {}).get(q, "")
            action_desc, imp, deadline = _question_to_action(q, answer, importance_default)
            if action_desc:
                actions.append(NextAction(
                    action_id=aid,
                    description=action_desc,
                    importance=imp,
                    deadline=deadline,
                    related_question=q,
                    created_at=datetime.now().isoformat(),
                ))
                aid += 1
    
    # 如果没有提取到行动，默认生成一个整理结论
    if not actions:
        actions.append(NextAction(
            action_id=aid,
            description="整理所有维度分析，做出最终判断和选择",
            importance=5,
            deadline=None,
            related_question="最终结论",
            created_at=datetime.now().isoformat(),
        ))
    
    # 聚活独特：按时间压强自动排序
    actions = sort_actions_by_time_pressure(actions)
    
    plan = ActionPlan(
        judgment_task=task,
        judgment_id=jid,
        actions=actions,
        created_at=datetime.now().isoformat(),
        total_count=len(actions),
        completed_count=0,
    )
    
    # 保存计划
    save_action_plan(plan)
    return plan


def _question_to_action(question: str, answer: str, default_imp: int) -> Tuple[str, int, Optional[str]]:
    """把问题+回答转换成行动描述，推断重要性和截止日期"""
    import re
    importance = default_imp
    deadline = None
    
    # 提取截止日期（识别 "今天/明天/周内/月底" 转成ISO）
    today = datetime.now()
    lower_q = question.lower()
    
    if "今天" in lower_q or "now" in lower_q:
        deadline = today.isoformat()
        importance = max(importance, 4)
    elif "明天" in lower_q:
        deadline = (today + timedelta(days=1)).isoformat()
        importance = max(importance, 4)
    elif "本周" in lower_q:
        deadline = (today + timedelta(days=7 - today.weekday())).isoformat()
        importance = max(importance, 3)
    elif "月底" in lower_q:
        # 到下个月第一天减一天
        if today.month == 12:
            next_month = datetime(today.year + 1, 1, 1)
        else:
            next_month = datetime(today.year, today.month + 1, 1)
        deadline = (next_month - timedelta(days=1)).isoformat()
        importance = max(importance, 3)
    
    # 提取重要性标记 "优先级高/低"
    if "高优先级" in lower_q or "重要" in lower_q and "不" not in lower_q:
        importance = 5
    elif "低优先级" in lower_q or "不重要" in lower_q:
        importance = 2
    
    if not answer:
        # 没回答，问题就是行动
        return (f"思考并回答：{question}", importance, deadline)
    
    # 有回答，基于回答生成行动
    lower_q = question.lower()
    
    if "确认" in lower_q or "验证" in lower_q:
        return (f"确认验证：{answer}", importance, deadline)
    if "找" in lower_q or "分析" in lower_q:
        return (f"分析完成：{answer} → 根据分析行动", importance, deadline)
    if "怎么做" in lower_q or "如何" in lower_q:
        return (f"执行：{answer}", importance, deadline)
    
    # 默认：基于回答行动
    return (f"{question} → 结论：{answer} → 按结论行动", importance, deadline)


def save_action_plan(plan: ActionPlan):
    """保存行动计划到日志"""
    with open(ACTION_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(plan.to_dict(), ensure_ascii=False) + "\n")


def mark_action_completed(action_id: int, result: str) -> bool:
    """标记行动完成，记录结果，并回流因果记忆"""
    from ..correlation_memory.correlation_memory import log_causal_event
    
    # 重新写入全部（简单实现，文件不大可接受）
    all_plans = load_all_plans()
    updated = False
    found_plan = None
    found_action = None
    
    for plan in all_plans:
        for action in plan["actions"]:
            if action.get("action_id") == action_id:
                action["completed"] = True
                action["result"] = result
                plan["completed_count"] += 1
                updated = True
                found_plan = plan
                found_action = action
                break
        if updated:
            break
    
    # 写回
    with open(ACTION_LOG_FILE, "w", encoding="utf-8") as f:
        for p in all_plans:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    
    # 回流因果记忆：把行动结果作为反馈
    if updated and found_plan and found_action:
        log_causal_event(
            task=found_plan["judgment_task"],
            result={},
            decision=found_action["description"],
            feedback=f"行动结果：{result}",
            outcome=True if "成功" in result.lower() or "完成" in result else None,
        )
        return True
    
    return False


def format_action_plan(plan: ActionPlan) -> str:
    """生成人类可读行动计划，按四象限分组"""
    lines = [
        f"=== 聚活行动计划（四象限时间压强排序）===\n",
        f"📋 判断任务：{plan.judgment_task[:80]}",
        f"⏰ 生成时间：{plan.created_at[:19]}",
        f"✅ 已完成：{plan.completed_count} / {plan.total_count}",
        "",
    ]
    
    # 按四象限分组输出
    quadrant_labels = {
        "I": "🔴 第一象限：重要×紧急（立即做）",
        "II": "🟡 第二象限：重要×不紧急（计划做，长期成长）",
        "III": "🔵 第三象限：不重要×紧急（考虑委托）",
        "IV": "⚪ 第四象限：不重要×不紧急（最后做）",
    }
    grouped = {q: [] for q in ["I", "II", "III", "IV"]}
    
    for action in plan.actions:
        q = action.get_quadrant()
        grouped[q].append(action)
    
    for q, label in quadrant_labels.items():
        if not grouped[q]:
            continue
        lines.append(f"## {label}")
        for idx, action in enumerate(grouped[q], 1):
            mark = "✓" if action.completed else " "
            score = action.calculate_time_pressure_score()
            lines.append(f"  [{mark}] {idx}. [{action.importance}/5] {action.description}")
            lines.append(f"       压强得分: {score:.0f} | 象限: {q}")
            if action.deadline:
                dt = datetime.fromisoformat(action.deadline)
                lines.append(f"       截止: {dt.strftime('%Y-%m-%d')}")
            if action.completed and action.result:
                lines.append(f"       → 结果: {action.result[:60]}")
        lines.append("")
    
    lines.append("---")
    lines.append("聚活独特技术：时间压强公式自动排序，越重要越紧急越靠前")
    lines.append("完成行动后调用：mark_action_completed(action_id, result) → 自动回流因果记忆")
    
    return "\n".join(lines)


def get_pending_actions_sorted() -> List[NextAction]:
    """获取所有待完成行动，按时间压强排序"""
    all_plans_data = load_all_plans()
    pending = []
    for plan_data in all_plans_data:
        for action_data in plan_data.get("actions", []):
            if not action_data.get("completed", False):
                action = NextAction.from_dict(action_data)
                pending.append(action)
    
    # 聚活独特排序
    return sort_actions_by_time_pressure(pending)


def get_daily_priorities() -> str:
    """
    获取今日优先行动：所有优先级高且截止在今天的行动
    聚活每日清单用这个
    """
    today = datetime.now().date()
    pending = get_pending_actions_sorted()
    today_pending = []
    
    for action in pending:
        if not action.deadline:
            # 重要性>=4也放今日
            if action.importance >= 4:
                today_pending.append(action)
        else:
            try:
                dt = datetime.fromisoformat(action.deadline).date()
                if dt == today:
                    today_pending.append(action)
            except:
                pass
    
    if not today_pending:
        return "🎉 今天没有高优先级待办，可以整理总结了"
    
    lines = ["=== 聚活今日优先行动（时间压强排序）===\n"]
    for idx, action in enumerate(today_pending, 1):
        mark = " " if not action.completed else "✓"
        score = action.calculate_time_pressure_score()
        quad = action.get_quadrant()
        lines.append(f"[{mark}] {idx}. [{action.importance}/5] {action.description}")
        lines.append(f"      压强: {score:.0f} | 象限: {quad}")
    
    return "\n".join(lines)
