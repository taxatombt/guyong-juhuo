"""
agent.py — guyong-juhuo Agent 主程序

定位：聚活 — 模拟具体个体，持续自我进化，最终超越人类

工作流（完整闭环）：
接收任务 → 加载 profile → 十维追问 → 输出判断 → 记录反馈 → 记入因果记忆

子系统矩阵：
  judgment/   → 判断系统（遇到两难怎么想）
  perception/ → 感知输入（注意力过滤，网页/PDF提取）
  correlation_memory/ → 因果记忆（过去如何影响现在）
  openspace/  → 自进化（错误→规则，三级进化）
  self_model/ → 自我模型（我的盲区在哪）
  emotion_system/ → 情感系统（情绪在说什么）
  curiosity/  → 好奇心引擎（主动探索什么）
  goal_system/ → 目标系统（对齐长期方向）
  output_system/ → 输出系统（什么时候输出什么格式）
  action_system/ → 行动规划（下一步怎么做）
  feedback_system/ → 反馈记录（执行结果记录）
"""

import sys
import os
import json
import readline

from perception import AttentionFilter, IncomingMessage
from judgment.router import check10d, format_report, format_structured
from output_system.output_system import OutputSystem, decide_output


class JuhuoAgent:
    """聚活 Agent — 完整主程序"""

    def __init__(self, profile_name: str = None):
        self.profile_name = profile_name
        self.attention_filter = AttentionFilter()
        self.output_system = OutputSystem()
        print(f"聚活 Agent 初始化完成{' ['+profile_name+']' if profile_name else ''}")

    def run(self, task: str = None, interactive: bool = False):
        if task:
            # 单次运行
            msg = IncomingMessage(content=task, source="cli", sender="user")
            filter_result = self.attention_filter.filter(msg)
            if not filter_result.passed:
                print(f"[过滤] 信息优先级过低: {filter_result.reason}")
                return
            result = check10d(task, profile_name=self.profile_name)
            decision = self.output_system.decide_output(result)
            if decision.format == "full":
                print(format_report(result))
            elif decision.format == "brief":
                print(result["conclusion"])
            elif decision.format == "structured":
                print(format_structured(result))
            return

        if interactive:
            print("\n聚活 交互模式 — 输入 'quit' 或 'exit' 退出\n")
            while True:
                try:
                    line = input("> ")
                    if line.strip().lower() in ["quit", "exit", "q"]:
                        break
                    if not line.strip():
                        continue
                    msg = IncomingMessage(content=line, source="cli", sender="user")
                    filter_result = self.attention_filter.filter(msg)
                    if not filter_result.passed:
                        print(f"[过滤] 信息优先级过低: {filter_result.reason}\n")
                        continue
                    result = check10d(line, profile_name=self.profile_name)
                    decision = self.output_system.decide_output(result)
                    print()
                    if decision.format == "full":
                        print(format_report(result))
                    elif decision.format == "brief":
                        print("结论:", result["conclusion"])
                    elif decision.format == "structured":
                        print(format_structured(result))
                    print()
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break
            print("\n再见")
            return


def main():
    args = sys.argv[1:]
    profile_name = None
    task = None
    i = 0
    while i < len(args):
        if args[i] == "--profile":
            profile_name = args[i+1]
            i += 2
        else:
            task = " ".join(args[i:])
            break
    agent = JuhuoAgent(profile_name=profile_name)
    agent.run(task=task, interactive=True)


if __name__ == "__main__":
    main()
