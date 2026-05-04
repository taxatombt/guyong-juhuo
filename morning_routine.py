#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
morning_routine.py — 早晨决策闭环（最小验证出口）

最小可行闭环场景：
  输入（精力/情绪/待办） → 10维判断 → 推荐 → 执行 → verdict → 更新 → 下次更好

设计原则：从最小出口往前推，不铺子系统。

用法：
  python morning_routine.py                    # 交互模式
  python morning_routine.py --task "写代码"   # 单任务
  python morning_routine.py --energy 6 --tasks "任务1,tasks2"  # 带参数
"""

from __future__ import annotations
import sys
import json
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

from judgment.logging_config import get_logger
from judgment.pipeline import check10d_full, PipelineConfig, format_full_report
from judgment.router import check10d_run
from judgment.closed_loop import receive_verdict
from emotion_system.emotion_engine import analyze_emotion
from correlation_memory.correlation_chain import log_judgment_event

log = get_logger("juhuo.morning")


def parse_energy(energy_str: str) -> int:
    """解析精力值（1-10）"""
    try:
        v = int(energy_str)
        return max(1, min(10, v))
    except Exception:
        return 5  # 默认中等精力


def parse_tasks(tasks_str: str) -> List[str]:
    """解析任务列表（逗号分隔）"""
    if not tasks_str or not tasks_str.strip():
        return []
    return [t.strip() for t in tasks_str.split(",") if t.strip()]


def build_morning_context(energy: int, emotion_state: Optional[str], tasks: List[str]) -> Dict[str, Any]:
    """
    构建早晨判断上下文，注入到 prompt 中。
    精力和情绪会通过 Emotion System → Judgment 调制维度权重。
    """
    return {
        "energy": energy,
        "emotion_state": emotion_state or "unknown",
        "tasks": tasks,
        "mode": "morning_decision",
    }


def judge_task(task: str, context: Dict[str, Any], user_id: str = "default") -> Dict[str, Any]:
    """
    对单个任务执行 10 维判断，返回结果。
    精力/情绪通过 emotion_state 参数注入（emotion_engine → judgment 调制维度权重）。
    包含 chain_id 以便后续 verdict 反馈。
    """
    emotion_state = context.get("emotion_state")
    try:
        # 使用同步接口，直接传 emotion_state 以激活情绪调制
        result = check10d_run(task, emotion_state=emotion_state, user_id=user_id)
    except Exception:
        # 降级：用 pipeline 接口
        result = check10d_full(task, user_id=user_id)
    return result


def format_morning_report(results: List[Dict[str, Any]], energy: int, emotion_state: str) -> str:
    """
    格式化早晨决策报告，按优先级排序。
    """
    lines = []
    lines.append("\n" + "=" * 50)
    lines.append("🌅 早晨决策报告")
    lines.append("=" * 50)
    lines.append(f"精力水平：{'🔋' * energy}{'⚪' * (10 - energy)} ({energy}/10)")
    lines.append(f"情绪状态：{emotion_state}")
    lines.append(f"待办任务：{len(results)} 项\n")

    # 按置信度排序
    sorted_results = sorted(results, key=lambda r: r.get("confidence", 0), reverse=True)

    lines.append("─" * 50)
    lines.append("📋 推荐执行顺序：\n")

    for i, r in enumerate(sorted_results, 1):
        task = r.get("task", "?")
        verdict = r.get("verdict", "？")
        confidence = r.get("confidence", 0)
        chain_id = r.get("chain_id", "")
        dims = r.get("dimensions", {})
        scores = r.get("scores", {})

        conf_bar = "█" * int(confidence * 20) + "░" * (20 - int(confidence * 20))
        lines.append(f"  {i}. {task}")
        lines.append(f"     → {verdict}  置信度：{conf_bar} {confidence * 100:.1f}%")
        if scores:
            top_dims = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
            dim_str = " / ".join([f"{k}={v:.0%}" for k, v in top_dims])
            lines.append(f"     主要维度：{dim_str}")
        lines.append(f"     [chain_id: {chain_id}]")
        lines.append("")

    lines.append("─" * 50)
    lines.append("请执行后告诉我结果，例如：")
    lines.append("  verdict <chain_id> correct   # 判断正确")
    lines.append("  verdict <chain_id> wrong     # 判断错误")
    lines.append("  verdict <chain_id> partial   # 部分正确")
    lines.append("=" * 50 + "\n")

    return "\n".join(lines)


def interact_morning(energy: int, tasks: List[str], user_id: str = "default") -> List[Dict[str, Any]]:
    """
    交互式早晨决策：分析情绪 → 判断任务 → 输出报告。
    """
    # Step 1: 情绪分析（仅描述性，不阻塞）
    emotion_state = "平静"
    try:
        emotion_result = analyze_emotion(f"今天精力{energy}/10，待办：{','.join(tasks[:3])}")
        if emotion_result:
            emotion_state = emotion_result.get("emotion_label", "平静")
    except Exception as e:
        log.debug(f"情绪分析跳过: {e}")

    # Step 2: 构建上下文
    context = build_morning_context(energy, emotion_state, tasks)

    # Step 3: 对每个任务执行 10 维判断
    results = []
    for task in tasks:
        print(f"⚖️  分析中: {task}...", end="", flush=True)
        r = judge_task(task, context, user_id)
        r["task"] = task  # 保留任务名
        results.append(r)
        print(" ✓")

    # Step 4: 输出报告
    report = format_morning_report(results, energy, emotion_state)
    print(report)

    return results


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="早晨决策闭环")
    parser.add_argument("--energy", "-e", default=None, help="精力水平 1-10（交互询问如未提供）")
    parser.add_argument("--tasks", "-t", default=None, help="任务列表，逗号分隔")
    parser.add_argument("--emotion", default=None, help="情绪描述（如：紧张、兴奋）")
    parser.add_argument("--user-id", default="default", help="用户标识")
    parser.add_argument("--task", default=None, help="单个任务（简写模式）")
    args = parser.parse_args()

    # ── 单任务模式 ────────────────────────────────────────────────────────
    if args.task:
        energy = int(args.energy) if args.energy else 5
        emotion_state = args.emotion or "平静"
        context = build_morning_context(energy, emotion_state, [args.task])
        result = judge_task(args.task, context, args.user_id)
        result["task"] = args.task
        report = format_morning_report([result], energy, emotion_state)
        print(report)
        return

    # ── 交互模式 ──────────────────────────────────────────────────────────
    # 精力
    if args.energy:
        energy = parse_energy(args.energy)
    else:
        while True:
            try:
                inp = input("精力水平（1-10，输入数字）：").strip()
                energy = parse_energy(inp)
                break
            except (EOFError, KeyboardInterrupt):
                print("\n已退出。")
                return

    # 情绪
    emotion_state = args.emotion
    if not emotion_state:
        try:
            inp = input("情绪状态（回车跳过，默认平静）：").strip()
            emotion_state = inp if inp else "平静"
        except (EOFError, KeyboardInterrupt):
            emotion_state = "平静"

    # 任务
    if args.tasks:
        tasks = parse_tasks(args.tasks)
    else:
        print("请输入今日待办（每行一个，输入空行结束）：")
        tasks = []
        while True:
            try:
                inp = input("  > ").strip()
                if not inp:
                    break
                tasks.append(inp)
            except (EOFError, KeyboardInterrupt):
                break

    if not tasks:
        print("没有待办任务，退出。")
        return

    interact_morning(energy, tasks, args.user_id)


if __name__ == "__main__":
    main()
