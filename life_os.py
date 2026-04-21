#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Life OS v3 — 精力/情绪驱动的任务调度"""
import sys, argparse, re
from typing import Dict, Tuple, List
from dataclasses import dataclass, field

# ── Constants ──────────────────────────────────────────────────────────────────
ENERGY_HIGH_THRESHOLD = 70    # 高精力阈值
ENERGY_MEDIUM_THRESHOLD = 45  # 中等精力阈值

# 情绪 → 任务类型加成 (emotion boosts)
# 格式: {emotion_name: {task_type: score_delta}}
EMOTION_BOOSTS: Dict[str, Dict[str, int]] = {
    "excitement": {"cognitive": +20, "social": +15, "physical": +10, "emotional": +0, "admin": +0},
    "joy":        {"cognitive": +15, "social": +10, "physical": +10, "emotional": +5, "admin": +5},
    "anxiety":    {"cognitive": -20, "social": +0,  "physical": +20, "emotional": +10,"admin": +10},
    "sadness":    {"cognitive": -10, "social": -10, "physical": +5,  "emotional": +5, "admin": +5},
    "calm":       {"cognitive": +10, "social": +0,  "physical": +5,  "emotional": +5, "admin": +5},
    "anger":      {"cognitive": -10, "social": +10, "physical": +15,  "emotional": +5, "admin": -5},
    "boredom":    {"cognitive": -15, "social": +10, "physical": +10,  "emotional": +0, "admin": +5},
    "determination": {"cognitive": +15, "social": +5, "physical": +10,  "emotional": +5, "admin": +5},
}

# 情绪中文标签
EMOTION_LABELS: Dict[str, str] = {
    "excitement": "兴奋", "anxiety": "焦虑", "joy": "愉悦",
    "sadness": "低落", "calm": "平静", "anger": "愤怒",
    "boredom": "无聊", "determination": "坚定",
}


# ── PAD Emotion Detection ──────────────────────────────────────────────────────
def detect_pad(text: str) -> Dict[str, float]:
    """
    从文本检测 PAD (Pleasure-Arousal-Dominance) 三维情绪。

    P (Pleasure): 愉快度，正=积极情绪，负=消极情绪
    A (Arousal):   激活度，正=兴奋/紧张，负=平静/疲惫
    D (Dominance): 控制感，正=主动/自信，负=被动/迷茫
    """
    t = text.lower()
    pleasure = arousal = dominance = 0.0

    # P+ 词：愉快、满足、安心
    p_plus = [
        "开心", "愉快", "愉悦", "满足", "轻松", "舒服", "舒心",
        "高兴", "快乐", "喜悦", "幸福", "美好", "温暖",
        "期待", "希望", "乐观", "憧憬",
    ]
    # P- 词：焦虑、难过、沮丧
    p_minus = [
        "焦虑", "低落", "抑郁", "疲惫", "紧张", "压力", "难过",
        "烦躁", "不安", "担心", "害怕", "恐惧", "沮丧", "绝望",
        "生气", "郁闷", "压抑", "不爽",
    ]
    # A+ 词：兴奋、激动、紧张
    a_plus = [
        "兴奋", "激动", "紧张", "心跳", "焦虑",
        "刺激", "热烈", "热血", "冲动",
        "愤怒", "气", "恼火", "火大",
    ]
    # A- 词：平静、放松、慵懒
    a_minus = [
        "平静", "放松", "慵懒", "疲惫", "低落", "困倦",
        "无聊", "懒散", "发呆",
    ]
    # D+ 词：自信、坚定、有掌控
    d_plus = [
        "自信", "掌控", "坚定", "主动", "有把握", "胸有成竹",
        "决心", "意志", "毅力", "坚定",
    ]
    # D- 词：迷茫、犹豫、失控
    d_minus = [
        "迷茫", "犹豫", "失控", "被动", "不确定", "没信心",
        "纠结", "彷徨", "无奈", "无力",
    ]

    if any(k in t for k in p_plus): pleasure += 0.4
    if any(k in t for k in p_minus): pleasure -= 0.4
    if any(k in t for k in ["愤怒", "气", "火大"]): pleasure -= 0.3
    # 压力大 → 失控感 → D降低
    if any(k in t for k in ["压力", "失控", "超载", "喘不过气"]): dominance -= 0.3
    if any(k in t for k in a_plus): arousal += 0.4
    if any(k in t for k in a_minus): arousal -= 0.3
    if any(k in t for k in d_plus): dominance += 0.3
    if any(k in t for k in d_minus): dominance -= 0.3

    return {
        "P": max(-1.0, min(1.0, pleasure)),
        "A": max(-1.0, min(1.0, arousal)),
        "D": max(-1.0, min(1.0, dominance)),
    }


