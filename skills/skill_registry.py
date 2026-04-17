#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_registry.py — Juhuo Skill 注册表

核心功能：
- 注册技能
- 查找技能
- 执行技能
- 技能钩子管理

使用方式：
    from skills import SkillRegistry, skill
    
    registry = SkillRegistry()
    
    # 注册技能
    @registry.register
    def my_skill(args, context):
        return {"result": f"Processed: {args}"}
    
    # 查找技能
    skill = registry.find("my_skill")
    
    # 执行技能
    result = registry.execute("my_skill", "test args")
"""

from __future__ import annotations
from typing import List, Optional, Dict, Callable, Any, TypeVar, Callable
from pathlib import Path
import importlib.util
import re

from .skill_types import (
    SkillDefinition, SkillExecution, SkillHook,
    SkillHookType, SkillSource, SkillMetadata,
)


T = TypeVar('T', bound=Callable)


class SkillRegistry:
    """
    技能注册表
    
    单例模式，全局唯一
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._skills: Dict[str, SkillDefinition] = {}
        self._handlers: Dict[str, Callable] = {}
        self._hooks: List[SkillHook] = []
        self._metadata: Dict[str, SkillMetadata] = {}
        self._initialized = True
    
    # ── 注册 ────────────────────────────────────────────────────────────────
    
    def register(
        self,
        name: str = None,
        description: str = "",
        when_to_use: str = "",
        argument_hint: str = "",
        allowed_tools: List[str] = None,
        **kwargs
    ) -> Callable:
        """
        装饰器注册技能
        
        @registry.register(
            description="描述",
            when_to_use="何时使用"
        )
        def my_skill(args, context):
            return result
        """
        def decorator(fn: Callable) -> Callable:
            skill_name = name or fn.__name__
            
            # 创建技能定义
            definition = SkillDefinition(
                name=skill_name,
                description=description or fn.__doc__ or "",
                when_to_use=when_to_use,
                argument_hint=argument_hint,
                allowed_tools=allowed_tools or [],
                **kwargs
            )
            
            self._skills[skill_name] = definition
            self._handlers[skill_name] = fn
            
            return fn
        
        return decorator
    
    def register_skill(
        self,
        definition: SkillDefinition,
        handler: Callable
    ) -> None:
        """手动注册技能"""
        self._skills[definition.name] = definition
        self._handlers[definition.name] = handler
    
    def unregister(self, name: str) -> bool:
        """取消注册技能"""
        if name in self._skills:
            del self._skills[name]
            del self._handlers[name]
            return True
        return False
    
    # ── 查询 ────────────────────────────────────────────────────────────────
    
    def get(self, name: str) -> Optional[SkillDefinition]:
        """获取技能定义"""
        return self._skills.get(name)
    
    def get_handler(self, name: str) -> Optional[Callable]:
        """获取技能处理器"""
        return self._handlers.get(name)
    
    def list_all(self) -> List[SkillDefinition]:
        """列出所有技能"""
        return list(self._skills.values())
    
    def list_enabled(self) -> List[SkillDefinition]:
        """列出已启用的技能"""
        return [s for s in self._skills.values() if s.enabled]
    
    def find_by_tag(self, tag: str) -> List[SkillDefinition]:
        """按标签查找"""
        return [s for s in self._skills.values() if tag in s.tags]
    
    def find_by_trigger(self, query: str) -> List[SkillDefinition]:
        """
        根据查询文本查找可能触发的技能
        
        简单实现：匹配 name、description、when_to_use
        未来可升级：embedding 相似度
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        results = []
        
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            
            # 计算匹配分数
            score = 0
            
            # 双向匹配：query 中的词在 skill 字段中
            skill_name_lower = skill.name.lower()
            skill_desc_lower = skill.description.lower()
            skill_when_lower = skill.when_to_use.lower()
            
            for word in query_words:
                if len(word) < 2:
                    continue
                if word in skill_name_lower:
                    score += 3
                if word in skill_desc_lower:
                    score += 2
                if word in skill_when_lower:
                    score += 2
            
            # 或者：skill 字段中的词在 query 中
            for field in [skill_name_lower, skill_desc_lower, skill_when_lower]:
                for word in field.split():
                    if len(word) >= 3 and word in query_lower:
                        score += 1
            
            if score > 0:
                results.append((skill, score))
        
        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in results]
    
    # ── 执行 ────────────────────────────────────────────────────────────────
    
    def execute(
        self,
        name: str,
        args: str = "",
        context: Dict = None
    ) -> SkillExecution:
        """
        执行技能
        
        执行流程：
        1. 触发 pre_execute 钩子
        2. 调用处理器
        3. 触发 post_execute 钩子
        4. 错误时触发 on_error 钩子
        """
        execution = SkillExecution(
            skill_name=name,
            args=args,
            context=context or {}
        )
        
        handler = self._handlers.get(name)
        if not handler:
            execution.mark_error(f"Skill '{name}' not found")
            return execution
        
        # 1. pre_execute 钩子
        self._run_hooks(SkillHookType.PRE_EXECUTE, name, execution)
        
        try:
            # 2. 执行
            result = handler(args, execution.context)
            execution.mark_complete(result)
            
            # 3. post_execute 钩子
            self._run_hooks(SkillHookType.POST_EXECUTE, name, execution)
            
        except Exception as e:
            execution.mark_error(str(e))
            # 4. error 钩子
            self._run_hooks(SkillHookType.ON_ERROR, name, execution)
        
        # 更新调用统计
        metadata = self._metadata.get(name)
        if metadata:
            metadata.invocation_count += 1
        
        return execution
    
    # ── 钩子 ────────────────────────────────────────────────────────────────
    
    def add_hook(
        self,
        hook_type: SkillHookType,
        callback: Callable,
        skill_name: str = ""
    ) -> None:
        """添加钩子"""
        hook = SkillHook(
            hook_type=hook_type,
            callback=callback,
            skill_name=skill_name
        )
        self._hooks.append(hook)
    
    def _run_hooks(
        self,
        hook_type: SkillHookType,
        skill_name: str,
        execution: SkillExecution
    ) -> None:
        """运行指定类型的钩子"""
        for hook in self._hooks:
            if hook.hook_type != hook_type:
                continue
            # 全局钩子 或 针对此技能的钩子
            if not hook.skill_name or hook.skill_name == skill_name:
                try:
                    hook.callback(execution)
                except Exception as e:
                    print(f"[Hook Error] {hook_type.value}: {e}")
    
    # ── 加载 ────────────────────────────────────────────────────────────────
    
    def load_from_file(self, file_path: Path) -> Optional[str]:
        """
        从文件加载技能
        
        文件格式：
        skill_name.py
        ├── SKILL.md (描述)
        └── handler.py (处理器)
        
        或者单个文件：
        skill_name.py
        └── def skill_handler(args, context): ...
        """
        if not file_path.exists():
            return None
        
        skill_name = file_path.stem
        
        # 加载模块
        spec = importlib.util.spec_from_file_location(skill_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 查找处理器函数
        handler = getattr(module, 'skill_handler', None)
        if not handler:
            # 尝试默认命名
            for attr_name in dir(module):
                if attr_name.startswith('_'):
                    continue
                attr = getattr(module, attr_name)
                if callable(attr) and not isinstance(attr, type):
                    handler = attr
                    break
        
        if not handler:
            return None
        
        # 尝试加载 SKILL.md
        skill_dir = file_path.parent
        skill_md = skill_dir / "SKILL.md"
        description = ""
        when_to_use = ""
        
        if skill_md.exists():
            content = skill_md.read_text(encoding="utf-8")
            # 简单解析
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('# '):
                    description = line[2:].strip()
                elif 'when_to_use' in line.lower() or '触发' in line:
                    # 尝试获取下一行
                    if i + 1 < len(lines):
                        when_to_use = lines[i + 1].strip()