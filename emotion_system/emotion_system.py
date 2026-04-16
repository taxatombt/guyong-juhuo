#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emotion_system.py — 情感系统 最小可用版
遵循建议：从小处开始，只做一件事
核心问题：**当前判断带来了什么情绪？这个情绪是不是一个需要重视的信号？**

设计原则：
- 严格依赖顺序：情绪来自判断过程，依赖前面所有底座
- 接口简单：只暴露两个核心方法「检测当前情绪」「判断是不是信号」
- 从小做起：不模拟完整人类情感，只做信号检测
- 持续学习：每次反馈后更新情绪-信号模式

核心逻辑：
1. 从判断文本 + 决策过程中提取情绪标签
2. 判断这个情绪是不是「需要重视的信号」：
   - 焦虑 → 信息不足/风险不确定 → 需要提醒
   - 兴奋 → 高价值机会 → 需要关注
   - 平淡 → 没信号，不用管
3. 信号自动注入判断上下文，提醒使用者
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date
import json
from pathlib import Path

# 文件路径
EMOTIONS_FILE = Path(__file__).parent.parent / "emotions.json"


@dataclass
class EmotionSignal:
    """一条情绪信号"""
    id: int
    task_id: str           # 关联的判断任务ID
    emotion_label: str     # anxiety / excitement / calm / anger / joy
    intensity: float      # 0-1，强度
    is_signal: bool        # 是不是需要重视的信号
    description: str       # 信号描述："焦虑提示信息不足，建议补充信息再判断"
    created_at: str

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "emotion_label": self.emotion_label,
            "intensity": self.intensity,
            "is_signal": self.is_signal,
            "description": self.description,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class EmotionPattern:
    """学习到的情绪模式"""
    label: str
    trigger_context: str   # 什么场景下触发
    signal_probability: float  # 这个情绪是有效信号的概率
    total_count: int
    signal_count: int

    def to_dict(self):
        return {
            "label": self.label,
            "trigger_context": self.trigger_context,
            "signal_probability": self.signal_probability,
            "total_count": self.total_count,
            "signal_count": self.signal_count,
        }


