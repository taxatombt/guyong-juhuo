#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compressor.py — Juhuo 四道压缩叠加

借鉴Claude Code TS的分层压缩:
- Snip: 提取关键信息片段
- Micro: 压缩成微总结
- Collapse: 合并相似事件
- Auto: 自动选择最佳压缩级别

快慢双流 + 分层压缩 = 更高效的记忆管理
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CompressionLevel(Enum):
    SNIP = "snip"      # 片段提取
    MICRO = "micro"    # 微总结
    COLLAPSE = "collapse"  # 合并压缩
    AUTO = "auto"      # 自动选择


@dataclass
class CompressedChunk:
    level: str
    content: str
    key_points: List[str]
    original_size: int
    compressed_size: int
    compression_ratio: float


class SnipCompressor:
    """Snip: 提取关键信息片段"""

    def compress(self, text: str, max_length: int = 100) -> CompressedChunk:
        # 提取关键信息：问题、决策、结果
        import re
        
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
        
        # 提取关键实体
        entities = re.findall(r"[\u4e00-\u9fa5]{2,4}(?:公司|项目|产品|人|技术|方案|策略)", text)
        for e in entities[:5]:
            key_points.append(f"[实体] {e}")
        
        content = " | ".join(key_points[:5]) if key_points else text[:max_length]
        
        return CompressedChunk(
            level=CompressionLevel.SNIP.value,
            content=content,
            key_points=key_points,
            original_size=len(text),
            compressed_size=len(content),
            compression_ratio=len(content)/len(text) if text else 1.0,
        )


class MicroCompressor:
    """Micro: 压缩成微总结"""

    def compress(self, text: str, max_length: int = 50) -> CompressedChunk:
        import re
        
        # 移除冗余词
        redundant = [r"实际上", r"其实", r"基本上", r"大概", r"可能", r"也许"]
        for r_word in redundant:
            text = re.sub(r_word, "", text)
        
        # 提取核心动作
        actions = re.findall(r"(应该|需要|必须|决定|选择|做了|没做|做了|正在)[^。]+", text)
        
        if actions:
            content = " → ".join([a[:30] for a in actions[:3]])
        else:
            # 取首句
            sentences = re.split(r"[。！？]", text)
            content = sentences[0][:max_length] if sentences else text[:max_length]
        
        return CompressedChunk(
            level=CompressionLevel.MICRO.value,
            content=content,
            key_points=actions[:3],
            original_size=len(text),
            compressed_size=len(content),
            compression_ratio=len(content)/len(text) if text else 1.0,
        )


class CollapseCompressor:
    """Collapse: 合并相似事件"""

    def compress_batch(self, chunks: List[str]) -> CompressedChunk:
        if not chunks:
            return CompressedChunk(
                level=CompressionLevel.COLLAPSE.value,
                content="",
                key_points=[],
                original_size=0,
                compressed_size=0,
                compression_ratio=1.0,
            )
        
        # 简单合并：取最新的 + 统计
        latest = chunks[0][:80] if chunks else ""
        similar_count = len(chunks)
        
        # 提取共同主题
        common = self._extract_common_theme(chunks)
        
        content = f"{latest} (共{similar_count}个相似)"
        if common:
            content = f"{common}: {content}"
        
        return CompressedChunk(
            level=CompressionLevel.COLLAPSE.value,
            content=content,
            key_points=[f"相似事件{similar_count}个", common] if common else [f"相似事件{similar_count}个"],
            original_size=sum(len(c) for c in chunks),
            compressed_size=len(content),
            compression_ratio=len(content)/sum(len(c) for c in chunks) if chunks else 1.0,
        )

    def _extract_common_theme(self, chunks: List[str]) -> str:
        """提取共同主题"""
        import re
        # 提取关键名词
        all_nouns = []
        for chunk in chunks[:5]:
            nouns = re.findall(r"[\u4e00-\u9fa5]{2,4}(?:决策|判断|选择|问题|情况)", chunk)
            all_nouns.extend(nouns)
        
        # 统计出现最多的
        from collections import Counter
        if all_nouns:
            counter = Counter(all_nouns)
            return counter.most_common(1)[0][0] if counter else ""
        return ""


class AutoCompressor:
    """Auto: 自动选择最佳压缩级别"""

    def __init__(self):
        self.snip = SnipCompressor()
        self.micro = MicroCompressor()
        self.collapse = CollapseCompressor()

    def compress(self, text: str, target_ratio: float = 0.3) -> CompressedChunk:
        """
        自动选择压缩级别
        target_ratio: 目标压缩比
        """
        # 先尝试snip
        snip_result = self.snip.compress(text)
        
        # 如果已经满足目标，直接返回
        if snip_result.compression_ratio <= target_ratio:
            return snip_result
        
        # 否则尝试micro
        micro_result = self.micro.compress(text)
        
        if micro_result.compression_ratio <= target_ratio:
            return micro_result
        
        # 最后用collapse
        return self.collapse.compress_batch([text])


class FourLayerCompressor:
    """
    四道压缩叠加 - Claude Code TS分层压缩的Juhuo实现
    
    快流: 即时snippet提取
    慢流: 定期micro/collapse压缩
    """

    def __init__(self):
        self.snip = SnipCompressor()
        self.micro = MicroCompressor()
        self.collapse = CollapseCompressor()
        self.auto = AutoCompressor()

    def fast_compress(self, text: str) -> CompressedChunk:
        """快流：即时snippet提取（用于实时上下文注入）"""
        return self.snip.compress(text)

    def slow_compress(self, text: str, level: CompressionLevel = CompressionLevel.AUTO) -> CompressedChunk:
        """慢流：定期深度压缩（用于长期记忆）"""
        if level == CompressionLevel.SNIP:
            return self.snip.compress(text)
        elif level == CompressionLevel.MICRO:
            return self.micro.compress(text)
        elif level == CompressionLevel.COLLAPSE:
            return self.collapse.compress_batch([text])
        else:
            return self.auto.compress(text)

    def compress_for_context(self, events: List[Dict], max_events: int = 3) -> List[Dict]:
        """
        为上下文压缩历史事件
        只保留最关键的片段
        """
        compressed = []
        
        for event in events[:max_events]:
            # 提取关键信息
            snippet = self.snip.compress(event.get("description", ""))
            
            compressed.append({
                "event_id": event.get("event_id"),
                "compressed_content": snippet.content,
                "key_points": snippet.key_points,
                "compression_level": snippet.level,
                "original_size": snippet.original_size,
                "compressed_size": snippet.compressed_size,
            })
        
        return compressed


# ── 便捷函数 ────────────────────────────────────────────────────────
_compressor: Optional[FourLayerCompressor] = None


def get_compressor() -> FourLayerCompressor:
    global _compressor
    if _compressor is None:
        _compressor = FourLayerCompressor()
    return _compressor


def fast_compress(text: str) -> CompressedChunk:
    """快捷函数：快速压缩"""
    return get_compressor().fast_compress(text)


def slow_compress(text: str, level: CompressionLevel = CompressionLevel.AUTO) -> CompressedChunk:
    """快捷函数：慢速压缩"""
    return get_compressor().slow_compress(text, level)


def compress_for_context(events: List[Dict], max_events: int = 3) -> List[Dict]:
    """快捷函数：为上下文压缩事件"""
    return get_compressor().compress_for_context(events, max_events)

   