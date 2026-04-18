#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verdict_collector.py — Verdict 数据自动积累

问题：verdict_outcomes.jsonl 样本量不够，统计意义不足
解决：从 session 历史自动抽取 verdict 案例

数据源：
1. 本地 session 历史 (chats.jsonl)
2. OpenClaw session 数据 (如果可用)
3. 手动导入

目标：至少 50+ 条有效 verdict 才能做有意义的进化判断
"""

from __future__ import annotations
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


# ═══════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════

# 配置（引用集中配置，不重复定义）
try:
    from .config import MIN_VERDICTS_FOR_EVOLUTION as MIN_VERDICTS
except ImportError:
    MIN_VERDICTS = 50  # 兼容旧环境
MIN_VERDICTS_FOR_EVOLUTION = MIN_VERDICTS  # 保持向后兼容
BATCH_SIZE = 10  # 每次导入的批量大小

DATA_DIR = Path(__file__).parent.parent / "data"
VERDICT_FILE = DATA_DIR / "verdicts" / "auto_verdicts.jsonl"
SESSION_CACHE = DATA_DIR / "sessions_cache.json"


# ═══════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class VerdictRecord:
    """判决记录"""
    chain_id: str
    task_text: str
    timestamp: str
    verdict: str  # correct / wrong / partial
    source: str  # session / manual / imported
    metadata: Dict = None
    
    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "task_text": self.task_text,
            "timestamp": self.timestamp,
            "verdict": self.verdict,
            "source": self.source,
            "metadata": self.metadata or {}
        }


# ═══════════════════════════════════════════════════════════════════════════
# 核心函数
# ═══════════════════════════════════════════════════════════════════════════

def ensure_dir():
    """确保目录存在"""
    VERDICT_FILE.parent.mkdir(parents=True, exist_ok=True)


def save_verdict(record: VerdictRecord) -> bool:
    """保存一条 verdict"""
    ensure_dir()
    try:
        with open(VERDICT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print(f"[VerdictCollector] Save error: {e}")
        return False


def load_verdicts(limit: Optional[int] = None) -> List[VerdictRecord]:
    """加载 verdict 记录"""
    ensure_dir()
    verdicts = []
    
    try:
        with open(VERDICT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        verdicts.append(VerdictRecord(**data))
                        if limit and len(verdicts) >= limit:
                            break
                    except:
                        continue
    except FileNotFoundError:
        pass
    
    return verdicts


def count_verdicts() -> Dict[str, int]:
    """统计 verdict 数量"""
    verdicts = load_verdicts()
    counts = {
        "total": len(verdicts),
        "correct": sum(1 for v in verdicts if v.verdict == "correct"),
        "wrong": sum(1 for v in verdicts if v.verdict == "wrong"),
        "partial": sum(1 for v in verdicts if v.verdict == "partial"),
    }
    counts["accuracy"] = counts["correct"] / counts["total"] if counts["total"] > 0 else 0
    return counts


def is_ready_for_evolution() -> Tuple[bool, Dict]:
    """
    检查是否准备好进行进化
    
    Returns:
        (is_ready, stats)
    """
    stats = count_verdicts()
    ready = stats["total"] >= MIN_VERDICTS_FOR_EVOLUTION
    return ready, stats


# ═══════════════════════════════════════════════════════════════════════════
# Session 数据导入
# ═══════════════════════════════════════════════════════════════════════════

def import_from_chats(chats_file: Path, limit: int = 100) -> int:
    """
    从 chats.json 导入 verdict 案例
    
    分析对话历史，提取：
    - 用户的判断请求
    - verdict 关键词 (正确/错误/对了/错了)
    
    Args:
        chats_file: chats.json 路径
        limit: 最多导入多少条
        
    Returns:
        实际导入数量
    """
    if not chats_file.exists():
        print(f"[VerdictCollector] File not found: {chats_file}")
        return 0
    
    try:
        with open(chats_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"[VerdictCollector] Invalid JSON: {chats_file}")
        return 0
    
    imported = 0
    verdict_patterns = [
        r"正确", r"错误", r"对了", r"错了",
        r"判断正确", r"判断错误",
        r"准确", r"不准",
        r"correct", r"wrong",
    ]
    
    # 遍历对话，提取 verdict
    tasks = []
    for chat in data.get("chats", []) if isinstance(data, dict) else data:
        messages = chat.get("messages", []) if isinstance(chat, dict) else chat
        
        for i, msg in enumerate(messages):
            if isinstance(msg, dict):
                content = msg.get("content", "")
                role = msg.get("role", "")
            else:
                content = str(msg)
                role = ""
            
            # 用户消息可能是判断请求
            if role == "user" and len(content) > 5:
                # 查找后续 assistant 消息中的 verdict
                for j in range(i + 1, min(i + 5, len(messages))):
                    next_msg = messages[j]
                    next_content = next_msg.get("content", "") if isinstance(next_msg, dict) else str(next_msg)
                    
                    for pattern in verdict_patterns:
                        if re.search(pattern, next_content):
                            tasks.append(content[:200])  # 截断
                            break
    
    # 保存为 verdict
    for task in tasks[:limit]:
        chain_id = f"imported_{int(time.time())}_{imported}"
        verdict = "correct"  # 默认 correct（需要人工审核）
        
        record = VerdictRecord(
            chain_id=chain_id,
            task_text=task,
            timestamp=datetime.now().isoformat(),
            verdict=verdict,
            source="imported",
            metadata={"original_file": str(chats_file)}
        )
        
        if save_verdict(record):
            imported += 1
    
    return imported


# ═══════════════════════════════════════════════════════════════════════════
# 新增：从 juhuo 自有 judgment_db 生成种子 verdict（最可靠来源）
# ═══════════════════════════════════════════════════════════════════════════

def import_from_judgment_db(limit: int = 30) -> int:
    """
    从 juhuo 的 judgment_db.sqlite 抽取 judgment_snapshots 作为种子 verdict。

    这些是 juhuo 自身产生的判断记录，每条都是完整的：
    task_text + complexity + answers + confidence + emotion_label
    可以直接作为 verdict 案例的来源。

    Returns:
        导入数量
    """
    imported = 0
    try:
        from .judgment_db import get_conn
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT chain_id, task_text, complexity, answers, confidence,
                       emotion_label, outcome_auto, corrected
                FROM judgment_snapshots
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

        for row in rows:
            task = row["task_text"] or ""
            if not task:
                continue

            # 已有明确 verdict 的（corrected=1），直接用
            if row["corrected"]:
                outcome = "correct" if row["outcome_auto"] and row["outcome_auto"] > 0.5 else "wrong"
            else:
                outcome = "partial"  # 未反馈的，标记为 partial

            chain_id = f"seed_{row['chain_id']}"
            record = VerdictRecord(
                chain_id=chain_id,
                task_text=task[:500],
                timestamp=datetime.now().isoformat(),
                verdict=outcome,
                source="judgment_db_seed",
                metadata={
                    "complexity": row["complexity"],
                    "emotion": row["emotion_label"],
                    "corrected": row["corrected"],
                }
            )
            if save_verdict(record):
                imported += 1

    except Exception as e:
        print(f"[VerdictCollector] import_from_judgment_db error: {e}")
    return imported


# ═══════════════════════════════════════════════════════════════════════════
# 新增：收集状态报告
# ═══════════════════════════════════════════════════════════════════════════

SCENARIO_CATEGORIES = ["career", "finance", "relationship", "education", "health", "family", "investment", "migration", "life"]


def get_collection_status() -> Dict:
    """
    返回当前 verdict 收集状态报告
    
    Returns:
        {
            "total": 42,
            "ready_for_evolution": False,
            "missing_to_target": 8,
            "by_verdict": {"correct": 20, "wrong": 10, "partial": 12},
            "by_category": {"career": 5, "finance": 8, ...},
            "gaps": ["migration", "education"]  # 样本不足的类别
        }
    """
    verdicts = load_verdicts()
    total = len(verdicts)

    by_verdict: Dict[str, int] = {"correct": 0, "wrong": 0, "partial": 0, "pending": 0}
    by_category: Dict[str, int] = {c: 0 for c in SCENARIO_CATEGORIES}
    gaps: list = []

    for v in verdicts:
        verdict = v.get("verdict", "pending")
        if verdict in by_verdict:
            by_verdict[verdict] += 1
        else:
            by_verdict["pending"] += 1

        # 从 task_text 检测场景类别
        task = v.get("task_text", "").lower()
        for cat in SCENARIO_CATEGORIES:
            if cat in task:
                by_category[cat] += 1

    # 识别样本不足的类别（< 3 条）
    for cat, count in by_category.items():
        if count < 3:
            gaps.append(cat)

    return {
        "total": total,
        "ready_for_evolution": is_ready_for_evolution(),
        "missing_to_target": max(0, MIN_VERDICTS_FOR_EVOLUTION - total),
        "target": MIN_VERDICTS_FOR_EVOLUTION,
        "by_verdict": by_verdict,
        "by_category": by_category,
        "gaps": gaps,
    }


def run_full_collection() -> Dict:
    """
    执行完整收集流程（CLI 入口）：
    1. 从 juhuo judgment_db 生成种子
    2. 从 CoPaw sessions 收集
    3. 输出状态报告
    """
    print("[VerdictCollector] 开始完整收集流程...")

    # 1. 从 juhuo 自有数据生成种子
    seed_count = import_from_judgment_db(limit=30)
    print(f"  [judgment_db 种子] 导入 {seed_count} 条")

    # 2. 从 CoPaw sessions 收集
    auto_stats = auto_collect()
    print(f"  [CoPaw sessions] 导入 {auto_stats.get('imported', 0)} 条")

    # 3. 输出状态
    status = get_collection_status()
    print(f"\n[状态] 总计: {status['total']}/{status['target']} verdict")
    print(f"  by verdict: {status['by_verdict']}")
    print(f"  by category: {status['by_category']}")
    if status['gaps']:
        print(f"  ⚠️ 样本不足类别: {status['gaps']}（需补充到 3+ 条）")
    else:
        print(f"  ✅ 全部分类覆盖充足")

    print(f"\n进化就绪: {'✅ 是' if status['ready_for_evolution'] else '❌ 否（还需 ' + str(status['missing_to_target']) + ' 条）'}")
    return status


if __name__ == "__main__":
    run_full_collection()



def import_from_jsonl(jsonl_file: Path, limit: int = 100) -> int:
    """从 JSONL 文件导入 verdict"""
    if not jsonl_file.exists():
        return 0
    
    imported = 0
    
    try:
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                if imported >= limit:
                    break
                    
                try:
                    data = json.loads(line)
                except:
                    continue
                
                # 尝试提取 task 和 verdict
                task = data.get("task", "") or data.get("question", "") or data.get("text", "")
                verdict = data.get("verdict", "") or data.get("result", "")
                
                if task and verdict in ["correct", "wrong", "partial"]:
                    chain_id = f"imported_{int(time.time())}_{imported}"
                    record = VerdictRecord(
                        chain_id=chain_id,
                        task_text=task[:500],
                        timestamp=data.get("timestamp", datetime.now().isoformat()),
                        verdict=verdict,
                        source="imported",
                        metadata={"original_file": str(jsonl_file)}
                    )
                    
                    if save_verdict(record):
                        imported += 1
    except Exception as e:
        print(f"[VerdictCollector] Import error: {e}")
    
    return imported


# ═══════════════════════════════════════════════════════════════════════════
# 新增：从 juhuo 自有 judgment_db 生成种子 verdict（最可靠来源）
# ═══════════════════════════════════════════════════════════════════════════

def import_from_judgment_db(limit: int = 30) -> int:
    """
    从 juhuo 的 judgment_db.sqlite 抽取 judgment_snapshots 作为种子 verdict。

    这些是 juhuo 自身产生的判断记录，每条都是完整的：
    task_text + complexity + answers + confidence + emotion_label
    可以直接作为 verdict 案例的来源。

    Returns:
        导入数量
    """
    imported = 0
    try:
        from .judgment_db import get_conn
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT chain_id, task_text, complexity, answers, confidence,
                       emotion_label, outcome_auto, corrected
                FROM judgment_snapshots
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

        for row in rows:
            task = row["task_text"] or ""
            if not task:
                continue

            # 已有明确 verdict 的（corrected=1），直接用
            if row["corrected"]:
                outcome = "correct" if row["outcome_auto"] and row["outcome_auto"] > 0.5 else "wrong"
            else:
                outcome = "partial"  # 未反馈的，标记为 partial

            chain_id = f"seed_{row['chain_id']}"
            record = VerdictRecord(
                chain_id=chain_id,
                task_text=task[:500],
                timestamp=datetime.now().isoformat(),
                verdict=outcome,
                source="judgment_db_seed",
                metadata={
                    "complexity": row["complexity"],
                    "emotion": row["emotion_label"],
                    "corrected": row["corrected"],
                }
            )
            if save_verdict(record):
                imported += 1

    except Exception as e:
        print(f"[VerdictCollector] import_from_judgment_db error: {e}")
    return imported


# ═══════════════════════════════════════════════════════════════════════════
# 新增：收集状态报告
# ═══════════════════════════════════════════════════════════════════════════

SCENARIO_CATEGORIES = ["career", "finance", "relationship", "education", "health", "family", "investment", "migration", "life"]


def get_collection_status() -> Dict:
    """
    返回当前 verdict 收集状态报告
    
    Returns:
        {
            "total": 42,
            "ready_for_evolution": False,
            "missing_to_target": 8,
            "by_verdict": {"correct": 20, "wrong": 10, "partial": 12},
            "by_category": {"career": 5, "finance": 8, ...},
            "gaps": ["migration", "education"]  # 样本不足的类别
        }
    """
    verdicts = load_verdicts()
    total = len(verdicts)

    by_verdict: Dict[str, int] = {"correct": 0, "wrong": 0, "partial": 0, "pending": 0}
    by_category: Dict[str, int] = {c: 0 for c in SCENARIO_CATEGORIES}
    gaps: list = []

    for v in verdicts:
        verdict = v.get("verdict", "pending")
        if verdict in by_verdict:
            by_verdict[verdict] += 1
        else:
            by_verdict["pending"] += 1

        # 从 task_text 检测场景类别
        task = v.get("task_text", "").lower()
        for cat in SCENARIO_CATEGORIES:
            if cat in task:
                by_category[cat] += 1

    # 识别样本不足的类别（< 3 条）
    for cat, count in by_category.items():
        if count < 3:
            gaps.append(cat)

    return {
        "total": total,
        "ready_for_evolution": is_ready_for_evolution(),
        "missing_to_target": max(0, MIN_VERDICTS_FOR_EVOLUTION - total),
        "target": MIN_VERDICTS_FOR_EVOLUTION,
        "by_verdict": by_verdict,
        "by_category": by_category,
        "gaps": gaps,
    }


def run_full_collection() -> Dict:
    """
    执行完整收集流程（CLI 入口）：
    1. 从 juhuo judgment_db 生成种子
    2. 从 CoPaw sessions 收集
    3. 输出状态报告
    """
    print("[VerdictCollector] 开始完整收集流程...")

    # 1. 从 juhuo 自有数据生成种子
    seed_count = import_from_judgment_db(limit=30)
    print(f"  [judgment_db 种子] 导入 {seed_count} 条")

    # 2. 从 CoPaw sessions 收集
    auto_stats = auto_collect()
    print(f"  [CoPaw sessions] 导入 {auto_stats.get('imported', 0)} 条")

    # 3. 输出状态
    status = get_collection_status()
    print(f"\n[状态] 总计: {status['total']}/{status['target']} verdict")
    print(f"  by verdict: {status['by_verdict']}")
    print(f"  by category: {status['by_category']}")
    if status['gaps']:
        print(f"  ⚠️ 样本不足类别: {status['gaps']}（需补充到 3+ 条）")
    else:
        print(f"  ✅ 全部分类覆盖充足")

    print(f"\n进化就绪: {'✅ 是' if status['ready_for_evolution'] else '❌ 否（还需 ' + str(status['missing_to_target']) + ' 条）'}")
    return status


if __name__ == "__main__":
    run_full_collection()



def auto_collect(days: int = 7) -> Dict:
    """
    自动收集 verdict 数据
    
    从多个数据源收集：
    1. chats.json
    2. chats.jsonl
    3. dialog/ 历史
    
    Args:
        days: 收集最近多少天的数据
        
    Returns:
        收集统计
    """
    stats = {"imported": 0, "sources": {}}
    
    # 1. 收集 chats.json
    chats_file = Path.home() / ".copaw" / "chats.json"
    if chats_file.exists():
        imported = import_from_chats(chats_file)
        stats["imported"] += imported
        stats["sources"]["chats.json"] = imported
    
    # 2. 收集 chats.jsonl
    chatsl_file = Path.home