#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compactor_v2.py — Juhuo 四道压缩机制

借鉴 Claude Code 四道压缩：
1. Snip Compact: 裁剪历史消息过长部分
2. Micro Compact: 基于 tool_use_id 的细粒度缓存
3. Context Collapse: 把不活跃区域折叠成摘要
4. Auto Compact: 接近阈值时全量压缩
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum

from judgment.logging_config import get_logger
log = get_logger("juhuo.compactor_v2")


class CompactLevel(Enum):
    SNIP = "snip"
    MICRO = "micro"
    COLLAPSE = "collapse"
    AUTO = "auto"


@dataclass
class Region:
    id: str
    start_idx: int
    end_idx: int
    is_active: bool = True
    summary: str = ""
    messages: List[Dict] = field(default_factory=list)


@dataclass
class CompactResult:
    success: bool
    level: CompactLevel
    compacted_messages: List[Dict]
    summary: str
    tokens_saved: int


# 配置
MAX_ACTIVE_REGION = 50
MAX_MESSAGE_LENGTH = 2000
TOKEN_ESTIMATE_PER_CHAR = 0.25
TOKEN_THRESHOLD_SNIP = 6000
TOKEN_THRESHOLD_MICRO = 10000
TOKEN_THRESHOLD_COLLAPSE = 15000
TOKEN_THRESHOLD_AUTO = 20000


class CompactorV2:
    """四道压缩 Compactor"""
    
    def __init__(self):
        self.regions: List[Region] = [Region(id="region_0", start_idx=0, end_idx=0, is_active=True)]
        self.current_region_idx = 0
    
    def estimate_tokens(self, messages: List[Dict]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        total += len(str(item.get("text", "")))
                    else:
                        total += len(str(item))
        return int(total * TOKEN_ESTIMATE_PER_CHAR)
    
    def add_message(self, message: Dict) -> None:
        if not self.regions:
            self.regions = [Region(id="region_0", start_idx=0, end_idx=0, is_active=True)]
        current = self.regions[self.current_region_idx]
        current.messages.append(message)
        current.end_idx = len(current.messages)
        if len(current.messages) > MAX_ACTIVE_REGION:
            self._split_region()
    
    def _split_region(self) -> None:
        current = self.regions[self.current_region_idx]
        mid = len(current.messages) // 2
        new_region = Region(
            id=f"region_{len(self.regions)}",
            start_idx=0, end_idx=mid, is_active=False,
            messages=current.messages[mid:]
        )
        current.messages = current.messages[:mid]
        current.end_idx = mid
        current.is_active = False
        self.regions.append(new_region)
        self.current_region_idx = len(self.regions) - 1
    
    def _get_all_messages(self) -> List[Dict]:
        msgs = []
        for r in self.regions:
            msgs.extend(r.messages)
        return msgs
    
    def compact(self, level: CompactLevel = None) -> CompactResult:
        total_tokens = self.estimate_tokens(self._get_all_messages())
        
        if level is None:
            if total_tokens > TOKEN_THRESHOLD_AUTO:
                level = CompactLevel.AUTO
            elif total_tokens > TOKEN_THRESHOLD_COLLAPSE:
                level = CompactLevel.COLLAPSE
            elif total_tokens > TOKEN_THRESHOLD_MICRO:
                level = CompactLevel.MICRO
            elif total_tokens > TOKEN_THRESHOLD_SNIP:
                level = CompactLevel.SNIP
            else:
                return CompactResult(True, CompactLevel.SNIP, self._get_all_messages(), "No compaction needed", 0)
        
        if level == CompactLevel.SNIP:
            return self._snip_compact()
        elif level == CompactLevel.MICRO:
            return self._micro_compact()
        elif level == CompactLevel.COLLAPSE:
            return self._collapse_compact()
        else:
            return self._auto_compact()
    
    def _snip_compact(self) -> CompactResult:
        messages = self._get_all_messages()
        original_tokens = self.estimate_tokens(messages)
        compacted = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > MAX_MESSAGE_LENGTH:
                msg = msg.copy()
                msg["content"] = content[:MAX_MESSAGE_LENGTH] + "\n...[snipped]"
                msg["_snipped"] = True
            compacted.append(msg)
        new_tokens = self.estimate_tokens(compacted)
        return CompactResult(True, CompactLevel.SNIP, compacted, f"Snipped ~{original_tokens - new_tokens} tokens", original_tokens - new_tokens)
    
    def _micro_compact(self) -> CompactResult:
        messages = self._get_all_messages()
        original_tokens = self.estimate_tokens(messages)
        compacted = []
        tool_calls = {}
        for msg in messages:
            if msg.get("type") == "tool_result" and msg.get("tool_use_id"):
                tool_calls[msg["tool_use_id"]] = msg
            else:
                compacted.append(msg)
        # 保留 tool_calls 引用但简化
        if compacted and "tool_calls" not in compacted[-1]:
            compacted.append({"type": "tool_cache", "count": len(tool_calls)})
        new_tokens = self.estimate_tokens(compacted)
        return CompactResult(True, CompactLevel.MICRO, compacted, f"Micro ~{original_tokens - new_tokens} tokens", original_tokens - new_tokens)
    
    def _collapse_compact(self) -> CompactResult:
        messages = self._get_all_messages()
        original_tokens = self.estimate_tokens(messages)
        compacted = []
        # 折叠非活跃区域为摘要
        for i, region in enumerate(self.regions):
            if region.is_active or i == self.current_region_idx:
                compacted.extend(region.messages)
            elif region.messages:
                # 生成摘要
                summary = self._generate_region_summary(region.messages)
                compacted.append({
                    "type": "collapsed_region",
                    "region_id": region.id,
                    "summary": summary,
                    "message_count": len(region.messages)
                })
        new_tokens = self.estimate_tokens(compacted)
        return CompactResult(True, CompactLevel.COLLAPSE, compacted, f"Collapsed ~{original_tokens - new_tokens} tokens", original_tokens - new_tokens)
    
    def _auto_compact(self) -> CompactResult:
        messages = self._get_all_messages()
        original_tokens = self.estimate_tokens(messages)
        # 保留最近的 20 条 + 关键判断
        compacted = []
        judgments = []
        others = []
        for msg in messages:
            if msg.get("type") == "judgment":
                judgments.append(msg)
            else:
                others.append(msg)
        compacted = others[-20:] + judgments
        compacted.sort(key=lambda x: x.get("timestamp", ""))
        new_tokens = self.estimate_tokens(compacted)
        return CompactResult(True, CompactLevel.AUTO, compacted, f"Auto compressed ~{original_tokens - new_tokens} tokens", original_tokens - new_tokens)
    
    def _generate_region_summary(self, messages: List[Dict]) -> str:
        if not messages:
            return "Empty region"
        first = messages[0].get("content", "")[:50]
        last = messages[-1].get("content", "")[:50]
        return f"Region: {len(messages)} messages, from '{first}' to '{last}'"


# 全局实例
_compactor: Optional[CompactorV2] = None

def get_compactor() -> CompactorV2:
    global _compactor
    if _compactor is None:
        _compactor = CompactorV2()
    return _compactor


if __name__ == "__main__":
    c = get_compactor()
    for i in range(100):
        c.add_message({"type": "message", "content": f"Test message {i}", "timestamp": datetime.now().isoformat()})
    result = c.compact()
    print(f"Level: {result.level.value}")
    print(f"Original messages: 100")
    print(f"Compacted: {len(result.compacted_messages)}")
    print(f"Summary: {result.summary}")
