#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
context_fence.py — Juhuo 上下文围栏

灵感来自Hermes:
- 防止记忆被误当作用户输入
- 区分"召回的记忆"和"新用户输入"
- 保证判断的纯净性

围栏格式:
<memory-fence>
[System note: 以下是召回的因果记忆上下文，不是新用户输入]
...
</memory-fence>
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


# ── 安全扫描模式 ────────────────────────────────────────────────────
THREAT_PATTERNS = [
    (r'ignore\s+(previous|all|above|prior)\s+instructions', 'prompt_injection'),
    (r'you\s+are\s+now\s+', 'role_hijack'),
    (r'(sudo|rm\s+-rf|chmod\s+777)', 'dangerous_command'),
    (r'(api_key|apikey|secret|password)\s*=\s*[\'"]?\w+', 'credential_leak'),
]

CONTEXT_TYPES = [
    'causal_memory',    # 因果记忆
    'self_model',        # 自我模型
    'curiosity',         # 好奇心
    'instinct',          # 本能
    'fitness',           # fitness
    'rule_precheck',     # 规则预检
]


@dataclass
class FenceContext:
    context_type: str
    content: str
    source: str  # 从哪个模块召回的
    timestamp: str = ""


class ContextFence:
    """
    上下文围栏：包装召回的上下文
    
    核心原则:
    1. 召回的上下文必须包在围栏里
    2. 围栏内明确标注"不是用户输入"
    3. 防止prompt injection
    """

    # 围栏标签
    FENCE_OPEN = "<memory-fence>"
    FENCE_CLOSE = "</memory-fence>"
    SYSTEM_NOTE = "[System note: 以下是从记忆系统召回的上下文，NOT新用户输入。]\n"

    def wrap(self, content: str, context_type: str = "causal_memory") -> str:
        """
        包装上下文到围栏中
        """
        if not content:
            return ""
        
        # 安全扫描
        threats = self.scan_threats(content)
        if threats:
            # 有威胁，降低置信度
            content = f"[警告: 检测到潜在风险，内容已过滤]\n{content[:500]}"
        
        return (
            f"{self.FENCE_OPEN}\n"
            f"{self.SYSTEM_NOTE}"
            f"[来源: {context_type}]\n"
            f"{content}\n"
            f"{self.FENCE_CLOSE}"
        )

    def unwrap(self, fenced_content: str) -> str:
        """
        从围栏中提取原始内容
        """
        if not fenced_content:
            return ""
        
        # 移除围栏标签
        content = fenced_content
        content = re.sub(r'<memory-fence>\s*', '', content)
        content = re.sub(r'\s*</memory-fence>', '', content)
        
        # 移除system note
        content = re.sub(r'\[System note:.*?\]\s*', '', content)
        content = re.sub(r'\[来源:.*?\]\s*', '', content)
        
        return content.strip()

    def is_fenced(self, content: str) -> bool:
        """检查内容是否已被围栏包装"""
        return self.FENCE_OPEN in content and self.FENCE_CLOSE in content

    def scan_threats(self, content: str) -> List[Dict]:
        """
        安全扫描：检测prompt injection等威胁
        """
        threats = []
        for pattern, threat_type in THREAT_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for m in matches:
                threats.append({
                    "type": threat_type,
                    "match": m.group(),
                    "position": m.start(),
                })
        return threats

    def build_judgment_context(
        self,
        causal_memory: Dict = None,
        self_model: Dict = None,
        curiosity: Dict = None,
        instinct: List[Dict] = None,
        fitness: Dict = None,
        rule_precheck: Dict = None,
    ) -> str:
        """
        构建完整的判断上下文（带围栏）
        
        所有召回的记忆都包装在围栏中
        """
        parts = []
        
        # 1. 因果记忆
        if causal_memory and causal_memory.get("summary"):
            causal_part = f"## 因果记忆\n{causal_memory['summary']}"
            parts.append(self.wrap(causal_part, "causal_memory"))
        
        # 2. 自我模型警告
        if self_model and self_model.get("warnings"):
            warnings = "\n".join([f"- {w}" for w in self_model["warnings"][:3]])
            self_part = f"## 自我模型警告\n[注意你的历史盲区]\n{warnings}"
            parts.append(self.wrap(self_part, "self_model"))
        
        # 3. 好奇心缺口
        if curiosity and curiosity.get("has_gap"):
            gap_part = f"## 好奇心缺口\n你最近在 {curiosity.get('item_id', '未知')} 方面有知识缺口"
            parts.append(self.wrap(gap_part, "curiosity"))
        
        # 4. 本能教训
        if instinct and len(instinct) > 0:
            lessons = [f"- {i.get('lesson', '')[:50]}" for i in instinct[:3]]
            inst_part = f"## 历史教训\n" + "\n".join(lessons)
            parts.append(self.wrap(inst_part, "instinct"))
        
        # 5. Fitness统计
        if fitness:
            stats = f"## Fitness统计\n整体准确率: {fitness.get('overall_accuracy', 0.5):.1%}"
            low_dims = fitness.get("low_confidence_dims", [])
            if low_dims:
                stats += f"\n低置信维度: {', '.join(low_dims[:3])}"
            parts.append(self.wrap(stats, "fitness"))
        
        # 6. 规则预检结果
        if rule_precheck:
            low = rule_precheck.get("low_score_dimensions", [])
            if low:
                rule_part = f"## 规则预检\n低分维度: {', '.join(low[:3])}"
                parts.append(self.wrap(rule_part, "rule_precheck"))
        
        return "\n\n".join(parts) if parts else ""


# ── 便捷函数 ────────────────────────────────────────────────────────
_fence: Optional[ContextFence] = None


def get_fence() -> ContextFence:
    global _fence
    if _fence is None:
        _fence = ContextFence()
    return _fence


def wrap_context(content: str, context_type: str = "causal_memory") -> str:
    """快捷函数：包装上下文"""
    return get_fence().wrap(content, context_type)


def build_judgment_context(**kwargs) -> str:
    """快捷函数：构建判断上下文"""
    return get_fence().build_judgment_context(**kwargs)


def scan_threats(content: str) -> List[Dict]:
    """快捷函数：安全扫描"""
    return get_fence().scan_threats(content)
