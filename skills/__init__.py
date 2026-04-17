#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skills — Juhuo Skill 系统

导入入口
"""

from .skill_types import (
    SkillDefinition,
    SkillExecution,
    SkillHookType,
    SkillSource,
    SkillMetadata,
)

from .skill_registry import SkillRegistry

from . import builtin_skills

# 全局注册表实例
registry = SkillRegistry()

# 自动加载内置技能
builtin_skills.register_all(registry)


__all__ = [
    "SkillDefinition",
    "SkillExecution",
    "SkillHookType",
    "SkillSource",
    "SkillMetadata",
    "SkillRegistry",
    "registry",
]
