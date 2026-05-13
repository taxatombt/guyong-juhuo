#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debate.py — 多方辩论判断系统

来源：TauricResearch/TradingAgents 的 Bull/Bear 对立辩论机制

核心理念：
- 判断不是单一 agent 输出，而是多个视角对立辩论的结果
- 至少 3 方：Bull（看多/支持）| Bear（看空/反对）| Judge（中立裁判）
- 辩论结束后，Judge 综合各方论点出最终 verdict
- 辩论日志全程记录，可复盘

与现有 judgment 的关系：
- judgment.check10d()  → 单一视角判断
- debate.debate()      → 多方辩论后出 verdict

使用方式：
    from judgment.debate import debate
    result = debate("是否应该创业？", agent_profile=profile)
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

try:
    from paths import PATHS
except ImportError:
    PATHS = {"DATA": os.path.join(os.path.dirname(__file__), "..", "data")}


DEBATE_DIR = os.path.join(PATHS["DATA"], "debates")
os.makedirs(DEBATE_DIR, exist_ok=True)

# ── 辩论角色定义 ─────────────────────────────────────────────────────

DEBATE_ROLES = {
    "bull": {
        "name": "多方（支持方）",
        "role_card": (
            "你是多方辩手。你的任务是：为用户的想法/决定寻找最有利的论据。\n"
            "要求：\n"
            "1. 列举至少3个支持该决定的正面理由\n"
            "2. 找出该决定的最大潜在收益\n"
            "3. 提供1-2个成功案例或数据支撑\n"
            "4. 指出在什么条件下这个决定是最佳选择\n"
            "语气：积极但有据，不夸大。"
        ),
        "temperature": 0.7,
    },
    "bear": {
        "name": "空方（反对方）",
        "role_card": (
            "你是空方辩手。你的任务是：找出用户想法/决定的最大风险和漏洞。\n"
            "要求：\n"
            "1. 列举至少3个反对该决定的负面理由\n"
            "2. 指出最可能被低估的风险\n"
            "3. 识别至少1个可能导致失败的致命弱点\n"
            "4. 提出最坏情况下的损失规模\n"
            "语气：严肃但不情绪化，用数据和逻辑说话。"
        ),
        "temperature": 0.7,
    },
    "devil": {
        "name": "魔鬼代言人",
        "role_card": (
            "你是魔鬼代言人。你的任务是：从完全对立的视角挑战用户的假设。\n"
            "要求：\n"
            "1. 找出用户忽略或视为理所当然的前提\n"
            "2. 提出与用户假设相反的证据或案例\n"
            "3. 问出\"如果前提本身是错的，你会怎么做？\"\n"
            "4. 评估替代方案的优劣\n"
            "语气：质疑但不否定，最终目的是完善决策而非阻止行动。"
        ),
        "temperature": 0.8,
    },
}


@dataclass
class DebateTurn:
    """一轮辩论"""
    speaker: str          # bull / bear / devil / judge
    speaker_name: str
    argument: str         # 论点内容
    timestamp: str = ""
    score: float = 0.0   # Judge 给的分（0-10）

    def to_dict(self) -> Dict:
        return {
            "speaker": self.speaker,
            "speaker_name": self.speaker_name,
            "argument": self.argument,
            "timestamp": self.timestamp,
            "score": self.score,
        }