class EmotionSystem:
    """情感系统最小可用版"""

    def __init__(self):
        self.signals: List[EmotionSignal] = []
        self.patterns: Dict[str, EmotionPattern] = {}
        self._current_pad: Dict[str, float] = {"P": 0.5, "A": 0.5, "D": 0.5}
        self._load()

    def _next_id(self) -> int:
        if not self.signals:
            return 1
        return max(s.id for s in self.signals) + 1

    def _load(self):
        if not EMOTIONS_FILE.exists():
            # 初始化默认模式
            self.patterns = {
                "anxiety": EmotionPattern(
                    label="anxiety",
                    trigger_context="信息不足/风险不确定",
                    signal_probability=0.8,
                    total_count=1,
                    signal_count=1,
                ),
                "excitement": EmotionPattern(
                    label="excitement",
                    trigger_context="发现高价值机会",
                    signal_probability=0.7,
                    total_count=1,
                    signal_count=1,
                ),
                "calm": EmotionPattern(
                    label="calm",
                    trigger_context="信息充分/判断明确",
                    signal_probability=0.1,
                    total_count=1,
                    signal_count=0,
                ),
                "anger": EmotionPattern(
                    label="anger",
                    trigger_context="违反原则/被冒犯",
                    signal_probability=0.9,
                    total_count=1,
                    signal_count=1,
                ),
            }
            self._save()
            return

        with open(EMOTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.signals = [EmotionSignal.from_dict(s) for s in data.get("signals", [])]
        if "patterns" in data:
            self.patterns = {
                p["label"]: EmotionPattern(**p)
                for p in data["patterns"]
            }

    def _save(self):
        data = {
            "signals": [s.to_dict() for s in self.signals],
            "patterns": [p.to_dict() for p in self.patterns.values()],
            "updated_at": datetime.now().isoformat(),
        }
        with open(EMOTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def detect_emotion(self, task_text: str, judgment_result: dict) -> EmotionSignal:
        """
        从当前判断任务中检测情绪，判断是不是信号
        核心入口：每次判断完成后调用
        """
        # 简单规则提取情绪（最小可用用规则，以后可以用大模型分类）
        intensity = 0.0
        label = "calm"
        description = ""
        is_signal = False

        # 规则1：低置信度维度多 → 容易焦虑
        low_conf_dims = [
            (dim, conf) for dim, conf in judgment_result.get("dim_confidence", {}).items()
            if conf < 0.5
        ]
        low_conf_count = len(low_conf_dims)
        if low_conf_count >= 2:
            label = "anxiety"
            intensity = min(1.0, low_conf_count * 0.2)
            dims_str = "、".join([d for d, c in low_conf_dims[:4]])  # 最多4个维度
            description = f"焦虑提示：低置信度维度【{dims_str}】{low_conf_count}个，信息不足，建议补充后再判断"
            pattern = self.patterns.get("anxiety")
            is_signal = pattern.signal_probability > 0.5 if pattern else True

        # 规则2：对齐高优先级目标 + 高价值关键词 → 兴奋
        has_high_value_keywords = [kw for kw in ["突破", "机会", "新发现", "超越", "永生", "创新", "成功", "重大"] if kw in task_text]
        if has_high_value_keywords and not label == "anxiety":
            label = "excitement"
            intensity = 0.7
            keywords_str = "、".join(has_high_value_keywords[:3])  # 最多3个关键词
            description = f"兴奋提示：检测到高价值关键词【{keywords_str}】，对齐长期目标，值得深入探索"
            pattern = self.patterns.get("excitement")
            is_signal = pattern.signal_probability > 0.5 if pattern else True

        # 规则3：文本中带负面情绪词 → 愤怒
        has_anger_keywords = [kw for kw in ["生气", "愤怒", "违反", "欺骗", "底线", "背叛", "恶意"] if kw in task_text]
        if has_anger_keywords:
            label = "anger"
            intensity = 0.9
            keywords_str = "、".join(has_anger_keywords[:3])
            description = f"愤怒提示：检测到负面关键词【{keywords_str}】，触及原则底线，需要重新评估"
            pattern = self.patterns.get("anger")
            is_signal = pattern.signal_probability > 0.5 if pattern else True

        # 规则4：风险/损失关键词 → 恐惧
        has_fear_keywords = [kw for kw in ["风险", "损失", "失败", "危险", "失去", "担心", "害怕"] if kw in task_text]
        if has_fear_keywords and label == "calm":
            label = "fear"
            intensity = 0.6
            keywords_str = "、".join(has_fear_keywords[:3])
            description = f"恐惧提示：检测到风险关键词【{keywords_str}】，需要谨慎评估潜在损失"
            pattern = self.patterns.get("fear")
            is_signal = pattern.signal_probability > 0.5 if pattern else True

        # 规则5：纠结/矛盾关键词 → 困惑
        has_conflict_keywords = [kw for kw in ["纠结", "矛盾", "两难", "不确定", "怎么选", "选哪个"] if kw in task_text]
        if has_conflict_keywords and label == "calm":
            label = "confusion"
            intensity = 0.5
            keywords_str = "、".join(has_conflict_keywords[:3])
            description = f"困惑提示：检测到决策冲突【{keywords_str}】，需要多维度分析利弊"
            pattern = self.patterns.get("confusion")
            is_signal = True  # 困惑总是信号

        # 规则6：紧迫/时间压力 → 紧迫感
        has_urgency_keywords = [kw for kw in ["紧急", "马上", "立刻", "时间紧", "来不及", "deadline"] if kw in task_text]
        if has_urgency_keywords and label == "calm":
            label = "urgency"
            intensity = 0.7
            keywords_str = "、".join(has_urgency_keywords[:3])
            description = f"紧迫提示：检测到时间压力【{keywords_str}】，注意不要仓促决策"
            pattern = self.patterns.get("urgency")
            is_signal = True

        # 创建信号
        signal = EmotionSignal(
            id=self._next_id(),
            task_id=judgment_result.get("meta", {}).get("task_id", "unknown"),
            emotion_label=label,
            intensity=intensity,
            is_signal=is_signal,
            description=description,
            created_at=datetime.now().isoformat(),
        )

        self.signals.append(signal)
        self._update_pad(label, intensity)
        self._save()
        return signal

    def _update_pad(self, label: str, intensity: float):
        """根据情绪标签更新 PAD 状态（P=愉悦度, A=激活度, D=支配度）"""
        pad_map = {
            "anxiety":    {"P": -0.3, "A":  0.7, "D": -0.2},
            "excitement": {"P":  0.7, "A":  0.8, "D":  0.3},
            "anger":      {"P": -0.5, "A":  0.9, "D":  0.8},
            "joy":        {"P":  0.9, "A":  0.6, "D":  0.4},
            "sadness":    {"P": -0.7, "A": -0.3, "D": -0.4},
            "fear":       {"P": -0.6, "A":  0.9, "D": -0.6},
            "calm":       {"P":  0.2, "A": -0.2, "D":  0.1},
        }
        base = pad_map.get(label, {"P": 0.0, "A": 0.0, "D": 0.0})
        decay = 0.7  # 旧值权重（平滑过渡）
        for dim in ("P", "A", "D"):
            self._current_pad[dim] = decay * self._current_pad[dim] + (1 - decay) * base[dim]

    def get_pad_state(self) -> Dict[str, float]:
        """返回当前 PAD 状态，供 curiosity/其他系统调用"""
        return dict(self._current_pad)

    def update_pattern(self, signal_id: int, was_signal: bool):
        """
        反馈后更新模式：用户说"这个情绪确实是信号"或"不是"，我们学习
        """
        signal = next((s for s in self.signals if s.id == signal_id), None)
        if not signal:
            return False

        pattern = self.patterns.get(signal.emotion_label)
        if not pattern:
            pattern = EmotionPattern(
                label=signal.emotion_label,
                trigger_context="",
                signal_probability=0.5,
                total_count=0,
                signal_count=0,
            )
            self.patterns[signal.emotion_label] = pattern

        pattern.total_count += 1
        if was_signal:
            pattern.signal_count += 1
        pattern.signal_probability = pattern.signal_count / pattern.total_count
        self._save()
        return True

    def get_current_signal_summary(self, judgment_result: dict) -> str:
        """获取当前判断的情绪信号总结，注入上下文"""
        signal = self.detect_emotion(
            judgment_result.get("task", ""),
            judgment_result
        )
        if not signal.is_signal:
            return ""

        return f"""
💡 情绪信号提醒：
{signal.description}
（情绪强度：{int(signal.intensity * 100)}%）
""".strip()

    def format_report(self) -> str:
        """生成情感系统报告"""
        total_signals = len(self.signals)
        signal_count = sum(1 for s in self.signals if s.is_signal)
        lines = ["情感系统报告\n", f"累计检测 {total_signals} 次情绪，{signal_count} 次是有效信号\n", "### 学习到的情绪模式\n"]

        for p in self.patterns.values():
            lines.append(f"- [{p.label}]: 信号概率 {int(p.signal_probability*100)}%，累计 {p.total_count} 次触发")
            if p.trigger_context:
                lines.append(f"  - 触发场景：{p.trigger_context}")

        lines.append("\n### 最近10条信号")
        for s in self.signals[-10:]:
            mark = "🔴" if s.is_signal else "□"
            lines.append(f"{mark} [{s.emotion_label}] {s.description}")

        return "\n".join(lines)
