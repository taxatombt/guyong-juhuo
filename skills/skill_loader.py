#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_loader.py — Juhuo Skills 按需加载系统

借鉴 OpenClaw：Skills 不全文注入，只注入 metadata。
模型需要时，按需读取 SKILL.md。

结构：
- skill_registry: 所有 skills 的 metadata
- 按需加载：只读取被调用的 skill
- 缓存：已加载的 skill 保持内存
"""

from __future__ import annotations
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path
import json, hashlib
from datetime import datetime

from judgment.logging_config import get_logger
log = get_logger("juhuo.skill_loader")


@dataclass
class SkillMetadata:
    """Skill 元数据（注入 prompt 的部分）"""
    name: str
    description: str
    location: str       # 文件路径
    tags: List[str]     # 触发关键词
    file_size: int      # 原始文件大小
    loaded: bool = False
    
    def to_prompt(self) -> str:
        """转为 prompt 中的 metadata 格式"""
        return f"""<skill>
  <name>{self.name}</name>
  <description>{self.description}</description>
  <location>{self.location}</location>
  <tags>{', '.join(self.tags)}</tags>
</skill>"""


@dataclass
class LoadedSkill:
    """已加载的 Skill 完整内容"""
    metadata: SkillMetadata
    content: str
    functions: List[Callable] = field(default_factory=list)
    loaded_at: datetime = field(default_factory=datetime.now)


class SkillLoader:
    """
    Skills 按需加载器
    
    OpenClaw 启发：
    - Skills 不全文注入 prompt
    - 只注入 metadata（name/description/location）
    - 模型需要时，读取 SKILL.md
    - 已加载的 skill 保持缓存
    """
    
    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or Path(__file__).parent.parent / "skills"
        self.registry: Dict[str, SkillMetadata] = {}
        self.cache: Dict[str, LoadedSkill] = {}
        self._scan_skills()
    
    def _scan_skills(self) -> None:
        """扫描所有 skills，建立 registry"""
        if not self.skills_dir.exists():
            return
        
        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir():
                continue
            
            skill_md = skill_path / "SKILL.md"
            if skill_md.exists():
                metadata = self._parse_skill_metadata(skill_path, skill_md)
                self.registry[metadata.name] = metadata
                log.info(f"Registered skill: {metadata.name}")
    
    def _parse_skill_metadata(self, skill_path: Path, skill_md: Path) -> SkillMetadata:
        """从 SKILL.md 解析 metadata"""
        content = skill_md.read_text(encoding="utf-8")
        
        # 简单解析 frontmatter
        name = skill_path.name
        description = ""
        tags = []
        
        for line in content.split("\n"):
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("tags:"):
                tags = [t.strip().strip('"').strip("'") for t in line.split(":", 1)[1].strip().split(",")]
        
        # 提取 description 如果没有 frontmatter
        if not description:
            for line in content.split("\n"):
                if line.startswith("# "):
                    description = line[2:].strip()
                    break
        
        return SkillMetadata(
            name=name,
            description=description,
            location=str(skill_md),
            tags=tags,
            file_size=skill_md.stat().st_size
        )
    
    def get_available_skills_prompt(self) -> str:
        """获取所有可用 skills 的 metadata（注入 prompt）"""
        if not self.registry:
            return ""
        
        lines = ["<available_skills>"]
        for meta in self.registry.values():
            lines.append(meta.to_prompt())
        lines.append("</available_skills>")
        
        return "\n".join(lines)
    
    def load_skill(self, name: str, force: bool = False) -> Optional[LoadedSkill]:
        """
        按需加载 skill
        
        模型调用时读取完整的 SKILL.md
        """
        # 检查缓存
        if not force and name in self.cache:
            log.debug(f"Skill cache hit: {name}")
            return self.cache[name]
        
        # 检查 registry
        if name not in self.registry:
            log.warning(f"Skill not found: {name}")
            return None
        
        metadata = self.registry[name]
        skill_path = Path(metadata.location)
        
        if not skill_path.exists():
            log.error(f"Skill file not found: {skill_path}")
            return None
        
        # 读取完整内容
        content = skill_path.read_text(encoding="utf-8")
        
        # 缓存
        loaded = LoadedSkill(
            metadata=metadata,
            content=content,
            loaded_at=datetime.now()
        )
        self.cache[name] = loaded
        metadata.loaded = True
        
        log.info(f"Loaded skill: {name} ({len(content)} chars)")
        return loaded
    
    def match_skills(self, query: str) -> List[SkillMetadata]:
        """
        根据查询匹配 skills
        
        用于自动触发相关 skill
        """
        query_lower = query.lower()
        matched = []
        
        for meta in self.registry.values():
            score = 0
            # 描述匹配
            if query_lower in meta.description.lower():
                score += 2
            # 标签匹配
            for tag in meta.tags:
                if tag.lower() in query_lower:
                    score += 1
            if score > 0:
                matched.append((score, meta))
        
        # 按分数排序
        matched.sort(key=lambda x: -x[0])
        return [m for _, m in matched]
    
    def get_skill_summary(self, name: str) -> str:
        """获取 skill 摘要（不需要完整加载）"""
        if name in self.registry:
            return self.registry[name].description
        return ""


# 全局实例
_loader: Optional[SkillLoader] = None

def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader


if __name__ == "__main__":
    loader = get_skill_loader()
    print(loader.get_available_skills_prompt())