@dataclass
class DebateReport:
    """完整辩论报告"""
    debate_id: str
    task: str
    timestamp: str
    turns: List[DebateTurn] = field(default_factory=list)
    final_verdict: str = ""
    final_confidence: float = 0.0
    bull_score: float = 0.0
    bear_score: float = 0.0
    winner: str = ""        # bull / bear / tie
    confidence_adjustment: float = 0.0  # 相对于单方判断的置信度调整
    key_insights: List[str] = field(default_factory=list)  # 辩论产生的关键洞察

    def to_dict(self) -> Dict:
        return {
            "debate_id": self.debate_id,
            "task": self.task[:200],
            "timestamp": self.timestamp,
            "turns": [t.to_dict() for t in self.turns],
            "final_verdict": self.final_verdict,
            "final_confidence": round(self.final_confidence, 3),
            "bull_score": round(self.bull_score, 2),
            "bear_score": round(self.bear_score, 2),
            "winner": self.winner,
            "confidence_adjustment": round(self.confidence_adjustment, 3),
            "key_insights": self.key_insights,
        }

    def save(self):
        """持久化辩论报告"""
        file = os.path.join(DEBATE_DIR, f"{self.debate_id}.json")
        with open(file, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return file


def debate(task: str, agent_profile: Optional[Dict] = None,
          llm_callable=None, max_rounds: int = 2,
          judge_model: Optional[str] = None) -> DebateReport:
    """
    核心辩论函数。

    流程：
    1. Round 1: Bull → Bear → Devil（各方亮出论点）
    2. Round 2: Bull 反驳 Bear → Bear 反驳 Bull（如果有 max_rounds >= 2）
    3. Judge 综合评分 → 给出最终 verdict + 置信度

    参数：
        task           — 辩论主题（用户的问题/决定）
        agent_profile  — agent 个性配置（可选）
        llm_callable   — LLM 调用函数，默认用 check10d_run 的 LLM
        max_rounds     — 辩论轮数（1 或 2）
        judge_model    — 裁判用的模型（默认同 agent）

    返回：DebateReport
    """
    if llm_callable is None:
        llm_callable = _default_llm

    debate_id = f"debate_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(task) % 100000:05d}"
    report = DebateReport(
        debate_id=debate_id,
        task=task,
        timestamp=datetime.now().isoformat(),
    )

    # 收集各方论点
    arguments = {}
    for role_id, role_cfg in DEBATE_ROLES.items():
        arg = _call_debate_role(role_id, role_cfg, task, agent_profile, llm_callable)
        arguments[role_id] = arg
        speaker_name = role_cfg["name"]
        report.turns.append(DebateTurn(
            speaker=role_id,
            speaker_name=speaker_name,
            argument=arg,
            timestamp=datetime.now().isoformat(),
        ))

    # Round 2：反驳（如果有）
    if max_rounds >= 2:
        for role_id, role_cfg in DEBATE_ROLES.items():
            opposing = "bear" if role_id == "bull" else "bull" if role_id == "bear" else None
            if opposing:
                rebuttal = _call_rebuttal(role_id, role_cfg, task, arguments[opposing], llm_callable)
                report.turns.append(DebateTurn(
                    speaker=f"{role_id}_rebuttal",
                    speaker_name=f"{role_cfg['name']}（反驳）",
                    argument=rebuttal,
                    timestamp=datetime.now().isoformat(),
                ))

    # Judge 综合评分
    judge_arg = _call_judge(task, arguments, report.turns, llm_callable)
    report.turns.append(DebateTurn(
        speaker="judge",
        speaker_name="裁判（综合）",
        argument=judge_arg["argument"],
        score=judge_arg.get("score", 0),
        timestamp=datetime.now().isoformat(),
    ))

    report.final_verdict = judge_arg.get("verdict", "（裁判未给出结论）")
    report.final_confidence = judge_arg.get("confidence", 0.5)
    report.bull_score = judge_arg.get("bull_score", 5.0)
    report.bear_score = judge_arg.get("bear_score", 5.0)
    report.winner = judge_arg.get("winner", "tie")

    # 置信度调整：多方胜 → +0.05，空方胜 → -0.10，持平 → 0
    if report.winner == "bull":
        report.confidence_adjustment = 0.05
    elif report.winner == "bear":
        report.confidence_adjustment = -0.10
    else:
        report.confidence_adjustment = 0.0

    # 提取关键洞察
    report.key_insights = _extract_insights(report.turns)

    # 持久化
    saved_file = report.save()

    return report


# ── 内部函数 ─────────────────────────────────────────────────────

def _default_llm(prompt: str, system: str = "", temperature: float = 0.7) -> str:
    """默认 LLM 调用（如果 judgment router 可用则用，否则降级）"""
    try:
        from judgment.router import check10d_run
        # 用 check10d_run 的 LLM（内部已初始化好的 client）
        # 这里做个简单包装，实际在 debate 内部应该直接用 router 的 LLM
        result = check10d_run(prompt[:200], complexity="simple")
        return result.get("verdict", prompt)[:500]
    except Exception as e:
        return f"[LLM unavailable: {e}]"


def _call_debate_role(role_id: str, role_cfg: Dict, task: str,
                      profile: Optional[Dict], llm: callable) -> str:
    """调用某个辩论角色"""
    system_prompt = role_cfg["role_card"]
    if profile:
        system_prompt += f"\n\n参考人物画像：{profile.get('summary','')}"

    user_prompt = f"请分析以下决策/问题：\n{task}"

    try:
        resp = llm(user_prompt, system=system_prompt, temperature=role_cfg["temperature"])
        return resp.strip()
    except Exception as e:
        return f"[调用失败: {e}]"


def _call_rebuttal(role_id: str, role_cfg: Dict, task: str,
                   opposing_arg: str, llm: callable) -> str:
    """调用反驳"""
    system_prompt = (
        f"你是{role_cfg['name']}，现在你需要针对对方论点提出反驳。\n"
        f"要求：直接针对对方论点，逻辑反驳，不重复自己的旧论据。"
    )
    user_prompt = (
        f"决策问题：{task}\n\n"
        f"对方论点：\n{opposing_arg[:800]}\n\n"
        f"你的反驳："
    )
    try:
        resp = llm(user_prompt, system=system_prompt, temperature=role_cfg["temperature"])
        return resp.strip()
    except Exception as e:
        return f"[反驳失败: {e}]"


def _call_judge(task: str, arguments: Dict, turns: List[DebateTurn],
                llm: callable) -> Dict:
    """裁判综合评分"""
    bull_arg = arguments.get("bull", "")
    bear_arg = arguments.get("bear", "")
    devil_arg = arguments.get("devil", "")

    system_prompt = (
        "你是一个中立裁判，综合多方辩论后给出最终判断。\n\n"
        "输出格式（JSON，键名必须为以下这些）：\n"
        '{\n  "verdict": "最终建议（一句话）",\n'
        '  "confidence": 0.0-1.0之间的置信度数值\n,'
        '  "bull_score": 0-10多方论点的得分\n'
        '  "bear_score": 0-10空方论点的得分\n'
        '  "winner": "bull" / "bear" / "tie"\n'
        '  "reasoning": "裁判的综合推理逻辑"\n'
        "}\n\n"
        "注意：\n"
        "- 置信度要反映辩论后你对结论的确信程度\n"
        "- winner 反映哪方论点更有说服力\n"
        "- 即使多方胜，也要指出残余风险"
    )
    user_prompt = (
        f"决策问题：{task}\n\n"
        f"多方论点：\n{bull_arg[:600]}\n\n"
        f"空方论点：\n{bear_arg[:600]}\n\n"
        f"魔鬼代言人论点：\n{devil_arg[:600]}\n\n"
        f"请给出裁判判断（JSON格式）："
    )
    try:
        raw = llm(user_prompt, system=system_prompt, temperature=0.3)
        # 提取 JSON
        import re
        m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw, re.DOTALL)
        if m:
            result = json.loads(m.group())
            result["argument"] = f"Bull {result.get('bull_score',5)}/10 | Bear {result.get('bear_score',5)}/10 | {result.get('reasoning','')}"
            return result
        return {"verdict": raw[:200], "confidence": 0.5, "bull_score": 5, "bear_score": 5,
                "winner": "tie", "argument": raw[:500]}
    except Exception as e:
        return {"verdict": "（裁判失败）", "confidence": 0.5, "bull_score": 5,
                "bear_score": 5, "winner": "tie", "argument": f"[错误: {e}]"}


