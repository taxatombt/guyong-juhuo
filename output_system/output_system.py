#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
output_system.py — 输出系统 最小可用版

核心问题：**想法怎么变成行动，什么时候该输出，输出什么格式**

设计原则：
- 从小处开始，先做核心决策：输出时机 + 三种格式
- 输出 = 不是简单把结果打出来，是决定「现在要不要说，说多少」

三种输出格式：
1. brief — 简短结论，适合快速决策，别人只想知道答案
2. full — 完整报告，适合复杂问题，要看到全过程
3. structured — JSON结构化，适合机器调用，后续处理

输出时机决策：
- 如果情绪信号 need_attention → 必须先输出情绪提示
- 如果自我模型有警告 → 必须先输出警告
- 如果好奇心有高优先级缺口 → 提示有未探索问题
- 最后看复杂度 → simple 输出 brief，complex 输出 full
"""

from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
import json

from emotion_system.emotion_system import EmotionSignal
from self_model.self_model import get_self_warnings
from curiosity.curiosity_engine import CuriosityEngine


OUTPUT_FORMATS = ["brief", "full", "structured"]


@dataclass
class OutputDecision:
    """输出决策"""
    should_output: bool
    format: str  # brief / full / structured
    preamble: List[str]  # 开头提示（情绪/自我警告）
    content_section: str  # main / full / summary
    include_causal_history: bool
    include_self_warnings: bool
    include_emotion_signal: bool


class OutputSystem:
    """输出系统主入口"""

    def decide_output(
        self,
        judgment_result: Dict,
        format_request: Optional[str] = None,
    ) -> OutputDecision:
        """
        决定输出：
        - format_request: 用户要求的格式，优先级最高
        - 自动决策：根据结果复杂度和信号决定
        """
        preamble = []
        complexity = judgment_result.get("complexity", "simple")
        
        # 规则1：情绪信号需要重视 → 必须放开头
        emotion = judgment_result.get("emotion", {})
        if emotion.get("need_attention"):
            preamble.append(f"[情绪信号] {emotion['signal_description']}")
        
        # 规则2：自我模型有警告 → 必须放开头
        self_model = judgment_result.get("self_model", {})
        warnings = self_model.get("warnings", [])
        if warnings:
            preamble.extend(warnings)
        
        # 规则3：高优先级好奇心待探索 → 提示
        curiosity = judgment_result.get("curiosity", {})
        if curiosity.get("has_gap"):
            preamble.append("[好奇心] 当前判断存在信息缺口，解决后判断质量会提高")
        
        # 用户指定格式 → 直接用
        if format_request and format_request in OUTPUT_FORMATS:
            include_causal = (format_request == "full") or (complexity == "critical")
            include_self = len(preamble) > 0
            return OutputDecision(
                should_output=True,
                format=format_request,
                preamble=preamble,
                content_section="full" if format_request == "full" else "summary",
                include_causal_history=include_causal,
                include_self_warnings=True,
                include_emotion_signal=True,
            )
        
        # 自动决策
        if complexity == "simple":
            return OutputDecision(
                should_output=True,
                format="brief",
                preamble=preamble,
                content_section="summary",
                include_causal_history=False,
                include_self_warnings=len(preamble) > 0,
                include_emotion_signal=emotion.get("need_attention", False),
            )
        elif complexity == "complex":
            return OutputDecision(
                should_output=True,
                format="full",
                preamble=preamble,
                content_section="full",
                include_causal_history=True,
                include_self_warnings=True,
                include_emotion_signal=emotion.get("need_attention", False),
            )
        elif complexity == "critical":
            return OutputDecision(
                should_output=True,
                format="full",
                preamble=preamble,
                content_section="full",
                include_causal_history=True,
                include_self_warnings=True,
                include_emotion_signal=emotion.get("need_attention", False),
            )
        else:
            return OutputDecision(
                should_output=True,
                format="brief",
                preamble=preamble,
                content_section="summary",
                include_causal_history=False,
                include_self_warnings=len(preamble) > 0,
                include_emotion_signal=emotion.get("need_attention", False),
            )

    def format_brief(self, judgment_result: Dict, decision: OutputDecision) -> str:
        """简短结论格式"""
        lines = []
        
        # 开头提示
        if decision.preamble:
            lines.extend(decision.preamble)
            lines.append("")
        
        lines.append(f"问题：{judgment_result.get('original_task', '')[:80]}")
        lines.append("")
        
        # 必须检查维度
        must = judgment_result.get("must_check", [])
        if must:
            lines.append(f"核心维度需要检查：{', '.join(must)}")
        
        # 跳过维度
        skipped = judgment_result.get("skipped", [])
        if skipped:
            lines.append(f"可以跳过：{', '.join(skipped)}")
        
        lines.append("")
        lines.append("👉 请按顺序检查以上维度，得到结论。")
        
        return "\n".join(lines)

    def format_full(self, judgment_result: Dict, decision: OutputDecision) -> str:
        """完整报告格式"""

        lines = []
        
        # 开头提示
        if decision.preamble:
            lines.extend(decision.preamble)
            lines.append("---")
            lines.append("")
        
        lines.append(f"# 判断报告：{judgment_result.get('original_task', '')}")
        lines.append("")
        
        lines.append("## 必须检查的维度")
        for dim in judgment_result.get("must_check", []):
            questions = judgment_result.get("questions", {}).get(dim, [])
            lines.append(f"### {dim}")
            for q in questions:
                lines.append(f"- {q}")
            lines.append("")
        
        if judgment_result.get("important", []):
            lines.append("## 重要参考维度")
            for dim in judgment_result.get("important", []):
                lines.append(f"- {dim}")
            lines.append("")
        
        if judgment_result.get("skipped", []):
            lines.append("## 可以跳过的维度")
            lines.append(f"- {', '.join(judgment_result.get('skipped', []))}")
            lines.append("")
        
        # 因果记忆
        if decision.include_causal_history:
            causal = judgment_result.get("correlation_memory", {})
            if causal.get("has_history"):
                lines.append("## 相关因果历史")
                lines.append(causal.get("summary", ""))
                lines.append("")
        
        # 自我模型
        if decision.include_self_warnings:
            self_m = judgment_result.get("self_model", {})
            warnings = self_m.get("warnings", [])
            if warnings:
                lines.append("## 自我提醒")
                for w in warnings:
                    lines.append(f"- {w}")
                lines.append("")
        
        # 情绪
        if decision.include_emotion_signal:
            emo = judgment_result.get("emotion", {})
            lines.append("## 情绪信号")
            lines.append(f"- 检测到情绪：{', '.join(emo.get('detected_emotions', []))}")
            lines.append(f"- {emo.get('signal_description', '')}")
            lines.append("")
        
        lines.append("---")
        lines.append("请逐一回答每个维度的问题，得到最终判断。")
        
        return "\n".join(lines)

    def format_structured(self, judgment_result: Dict) -> str:
        """结构化JSON输出，机器消费"""
        return json.dumps(judgment_result, ensure_ascii=False, indent=2)


def format_output(
    judgment_result: Dict,
    format_request: Optional[str] = None,
) -> str:
    """入口：格式化输出判断结果"""
    system = OutputSystem()
    decision = system.decide_output(judgment_result, format_request)
    
    if not decision.should_output:
        return ""
    
    if decision.format == "brief":
        return system.format_brief(judgment_result, decision)
    elif decision.format == "full":
        return system.format_full(judgment_result, decision)
    elif decision.format == "structured":
        return system.format_structured(judgment_result)
    else:
        return system.format_brief(judgment_result, decision)


# 测试
if __name__ == "__main__":
    from router import check10d
    
    test_result = check10d("我很焦虑，不知道选A还是B，现在两个机会都不错")
    system = OutputSystem()
    decision = system.decide_output(test_result)
    
    print("=== 输出决策 ===")
    print(f"format: {decision.format}")
    print(f"preamble: {decision.preamble}")
    print("\n=== 完整输出 ===")
    print(system.format_full(test_result, decision))