# ── Data Classes ───────────────────────────────────────────────────────────────
@dataclass
class Task:
    """任务：名称 + 各维度需求 + 类型"""
    name: str
    cognitive_demand: int = 20      # 认知需求 (0-100)
    social_demand: int = 20         # 社交需求
    physical_demand: int = 20        # 体力需求
    emotional_demand: int = 20      # 情绪能量需求
    task_type: str = "admin"        # cognitive | social | physical | emotional | admin

    @staticmethod
    def classify(task_name: str) -> "Task":
        """根据任务名自动分类"""
        lowered = task_name.lower()
        task = Task(name=task_name)

        cognitive_keywords = ["写", "bp", "报告", "分析", "规划", "策略",
                             "思考", "开发", "代码", "阅读", "学习", "研究",
                             "写作", "方案", "设计", "策划", "总结"]
        social_keywords = ["见", "会", "电话", "聊", "客户", "面试",
                           "谈判", "交流", "拜访", "社交", "应酬"]
        physical_keywords = ["健", "跑", "瑜伽", "运动", "健身", "游泳",
                             "骑车", "爬山", "打球", "徒步", "散步"]
        emotional_keywords = ["妈妈", "家人", "朋友", "放松", "休息",
                              "冥想", "独处", "娱乐", "看电影", "玩游戏"]

        if any(k in lowered for k in cognitive_keywords):
            task.cognitive_demand = 80
            task.task_type = "cognitive"
        elif any(k in lowered for k in social_keywords):
            task.social_demand = 80
            task.task_type = "social"
        elif any(k in lowered for k in physical_keywords):
            task.physical_demand = 80
            task.task_type = "physical"
        elif any(k in lowered for k in emotional_keywords):
            task.emotional_demand = 80
            task.task_type = "emotional"

        return task


@dataclass
@dataclass
class LifeState:
    """生命状态：精力(PAD Pleasure-Arousal-Dominance)"""
    energy: int
    pad: Dict[str, float]
    emotion_label: str

    @staticmethod
    def from_pad(energy: int, pad: Dict[str, float]) -> "LifeState":
        """从精力+PAD值推断情绪标签"""
        p, a, d = pad.get("P", 0), pad.get("A", 0), pad.get("D", 0)
        if p > 0.2 and a > 0.2:
            label = "excitement"
        elif p < -0.2 and a > 0.2 and d <= -0.2:
            label = "anxiety"
        elif p < -0.2 and a > 0.2 and d > -0.2:
            label = "anger"
        elif p > 0.2 and a <= 0.2:
            label = "joy"
        elif p < -0.2 and a <= 0.2:
            label = "sadness"
        elif abs(p) <= 0.2 and a < -0.2:
            label = "boredom"
        elif d > 0.2 and a >= 0.0:
            label = "determination"
        else:
            label = "calm"
        return LifeState(energy=energy, pad=pad, emotion_label=label)


@dataclass
class ScheduleTask:
    """调度结果中的任务"""
    task: str
    task_type: str
    can_do: bool
    reason: str
    relevance_score: int
    time_slot: str
    judgment_score: float = -1.0
    verdict: str = ""
    rank: int = 0


def can_execute(task: Task, state: LifeState) -> Tuple[bool, str]:
    """判断任务是否可执行"""
    if task.cognitive_demand >= 70 and state.energy < ENERGY_MEDIUM_THRESHOLD:
        return False, "精力不足"
    if task.social_demand >= 70 and state.pad.get("A", 0) < 0.3:
        return False, "情绪未激活"
    return True, ""


def relevance_score(task: Task, state: LifeState) -> int:
    """任务-状态匹配度评分"""
    score = 50
    if task.cognitive_demand >= 70:
        score += 30 if state.energy >= ENERGY_HIGH_THRESHOLD else -10
    if task.social_demand >= 70:
        score += 20 if state.pad.get("A", 0) >= 0.3 else -20
    if task.physical_demand >= 70:
        score += 15
    score += EMOTION_BOOSTS.get(state.emotion_label, {}).get(task.task_type, 0)
    return max(0, min(100, score))


