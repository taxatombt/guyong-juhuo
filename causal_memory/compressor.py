#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compressor.py — Juhuo 四道压缩 + Hermes五阶段升级

Hermes五阶段压缩:
1. Prune: 裁剪旧工具结果
2. Protect head: 保护头部消息
3. Protect tail: 按token预算保护尾部
4. Summarize middle: 摘要中间轮次
5. Iterative: 迭代更新
"""

import re, json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CompressionLevel(Enum):
    SNIP = "snip"
    MICRO = "micro"
    COLLAPSE = "collapse"
    AUTO = "auto"
    HERMES_FIVE_STAGE = "hermes_five_stage"


@dataclass
class CompressedChunk:
    level: str
    content: str
    key_points: List[str]
    original_size: int
    compressed_size: int
    compression_ratio: float


@dataclass
class HermesCompressionResult:
    original_count: int
    compressed_count: int
    summary: str
    stages_passed: List[str]
    tokens_saved: int


# ── 四道压缩 ──────────────────────────────────────────────────────
class SnipCompressor:
    def compress(self, text: str, max_length: int = 100) -> CompressedChunk:
        key_patterns = [
            (r"([^?？]+[?？])", "问题"),
            (r"(应该|不应该|决定|选择|做|不做)[^。]+", "决策"),
            (r"(结果|所以|因此|最后)[^。]+", "结果"),
        ]
        
        key_points = []
        for pattern, label in key_patterns:
            matches = re.findall(pattern, text)
            for m in matches[:2]:
                key_points.append(f"[{label}] {m[:80]}")
        
        content = " | ".join(key_points[:5]) if key_points else text[:max_length]
        
        return CompressedChunk(
            level=CompressionLevel.SNIP.value,
            content=content, key_points=key_points,
            original_size=len(text), compressed_size=len(content),
            compression_ratio=len(content)/len(text) if text else 1.0,
        )


class MicroCompressor:
    def compress(self, text: str, max_length: int = 50) -> CompressedChunk:
        redundant = [r"实际上", r"其实", r"基本上", r"大概", r"可能", r"也许"]
        for r_word in redundant:
            text = re.sub(r_word, "", text)
        
        actions = re.findall(r"(应该|需要|必须|决定|选择|做了|没做)[^。]+", text)
        
        if actions:
            content = " → ".join([a[:30] for a in actions[:3]])
        else:
            sentences = re.split(r"[。！？]", text)
            content = sentences[0][:max_length] if sentences else text[:max_length]
        
        return CompressedChunk(
            level=CompressionLevel.MICRO.value,
            content=content, key_points=actions[:3],
            original_size=len(text), compressed_size=len(content),
            compression_ratio=len(content)/len(text) if text else 1.0,
        )


class CollapseCompressor:
    def compress_batch(self, chunks: List[str]) -> CompressedChunk:
        if not chunks:
            return CompressedChunk(level="collapse", content="", key_points=[],
                                  original_size=0, compressed_size=0, compression_ratio=1.0)
        
        latest = chunks[0][:80] if chunks else ""
        similar_count = len(chunks)
        common = self._extract_common_theme(chunks)
        
        content = f"{latest} (共{similar_count}个相似)"
        if common:
            content = f"{common}: {content}"
        
        return CompressedChunk(
            level=CompressionLevel.COLLAPSE.value,
            content=content, key_points=[f"相似{similar_count}个"],
            original_size=sum(len(c) for c in chunks),
            compressed_size=len(content),
            compression_ratio=len(content)/sum(len(c) for c in chunks) if chunks else 1.0,
        )

    def _extract_common_theme(self, chunks: List[str]) -> str:
        all_nouns = []
        for chunk in chunks[:5]:
            nouns = re.findall(r"[\u4e00-\u9fa5]{2,4}(?:决策|判断|选择|问题)", chunk)
            all_nouns.extend(nouns)
        if all_nouns:
            from collections import Counter
            return Counter(all_nouns).most_common(1)[0][0]
        return ""


# ── Hermes五阶段压缩 ──────────────────────────────────────────────
class HermesFiveStageCompressor:
    """
    Hermes五阶段压缩
    
    1. Prune: 裁剪旧工具结果
    2. Protect head: 保护头部消息
    3. Protect tail: 按token预算保护尾部
    4. Summarize middle: 摘要中间轮次
    5. Iterative: 迭代更新
    """
    
    SUMMARY_RATIO = 0.20
    SUMMARY_TOKENS_CEILING = 12000
    MAX_TOKENS_PER_MSG = 4000
    PROTECT_LAST_N_TURNS = 4
    
    def compress(self, messages: List[Dict], target_max_tokens: int = 15250) -> HermesCompressionResult:
        """五阶段压缩主入口"""
        stages_passed = []
        original_count = len(messages)
        original_size = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        
        # Stage 1: Prune - 裁剪旧工具结果
        messages = self._stage1_prune(messages)
        stages_passed.append("prune")
        
        # Stage 2: Protect head - 保护头部消息
        messages = self._stage2_protect_head(messages)
        stages_passed.append("protect_head")
        
        # Stage 3: Protect tail - 保护尾部
        messages = self._stage3_protect_tail(messages, target_max_tokens)
        stages_passed.append("protect_tail")
        
        # Stage 4: Summarize middle - 摘要中间
        messages = self._stage4_summarize_middle(messages)
        stages_passed.append("summarize_middle")
        
        # Stage 5: Iterative - 迭代检查
        messages = self._stage5_iterative(messages, target_max_tokens)
        stages_passed.append("iterative")
        
        compressed_count = len(messages)
        compressed_size = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        
        return HermesCompressionResult(
            original_count=original_count,
            compressed_count=compressed_count,
            summary=f"{original_count}条 → {compressed_count}条 (节省{original_size-compressed_size}字符)",
            stages_passed=stages_passed,
            tokens_saved=original_size - compressed_size,
        )
    
    def _stage1_prune(self, messages: List[Dict]) -> List[Dict]:
        """Stage 1: 裁剪旧工具结果"""
        pruned = []
        for msg in messages:
            role = msg.get("role", "")
            if role == "tool" and len(msg.get("content", "")) > self.MAX_TOKENS_PER_MSG:
                content = msg["content"]
                chunk_size = len(content) // 4
                msg["content"] = content[:chunk_size] + "\n...[裁剪]...\n" + content[-chunk_size:]
                msg["_pruned"] = True
            pruned.append(msg)
        return pruned
    
    def _stage2_protect_head(self, messages: List[Dict]) -> List[Dict]:
        """Stage 2: 保护头部消息"""
        protected = []
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            if role == "system" and "system" not in protected:
                msg["_protected"] = True
                protected.append("system")
            elif role == "user" and "user" not in protected:
                msg["_protected"] = True
                protected.append("user")
            elif role == "assistant" and "assistant" not in protected:
                msg["_protected"] = True
                protected.append("assistant")
        return messages
    
    def _stage3_protect_tail(self, messages: List[Dict], budget: int) -> List[Dict]:
        """Stage 3: 按预算保护尾部"""
        if len(messages) <= self.PROTECT_LAST_N_TURNS:
            return messages
        
        # 标记尾部需要保护的
        for msg in messages[-self.PROTECT_LAST_N_TURNS:]:
            msg["_protected_tail"] = True
        
        return messages
    
    def _stage4_summarize_middle(self, messages: List[Dict]) -> List[Dict]:
        """Stage 4: 摘要中间轮次"""
        result = []
        middle_start = None
        middle_end = None
        
        # 找到中间部分
        for i, msg in enumerate(messages):
            if not msg.get("_protected") and not msg.get("_protected_tail"):
                if middle_start is None:
                    middle_start = i
                middle_end = i
        
        if middle_start is None or middle_end - middle_start < 3:
            return messages
        
        # 摘要中间部分
        middle_msgs = messages[middle_start:middle_end+1]
        if middle_msgs:
            summary_content = self._summarize_batch(middle_msgs)
            result = messages[:middle_start] + [{
                "role": "system",
                "content": f"[中间{len(middle_msgs)}条消息摘要]\n{summary_content}",
                "_summarized": True
            }] + messages[middle_end+1:]
            return result
        
        return messages
    
    def _stage5_iterative(self, messages: List[Dict], budget: int) -> List[Dict]:
        """Stage 5: 迭代检查"""
        current_size = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        
        # 如果还超出预算，继续裁剪
        while current_size > budget and len(messages) > 10:
            # 移除最旧的非保护消息
            for i, msg in enumerate(messages):
                if not msg.get("_protected") and not msg.get("_protected_tail") and not msg.get("_summarized"):
                    messages.pop(i)
                    break
            current_size = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        
        return messages
    
    def _summarize_batch(self, msgs: List[Dict]) -> str:
        """批量摘要"""
        if not msgs:
            return ""
        
        # 提取关键信息
        key_contents = []
        for msg in msgs[:10]:
            content = msg.get("content", "")[:200]
            if content:
                key_contents.append(content)
        
        return "\n".join([f"- {c[:100]}" for c in key_contents[:5]])


# ── 主压缩器 ──────────────────────────────────────────────────────
class FourLayerCompressor:
    """四道压缩 + Hermes五阶段"""
    
    def __init__(self):
        self.snip = SnipCompressor()
        self.micro = MicroCompressor()
        self.collapse = CollapseCompressor()
        self.hermes = HermesFiveStageCompressor()
    
    def fast_compress(self, text: str) -> CompressedChunk:
        """快流：即时snippet"""
        return self.snip.compress(text)
    
    def slow_compress(self, text: str, level: str = "auto") -> CompressedChunk:
        """慢流：深度压缩"""
        if level == "snip":
            return self.snip.compress(text)
        elif level == "micro":
            return self.micro.compress(text)
        elif level == "collapse":
            return self.collapse.compress_batch([text])
        else:
            result = self.micro.compress(text)
            if result.compression_ratio > 0.3:
                result = self.collapse.compress_batch([text])
            return result
    
    def hermes_compress(self, messages: List[Dict], budget: int = 15250) -> HermesCompressionResult:
        """Hermes五阶段压缩"""
        return self.hermes.compress(messages, budget)
    
    def compress_for_context(self, events: List[Dict], max_events: int = 3) -> List[Dict]:
        """为上下文压缩事件"""
        compressed = []
        for event in events[:max_events]:
            snippet = self.snip.compress(event.get("description", ""))
            compressed.append({
                "event_id": event.get("event_id"),
                "compressed_content": snippet.content,
                "key_points": snippet.key_points,
            })
        return compressed


# ── 便捷函数 ──────────────────────────────────────────────────────
_compressor: Optional[FourLayerCompressor] = None

def get_compressor() -> FourLayerCompressor:
    global _compressor
    if _compressor is None:
        _compressor = FourLayerCompressor()
    return _compressor

def fast_compress(text: str) -> CompressedChunk:
    return get_compressor().fast_compress(text)

def slow_compress(text: str, level: str = "auto") -> CompressedChunk:
    return get_compressor().slow_compress(text, level)

def hermes_compress(messages: List[Dict], budget: int = 15250) -> HermesCompressionResult:
    return get_compressor().hermes_compress(messages, budget)

def compress_for_context(events: List[Dict], max_events: int = 3) -> List[Dict]:
    return get_compressor().compress_for_context(events, max_events)


# ═══════════════════════════════════════════════════════════════════════════
# ml-intern 启发：Token 阈值检测 + LLM 摘要压缩
# ═══════════════════════════════════════════════════════════════════════════

# Token 估算：中文 ≈ 0.25 char/token，英文 ≈ 0.33 char/token
_CHARS_PER_TOKEN = 0.28

# 默认触发阈值（ml-intern 用 model_max_tokens * 0.85）
# Juhuo 用 15 万 token 阈值
DEFAULT_TOKEN_THRESHOLD = 150_000  # 15 万 token
COMPACTION_TRIGGER_RATIO = 0.85    # 达到 85% 触发压缩


class TokenBudget:
    """
    Token 预算追踪器（ml-intern ContextManager 启发）。

    跟踪当前上下文 token 消耗，当接近阈值时触发压缩。
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_TOKEN_THRESHOLD,
        trigger_ratio: float = COMPACTION_TRIGGER_RATIO,
    ):
        self.max_tokens = max_tokens
        self.trigger_ratio = trigger_ratio
        self.current_tokens = 0
        self.compactions = 0
        self.last_compaction_tokens = 0

    @property
    def trigger_threshold(self) -> int:
        return int(self.max_tokens * self.trigger_ratio)

    @property
    def needs_compaction(self) -> bool:
        return self.current_tokens >= self.trigger_threshold

    def estimate_tokens(self, text: str) -> int:
        """估算文本 token 数（简化版，非精确）"""
        return int(len(str(text)) * _CHARS_PER_TOKEN)

    def estimate_messages_tokens(self, messages: list) -> int:
        """估算消息列表总 token 数"""
        total = 0
        for msg in messages:
            if isinstance(msg, dict):
                content = str(msg.get("content", ""))
            else:
                content = str(getattr(msg, "content", ""))
            total += self.estimate_tokens(content)
        return total

    def update_from_messages(self, messages: list) -> None:
        """从消息列表更新 token 计数"""
        self.current_tokens = self.estimate_messages_tokens(messages)

    def report(self) -> dict:
        return {
            "current_tokens": self.current_tokens,
            "max_tokens": self.max_tokens,
            "trigger_threshold": self.trigger_threshold,
            "usage_ratio": self.current_tokens / self.max_tokens if self.max_tokens > 0 else 0,
            "needs_compaction": self.needs_compaction,
            "compactions": self.compactions,
        }


