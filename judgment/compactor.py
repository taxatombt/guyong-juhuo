#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compactor.py — Juhuo Context 压缩器

借鉴 Codex Compaction：对话历史太长时，压缩为摘要

触发条件：
- Token 超过阈值
- 或者手动触发

压缩策略：
1. 提取关键决策点
2. 保留重要的 judgment chains
3. 生成摘要
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from judgment.logging_config import get_logger
log = get_logger("juhuo.compactor")


# 配置
MAX_HISTORY_ITEMS = 100    # 保留最近 N 条
TOKEN_THRESHOLD = 8000     # 超过这个 token 数触发压缩
COMPACTION_DIR = Path(__file__).parent.parent / "data" / "compactions"


@dataclass
class CompactionRecord:
    """压缩记录"""
    id: str
    timestamp: str
    original_count: int
    compacted_count: int
    summary: str
    preserved_chain_ids: List[str]  # 保留的判断链


@dataclass
class CompactionResult:
    """压缩结果"""
    success: bool
    compacted_items: List[Dict]
    summary: str
    preserved_chains: List[str]


def compact_history(items: List[Dict], reason: str = "auto") -> CompactionResult:
    """
    压缩对话历史
    
    Args:
        items: 历史条目列表
        reason: 压缩原因
        
    Returns:
        CompactionResult
    """
    log.info(f"Starting compaction: {len(items)} items, reason={reason}")
    
    if len(items) <= MAX_HISTORY_ITEMS:
        return CompactionResult(
            success=True,
            compacted_items=items,
            summary="No compaction needed",
            preserved_chains=[]
        )
    
    # 1. 识别重要的 judgment chains
    preserved_chains = []
    compacted = []
    
    for item in items:
        # 保留有 verdict 的判断
        if item.get("type") == "judgment" and item.get("verdict"):
            preserved_chains.append(item.get("chain_id", ""))
            compacted.append(item)
        # 保留最近的 MAX_HISTORY_ITEMS/2 条
        elif len(compacted) < MAX_HISTORY_ITEMS // 2:
            compacted.append(item)
    
    # 2. 生成摘要
    summary = _generate_summary(items, len(compacted))
    
    # 3. 保存压缩记录
    record = CompactionRecord(
        id=f"compact_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        timestamp=datetime.now().isoformat(),
        original_count=len(items),
        compacted_count=len(compacted),
        summary=summary,
        preserved_chain_ids=preserved_chains
    )
    
    _save_compaction_record(record)
    
    log.info(f"Compaction complete: {len(items)} -> {len(compacted)} items")
    
    return CompactionResult(
        success=True,
        compacted_items=compacted,
        summary=summary,
        preserved_chains=preserved_chains
    )


def _generate_summary(items: List[Dict], kept: int) -> str:
    """生成压缩摘要"""
    judgments = [i for i in items if i.get("type") == "judgment"]
    correct = sum(1 for i in judgments if i.get("verdict") == "correct")
    
    summary = f"压缩摘要：共 {len(items)} 条，保留 {kept} 条。"
    if judgments:
        summary += f" 其中 {len(judgments)} 个判断，准确率 {correct/len(judgments):.0%}。"
    
    return summary


def _save_compaction_record(record: CompactionRecord) -> None:
    """保存压缩记录"""
    COMPACTION_DIR.mkdir(parents=True, exist_ok=True)
    file = COMPACTION_DIR / f"{record.id}.json"
    with open(file, "w", encoding="utf-8") as f:
        json.dump(asdict(record), f, ensure_ascii=False, indent=2)


def get_compaction_history(limit: int = 10) -> List[CompactionRecord]:
    """获取压缩历史"""
    records = []
    if not COMPACTION_DIR.exists():
        return records
    
    for file in sorted(COMPACTION_DIR.glob("*.json"), reverse=True)[:limit]:
        with open(file, "r", encoding="utf-8") as f:
            records.append(CompactionRecord(**json.load(f)))
    
    return records


def restore_from_compaction(compaction_id: str) -> Optional[List[Dict]]:
    """从压缩记录恢复"""
    file = COMPACTION_DIR / f"{compaction_id}.json"
    if not file.exists():
        return None
    
    with open(file, "r", encoding="utf-8") as f:
        record = CompactionRecord(**json.load(f))
    
    return record.preserved_chain_ids


if __name__ == "__main__":
    print("Compactor CLI")
    history = get_compaction_history()
    for r in history:
        print(f"{r.timestamp}: {r.original_count} -> {r.compcated_count} items")