def time_slot(task: Task) -> str:
    """推荐时间段"""
    if task.cognitive_demand >= 70:
        return "上午 (08:30-11:30)"
    if task.physical_demand >= 70:
        return "傍晚 (17:00-19:00)"
    if task.social_demand >= 70:
        return "下午 (14:00-17:00)"
    return "灵活"


def feasibility_check(task: Task, state: LifeState) -> Tuple[bool, str]:
    """精力+情绪双重可行性检查"""
    if task.cognitive_demand >= 70 and state.energy < ENERGY_MEDIUM_THRESHOLD:
        return False, f"精力{state.energy}不足(需{ENERGY_MEDIUM_THRESHOLD}+)"
    if task.social_demand >= 70 and state.pad.get("A", 0) < 0.3:
        return False, f"情绪A={state.pad.get('A',0):.2f}未激活"
    if task.physical_demand >= 70 and state.energy < ENERGY_LOW_THRESHOLD:
        return False, f"精力不足"
    return True, ""


ENERGY_LOW_THRESHOLD = 30


def rule_summary(state: LifeState, doable: List[ScheduleTask]) -> str:
    """生成推荐摘要"""
    if state.energy >= ENERGY_HIGH_THRESHOLD:
        energy_advice = "精力充沛，推荐高认知任务"
    elif state.energy >= ENERGY_MEDIUM_THRESHOLD:
        energy_advice = "精力尚可，可处理中等强度任务"
    else:
        energy_advice = "精力有限，建议低强度任务或休息"

    emotion_name = EMOTION_LABELS.get(state.emotion_label, state.emotion_label)
    top = [t for t in doable if t.can_do][:2]
    tasks_str = " / ".join([t.task for t in top]) if top else "无"

    return (
        f"精力: {state.energy}/100 | 情绪: {emotion_name} | {energy_advice}"
        f"\n推荐: {tasks_str}"
    )


def main():
    parser = argparse.ArgumentParser(description="Life OS — 精力/情绪驱动任务调度")
    parser.add_argument("tasks", nargs="+", help="今日任务列表")
    parser.add_argument("--energy", type=int, default=70, help="精力值 0-100 (默认70)")
    parser.add_argument("--pad", type=str, default="", help="PAD值，格式: P=0.3,A=0.5,D=0.6")
    args = parser.parse_args()

    # 解析 PAD
    if args.pad:
        pad = {}
        for part in args.pad.split(","):
            k, v = part.split("=")
            pad[k.strip()] = float(v.strip())
    else:
        pad = detect_pad(" ".join(args.tasks))

    state = LifeState.from_pad(args.energy, pad)
    emotion_name = EMOTION_LABELS.get(state.emotion_label, state.emotion_label)

    print(f"精力: {state.energy}/100  PAD: P={pad['P']:.2f} A={pad['A']:.2f} D={pad['D']:.2f}")
    print(f"情绪: {emotion_name} ({state.emotion_label})")
    print(f"{'─'*50}")

    # 处理任务
    tasks = [Task.classify(t) for t in args.tasks]
    schedule_tasks: List[ScheduleTask] = []
    for t in tasks:
        can_do, reason = can_execute(t, state)
        rs = relevance_score(t, state)
        ts = time_slot(t)
        schedule_tasks.append(
            ScheduleTask(task=t.name, task_type=t.task_type,
                        can_do=can_do, reason=reason,
                        relevance_score=rs, time_slot=ts)
        )

    doable = [s for s in schedule_tasks if s.can_do]
    notdo = [s for s in schedule_tasks if not s.can_do]

    if not doable:
        print("无可行任务，建议休息")
        return

    print(f"可选任务: {len(doable)}/{len(schedule_tasks)}")
    print()

    for r in doable:
        label = EMOTION_LABELS.get(state.emotion_label, state.emotion_label)
        print(f"  [{r.rank or '?'}] {r.task}")
        print(f"      类型={r.task_type} | 推荐时段={r.time_slot} | 匹配度={r.relevance_score}%")

    print()
    print(rule_summary(state, doable))

    for r in notdo:
        print(f"  [x] {r.task} — {r.reason}")

    # 行为日志
    try:
        from judgment.behavior_logger import log_agent_behavior, ActionChannel
        log_agent_behavior(
            task_text=" | ".join(args.tasks),
            channel=ActionChannel.JUDGMENT,
            verdict=rule_summary(state, doable),
            confidence=state.energy / 100.0,
            tool_calls=[],
            execution_result="",
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