def _extract_insights(turns: List[DebateTurn]) -> List[str]:
    """从辩论中提取关键洞察"""
    insights = []
    for t in turns:
        if t.speaker in ("bull", "bear", "devil"):
            # 取论点前100字作为洞察
            insight = t.argument[:100].replace("\n", " ").strip()
            if insight:
                insights.append(f"[{t.speaker_name}] {insight}...")
    return insights[:6]  # 最多6条


def format_debate_report(report: DebateReport) -> str:
    """把 DebateReport 格式化为可读文本"""
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  🗳️ 多方辩论报告")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  辩题：{report.task[:80]}")
    lines.append(f"  辩论ID：{report.debate_id}")
    lines.append("")

    for turn in report.turns:
        icon = {"bull": "🐂", "bear": "🐻", "devil": "😈", "judge": "⚖️",
                "bull_rebuttal": "🐂💬", "bear_rebuttal": "🐻💬"}.get(turn.speaker, "💬")
        lines.append(f"  {icon} 【{turn.speaker_name}】")
        # 截断论点
        arg = turn.argument[:200].replace("\n", " ")
        lines.append(f"     {arg}{'...' if len(turn.argument) > 200 else ''}")
        if turn.score > 0:
            lines.append(f"     评分：{turn.score}/10")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  ⚖️ 最终裁判")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  结论：{report.final_verdict}")
    lines.append(f"  置信度：{report.final_confidence:.0%}")
    lines.append(f"  比分：🐂{report.bull_score:.1f} vs 🐻{report.bear_score:.1f}")
    if report.winner == "bull":
        lines.append("  胜方：🐂 多方（支持方论据更有力）")
    elif report.winner == "bear":
        lines.append("  胜方：🐻 空方（反对方论据更有力）")
    else:
        lines.append("  结果：平局（双方势均力敌）")
    lines.append(f"  置信度调整：{report.confidence_adjustment:+.0%}")
    lines.append("")

    if report.key_insights:
        lines.append("  💡 关键洞察：")
        for ins in report.key_insights[:4]:
            lines.append(f"    · {ins[:100]}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
