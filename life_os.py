#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Life OS 最小 CLI"""

import sys
import argparse
from typing import Dict, List, Optional
from dataclasses import dataclass

ENERGY_HIGH = 70
ENERGY_MED = 45
ENERGY_LOW = 30
AROUSAL_SOCIAL = 0.3

@dataclass
class Task:
    name: str
    cognitive_demand: int = 20
    social_demand: int = 20
    emotional_benefit: int = 20
    physical_demand: int = 20

@dataclass
class LifeState:
    energy: int
    emotion_state: Dict[str, float]
    emotion_label: str

def classify_task(task_name: str) -> Task:
    name_lower = task_name.lower()
    t = Task(name=task_name)
    high_cog = ["写", "bp", "报告", "分析", "规划", "策略", "思考", "开发"]
    if any(kw in name_lower for kw in high_cog):
        t.cognitive_demand = 80
    social_kw = ["见", "会", "电话", "聊", "客户", "会议"]
    if any(kw in name_lower for kw in social_kw):
        t.social_demand = 80
    phys_kw = ["健", "跑", "瑜伽", "运动", "健身"]
    if any(kw in name_lower for kw in phys_kw):
        t.physical_demand = 80
    emotional_kw = ["妈妈", "家人", "朋友", "放松", "休息"]
    if any(kw in name_lower for kw in emotional_kw):
        t.emotional_benefit = 80
    return t

def can_execute(task: Task, state: LifeState) -> tuple:
    if task.cognitive_demand >= 70 and state.energy < ENERGY_MED:
        return False, "精力{}%不足".format(state.energy)
    if task.social_demand >= 70 and state.emotion_state.get("A", 0) < AROUSAL_SOCIAL:
        return False, "激活度不足"
    return True, "OK"

def score_task(task: Task, state: LifeState) -> int:
    score = 50
    if task.cognitive_demand >= 70:
        score += 30 if state.energy >= ENERGY_HIGH else -10
    bonus = {"excitement": 20, "joy": 15, "anxiety": -30, "sadness": -10, "calm": 10}
    score += bonus.get(state.emotion_label, 0)
    score += task.emotional_benefit // 10
    return max(0, min(100, score))

def pad_to_emotion(pad: Dict) -> str:
    P, A = pad.get("P", 0), pad.get("A", 0)
    if P > 0.2 and A > 0.2: return "excitement"
    if P < -0.2 and A > 0.2: return "anxiety"
    if P > 0.2 and A < 0.2: return "joy"
    if P < -0.2 and A < 0.2: return "sadness"
    return "calm"

def schedule(tasks: List[str], energy: int, pad: Dict) -> List[Dict]:
    emotion_label = pad_to_emotion(pad)
    state = LifeState(energy=energy, emotion_state=pad, emotion_label=emotion_label)
    results = []
    for task_name in tasks:
        task = classify_task(task_name)
        can_do, reason = can_execute(task, state)
        score = score_task(task, state) if can_do else 0
        slot = "上午 (08:30-11:30)" if task.cognitive_demand >= 70 else \
               "下午 (16:00-18:00)" if task.physical_demand >= 70 else "灵活"
        results.append({
            "task": task_name,
            "can_do": can_do,
            "reason": reason if not can_do else "",
            "score": score,
            "time_slot": slot if can_do else "延期",
            "type": "cognitive" if task.cognitive_demand >= 70 else \
                    "social" if task.social_demand >= 70 else \
                    "physical" if task.physical_demand >= 70 else "admin"
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def main():
    parser = argparse.ArgumentParser(description="Life OS 最小 CLI")
    parser.add_argument("tasks", nargs="*", help="任务列表，逗号分隔")
    parser.add_argument("--energy", type=int, default=70, help="精力 0-100")
    parser.add_argument("--emotion", default="", help="PAD状态 P=0.3,A=0.5,D=0.6")
    args = parser.parse_args()
    
    if not args.tasks:
        print("用法: python life_os.py <任务1/任务2/...> [--energy 80] [--emotion P=0.3,A=0.5,D=0.6]")
        return
    tasks = []
    for t in args.tasks:
        tasks.extend([x.strip() for x in t.replace("、", "/").split("/") if x.strip()])
    
    pad = {"P": 0.0, "A": 0.0, "D": 0.0}
    if args.emotion:
        for part in args.emotion.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                pad[k.strip()] = float(v.strip())
    
    emotion_label = pad_to_emotion(pad)
    
    print("=== Life OS 调度 ===")
    print("精力: {}% | 情绪: {} (P={:.1f}, A={:.1f}, D={:.1f})".format(
        args.energy, emotion_label, pad["P"], pad["A"], pad["D"]))
    print()
    
    results = schedule(tasks, args.energy, pad)
    print("{:<4} {:<20} {:<10} {:<4} {:<20}".format("序号", "任务", "类型", "分", "时段"))
    print("-" * 60)
    for i, r in enumerate(results, 1):
        status = "[OK]" if r["can_do"] else "[延]"
        print("{:<4} {:<20} {:<10} {:<4} {:<20} {}".format(
            i, r["task"], r["type"], r["score"], r["time_slot"], status))
    print()
    
    if emotion_label == "anxiety":
        print("[建议] 焦虑状态，建议先做低认知任务或运动调节")
    elif emotion_label == "excitement":
        print("[建议] 兴奋状态，适合深度工作和高认知任务")
    elif args.energy < ENERGY_MED:
        print("[建议] 精力{}%较低，推迟高认知任务".format(args.energy))
    
    cog = [r for r in results if r["type"] == "cognitive" and r["can_do"]]
    soc = [r for r in results if r["type"] == "social" and r["can_do"]]
    phy = [r for r in results if r["type"] == "physical" and r["can_do"]]
    
    if cog and soc:
        print("[推荐组合] 上午{} + 下午{}".format(cog[0]["task"], soc[0]["task"]))
    if phy:
        print("[体力调节] 建议{}放在傍晚".format(phy[0]["task"]))
    
    print()
    print("=== 完成 ===")

if __name__ == "__main__":
    main()
