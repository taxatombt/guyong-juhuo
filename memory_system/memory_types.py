#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_types.py — Juhuo 4类记忆系统

借鉴 Claude Code Memory System 设计：
- user: 用户信息（角色、目标、偏好）
- feedback: 反馈指导（用户告诉 Agent 怎么做）
- project: 项目信息（正在进行的工作）
- reference: 参考信息（外部系统指针）

铁律：可推导信息不存为记忆

设计原则：
- 记忆必须包含"无法从当前上下文推导"的信息
- 代码模式/架构/git历史/文件结构 → 可推导，不存
- 用户偏好/特定反馈/项目背景 → 不可推导，存
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import json
from pathlib import Path


MEMORY_DIR = Path(__file__).parent / "memories"
MEMORY_DIR.mkdir(exist_ok=True)

USER_FILE = MEMORY_DIR / "user_memories.jsonl"
FEEDBACK_FILE = MEMORY_DIR / "feedback_memories.jsonl"
PROJECT_FILE = MEMORY_DIR / "project_memories.jsonl"
REFERENCE_FILE = MEMORY_DIR / "reference_memories.jsonl"


class MemoryType(Enum):
    """记忆类型枚举"""
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


# ═══════════════════════════════════════════════════════════════════════════
# 记忆数据结构
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class BaseMemory:
    """记忆基类"""
    id: str
    content: str              # 记忆内容（自然语言）
    scope: str                # private | team
    created_at: str = ""     # 默认空字符串
    updated_at: str = ""
    used_count: int = 0      # 被召回次数
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "scope": self.scope,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "used_count": self.used_count,
        }


@dataclass
class UserMemory(BaseMemory):
    """
    用户记忆：关于用户是谁、目标、偏好
    
    何时保存：
    - 了解用户的角色（数据科学家 / 学生 / 工程师）
    - 了解用户的偏好（喜欢详细解释 / 喜欢简洁）
    - 了解用户的知识水平（新手 / 专家）
    
    如何使用：
    - 回答时考虑用户背景
    - 解释时使用用户能理解的术语
    """
    scope: str = "private"    # 用户记忆永远是 private
    
    def to_dict(self) -> Dict:
        d = super().to_dict()
        d["type"] = "user"
        return d


@dataclass
class FeedbackMemory(BaseMemory):
    """
    反馈记忆：用户对 Agent 行为的纠正和确认
    
    何时保存：
    - 用户纠正 Agent 的行为（"不要这样做，应该那样"）
    - 用户确认 Agent 的做法正确（"对，就是这样"）
    - 用户给出具体指导（"以后遇到这种情况，优先..."）
    
    如何使用：
    - 下次遇到类似情况时，想起这个反馈
    - 指导 Agent 选择正确的行动路径
    """
    trigger_context: str = ""  # 触发这个反馈的场景
    outcome: str = ""          # correct(正确) / incorrect(错误) / guidance(指导)
    
    def to_dict(self) -> Dict:
        d = super().to_dict()
        d["type"] = "feedback"
        d["trigger_context"] = self.trigger_context
        d["outcome"] = self.outcome
        return d


@dataclass
class ProjectMemory(BaseMemory):
    """
    项目记忆：正在进行的工作、项目目标、已知问题
    
    何时保存：
    - 了解项目的当前状态（"正在重构X模块"）
    - 了解项目的已知问题（"Y功能有bug，暂未修复"）
    - 了解项目的约束（"必须在月底前完成"）
    
    如何使用：
    - 保持对项目整体的认知
    - 避免重复已知的错误
    """
    project_id: str = ""      # 关联的项目ID
    status: str = ""          # active / paused / completed / cancelled
    
    def to_dict(self) -> Dict:
        d = super().to_dict()
        d["type"] = "project"
        d["project_id"] = self.project_id
        d["status"] = self.status
        return d


@dataclass
class ReferenceMemory(BaseMemory):
    """
    参考记忆：外部系统的指针、文档链接、知识库位置
    
    何时保存：
    - 记录某个文档的位置（而不是内容本身）
    - 记录 API 文档的 URL
    - 记录其他系统的入口点
    
    注意：只存指针，内容在外部系统中维护
    """
    source_system: str = ""    # 来源系统
    source_url: str = ""       # 链接/路径
    content_hash: str = ""     # 内容哈希，用于检测变更
    
    def to_dict(self) -> Dict:
        d = super().to_dict()
        d["type"] = "reference"
        d["source_system"] = self.source_system
        d["source_url"] = self.source_url
        d["content_hash"] = self.content_hash
        return d


# ═══════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════

def generate_id(memory_type: MemoryType) -> str:
    """生成记忆ID"""
    import hashlib
    import time
    raw = f"{memory_type.value}_{time.time()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def get_file_path(memory_type: MemoryType) -> Path:
    """获取对应类型的存储文件"""
    mapping = {
        MemoryType.USER: USER_FILE,
        MemoryType.FEEDBACK: FEEDBACK_FILE,
        MemoryType.PROJECT: PROJECT_FILE,
        MemoryType.REFERENCE: REFERENCE_FILE,
    }
    return mapping[memory_type]


def load_memories(memory_type: MemoryType) -> List[Dict]:
    """加载某类型的所有记忆"""
    file_path = get_file_path(memory_type)
    if not file_path.exists():
        return []
    
    memories = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                memories.append(json.loads(line))
    return memories


def save_memory(memory: Dict, memory_type: MemoryType) -> None:
    """保存一条记忆到对应文件"""
    file_path = get_file_path(memory_type)
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(memory, ensure_ascii=False) + "\n")


def increment_used_count(memory_id: str, memory_type: MemoryType) -> None:
    """增加记忆被使用次数"""
    memories = load_memories(memory_type)
    for m in memories:
        if m.get("id") == memory_id:
            m["used_count"] = m.get("used_count", 0) + 1
            break
    
    # 重写文件
    file_path = get_file_path(memory_type)
    with open(file_path, "w", encoding="utf-8") as f:
        for m in memories:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