# ml-intern 的 _COMPACT_PROMPT（翻译为中文场景适配）
_COMPACT_PROMPT_CN = (
    "请对以上对话进行简洁摘要，重点关注：\n"
    "  1. 关键决策及其原因\n"
    "  2. 已解决的问题\n"
    "  3. 后续开发所需的重要上下文\n"
    "  4. 当前判断的核心分歧点\n"
    "你的摘要将给一个新的判断者阅读，让他们能快速接手当前工作。"
)


async def compact_with_llm(
    messages: list,
    llm_callable,
    model: str = "MiniMax-M2.7",
    max_output_tokens: int = 2048,
) -> tuple[list, str]:
    """
    用 LLM 对历史消息进行摘要压缩（ml-intern ContextManager 思路）。

    Args:
        messages: 原始消息列表
        llm_callable: LLM 调用函数，签名同 judgment.llm_calls 中的实现
        model: 使用的模型
        max_output_tokens: 摘要最大 token 数

    Returns:
        (compressed_messages, summary) — 压缩后消息列表 + 摘要文本
    """
    if not messages:
        return [], ""

    # 构造摘要消息
    summary_request = [
        {"role": "user", "content": _COMPACT_PROMPT_CN},
    ]
    # 把历史消息拼进去
    history_text = ""
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "")
        history_text += f"\n[{role}] {content[:500]}"
    summary_request[0]["content"] = _COMPACT_PROMPT_CN + history_text

    try:
        result = await llm_callable(
            messages=summary_request,
            model=model,
            max_tokens=max_output_tokens,
            temperature=0.3,  # 低温度，保持准确性
        )
        summary = result if isinstance(result, str) else (result.get("content", "") or "")
    except Exception as e:
        summary = f"[摘要失败: {e}]"

    # 保留最近 3 条消息 + 摘要
    keep_tail = messages[-3:] if len(messages) >= 3 else messages
    compressed = [
        {
            "role": "system",
            "content": f"[对话摘要] {summary}",
            "_compacted": True,
            "_original_count": len(messages),
        }
    ] + keep_tail

    return compressed, summary


# ── 便捷函数 ──────────────────────────────────────────────────────
_token_budget: TokenBudget | None = None


def get_token_budget() -> TokenBudget:
    global _token_budget
    if _token_budget is None:
        _token_budget = TokenBudget()
    return _token_budget


def check_token_budget(messages: list) -> dict:
    """快速检查当前 token 预算状态。"""
    budget = get_token_budget()
    budget.update_from_messages(messages)
    return budget.report()

