"""
lesson_recognition.py — 模式错误识别

从错误中总结可复用教训，识别重复模式
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class PatternWarning:
    """模式警告"""
    pattern_name: str
    description: str
    matched: bool
    severity: float  # 0-1, 越高越严重
    suggestion: str


# 常见错误模式库
COMMON_PATTERNS = [
    {
        "name": "跳过实事求是检查",
        "description": "没有先做调查研究就下结论",
        "hint_words": ["大概", "差不多", "应该是", "可能"],
        "severity": 0.8,
        "suggestion": "回到事实，先核实关键信息",
    },
    {
        "name": "确认偏差",
        "description": "只找支持自己观点的证据",
        "hint_words": ["我就说", "果然", "你看", "没错吧"],
        "severity": 0.7,
        "suggestion": "强制找三个反对证据",
    },
    {
        "name": "近因效应",
        "description": "被最近发生的事情过度影响",
        "hint_words": ["最近", "刚才", "刚刚", "这一次"],
        "severity": 0.5,
        "suggestion": "拉长线看统计规律，不要被单次影响",
    },
    {
        "name": "忽略机会成本",
        "description": "只看表面收益，不算真正代价",
        "hint_words": ["只要做成了", "总收益", "只要", "肯定赚"],
        "severity": 0.7,
        "suggestion": "问一句：如果不做这个，我还能做什么？",
    },
    {
        "name": "时间折扣",
        "description": "高估即时收益，低估长期复利",
        "hint_words": ["现在", "马上", "立刻", "今天", "快点"],
        "severity": 0.6,
        "suggestion": "五年后看，这件事的价值还在吗？",
    },
    {
        "name": "群体压力",
        "description": "因为大家都这样所以跟着走",
        "hint_words": ["别人都", "大家都", "都说", "都是这么做"],
        "severity": 0.6,
        "suggestion": "别人做是别人的事，你真的认同吗？",
    },
    {
        "name": "情绪驱动",
        "description": "强烈情绪影响判断",
        "hint_words": ["气死我了", "太开心", "必须", "马上", "绝了"],
        "severity": 0.8,
        "suggestion": "冷静 24 小时再决定，不急这一天",
    },
    {
        "name": "抓错主要矛盾",
        "description": "精力放在次要问题，核心问题没解决",
        "hint_words": ["先把这个做了", "顺便", "其实这个也", "一起"],
        "severity": 0.7,
        "suggestion": "停！现在问：真正要解决的问题到底是什么？",
    },
]


def get_pattern_warnings(text: str) -> List[PatternWarning]:
    """识别文本中可能的错误模式警告"""
    warnings = []

    for pattern in COMMON_PATTERNS:
        matched = False
        for word in pattern["hint_words"]:
            if word in text:
                matched = True
                break

        warnings.append(PatternWarning(
            pattern_name=pattern["name"],
            description=pattern["description"],
            matched=matched,
            severity=pattern["severity"],
            suggestion=pattern["suggestion"],
        ))

    return [w for w in warnings if w.matched]


def format_pattern_warnings(warnings: List[PatternWarning]) -> str:
    """格式化模式警告"""
    if not warnings:
        return ""

    lines = ["⚠️ 【错误模式检测】", ""]
    for w in sorted(warnings, key=lambda x: -x.severity):
        lines.append(f"  [{w.pattern_name}] {w.description}")
        lines.append(f"    💡 {w.suggestion}")
    lines.append("")

    return "\n".join(lines)


@dataclass
class MistakeAnalysis:
    """错误分析"""
    title: str
    context: str
    mistake_description: str
    pattern: Optional[str]
    lesson: str
    prevent_next_time: str


def analyze_mistake(analysis: MistakeAnalysis) -> Dict:
    """结构化分析一个错误，用于后续模式匹配"""
    return {
        "title": analysis.title,
        "context": analysis.context,
        "description": analysis.mistake_description,
        "pattern": analysis.pattern,
        "lesson": analysis.lesson,
        "prevention": analysis.prevent_next_time,
        "timestamp": None,  # 调用方填写
    }
