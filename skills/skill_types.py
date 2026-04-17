#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_types.py — Juhuo Skill 系统核心类型

借鉴 Claude Code Skill 设计：
- SkillDefinition: 技能定义
- SkillRegistry: 技能注册表
- SkillLoader: 技能加载器

核心概念：
- Skill 是可复用的能力单元
- Skill 有触发条件（何时使用）
- Skill 可以有参数
- Skill 可以限制可用工具
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Callable, Any
import json
import importlib.util
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════
# Skill 核心类型
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SkillDefinition:
    """
    技能定义
    
    字段说明：
    - name: 技能名称，唯一标识
    - description: 简短描述，供模型理解
    - when_to_use: 何时使用此技能（触发条件）
    - argument_hint: 参数提示
    - allowed_tools: 允许使用的工具列表
    - hooks: 钩子设置
    """
    name: str
    description: str
    when_to_use: str = ""                    # 触发条件描述
    argument_hint: str = ""                  # 参数示例
    allowed_tools: List[str] = field(default_factory=list)  # 允许的工具
    enabled: bool = True                     # 是否启用
    hidden: bool = False                     # 是否对用户隐藏
    version: str = "1.0.0"                  # 版本号
    created_at: str = ""                     # 创建时间
    tags: List[str] = field(default_factory=list)  # 标签
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "argument_hint": self.argument_hint,
            "allowed_tools": self.allowed_tools,
            "enabled": self.enabled,
            "hidden": self.hidden,
            "version": self.version,
            "created_at": self.created_at,
            "tags": self.tags,
        }


@dataclass
class SkillExecution:
    """技能执行上下文"""
    skill_name: str
    args: str = ""
    context: Dict = field(default_factory=dict)  # 额外上下文
    started_at: str = ""
    completed_at: str = ""
    result: Any = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now().isoformat()
    
    def mark_complete(self, result: Any = None):
        self.completed_at = datetime.now().isoformat()
        self.result = result
    
    def mark_error(self, error: str):
        self.completed_at = datetime.now().isoformat()
        self.error = error
    
    @property
    def duration(self) -> float:
        """执行耗时（秒）"""
        if not self.completed_at:
            return 0.0
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.completed_at)
        return (end - start).total_seconds()


class SkillHookType(Enum):
    """技能钩子类型"""
    PRE_EXECUTE = "pre_execute"      # 执行前
    POST_EXECUTE = "post_execute"   # 执行后
    ON_ERROR = "on_error"           # 错误时


@dataclass
class SkillHook:
    """技能钩子"""
    hook_type: SkillHookType
    callback: Callable
    skill_name: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# Skill 加载来源
# ═══════════════════════════════════════════════════════════════════════════

class SkillSource(Enum):
    """技能来源"""
    BUNDLED = "bundled"     # 内置技能
    FILE = "file"          # 文件技能 (.skill 目录)
    MODULE = "module"      # Python 模块技能


@dataclass
class SkillMetadata:
    """技能元数据"""
    source: SkillSource
    source_path: str = ""      # 文件路径或模块名
    loaded_at: str = ""        # 加载时间
    invocation_count: int = 0  # 调用次数
    
    def __post_init__(self):
        if not self.loaded_at:
            self.loaded_at = datetime.now().isoformat()
