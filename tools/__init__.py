#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools — Juhuo Agent 系统工具集

整合所有子系统暴露的工具接口，提供统一的工具调用入口。

工具分类：
1. judgment_tools — 十维判断系统 (9个工具)
2. memory_tools — 4类记忆 + 因果记忆 (9个工具)
3. perception_tools — 感知系统 (7个工具)
4. emotion_tools — 情绪 + 好奇心 (7个工具)
5. action_tools — 行动系统 (6个工具)
6. goal_tools — 目标系统 (4个工具)
7. output_tools — 输出系统 (4个工具)
8. evolution_tools — 进化系统 (6个工具)

总计：52个工具

使用方式：
```python
from tools import TOOL_REGISTRY, execute_tool

# 执行工具
result = execute_tool("check10d", {"task_text": "要不要辞职创业"})
print(result.result)

# 列出工具
print(TOOL_REGISTRY.list_by_category("judgment"))
```

工具命名规范：
- tool_<name> — 工具函数
- TOOL_<CATEGORY> — 工具注册表
- ToolResult — 统一返回类型
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

# ═══════════════════════════════════════════════════════════════════════════
# 统一返回类型
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ToolResult:
    """统一工具返回类型"""
    success: bool
    tool_name: str
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "tool": self.tool_name,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time
        }


# ═══════════════════════════════════════════════════════════════════════════
# 导入所有工具
# ═══════════════════════════════════════════════════════════════════════════

from .judgment_tools import JUDGMENT_TOOLS, JudgmentToolResult
from .memory_tools import MEMORY_TOOLS, MemoryToolResult
from .perception_tools import PERCEPTION_TOOLS, PerceptionToolResult
from .emotion_tools import EMOTION_TOOLS, EmotionToolResult
from .action_tools import ACTION_TOOLS, ActionToolResult
from .goal_tools import GOAL_TOOLS, GoalToolResult
from .output_tools import OUTPUT_TOOLS, OutputToolResult
from .evolution_tools import EVOLUTION_TOOLS, EvolutionToolResult


# ═══════════════════════════════════════════════════════════════════════════
# 合并所有工具到统一注册表
# ═══════════════════════════════════════════════════════════════════════════

TOOL_REGISTRY: Dict[str, Dict] = {}

# 添加工具
for name, tool in JUDGMENT_TOOLS.items():
    TOOL_REGISTRY[name] = {**tool, "category": "judgment"}

for name, tool in MEMORY_TOOLS.items():
    TOOL_REGISTRY[name] = {**tool, "category": "memory"}

for name, tool in PERCEPTION_TOOLS.items():
    TOOL_REGISTRY[name] = {**tool, "category": "perception"}

for name, tool in EMOTION_TOOLS.items():
    TOOL_REGISTRY[name] = {**tool, "category": "emotion"}

for name, tool in ACTION_TOOLS.items():
    TOOL_REGISTRY[name] = {**tool, "category": "action"}

for name, tool in GOAL_TOOLS.items():
    TOOL_REGISTRY[name] = {**tool, "category": "goal"}

for name, tool in OUTPUT_TOOLS.items():
    TOOL_REGISTRY[name] = {**tool, "category": "output"}

for name, tool in EVOLUTION_TOOLS.items():
    TOOL_REGISTRY[name] = {**tool, "category": "evolution"}


# ═══════════════════════════════════════════════════════════════════════════
# 工具执行器
# ═══════════════════════════════════════════════════════════════════════════

def execute_tool(tool_name: str, params: Dict = None) -> ToolResult:
    """
    执行工具
    
    Args:
        tool_name: 工具名称
        params: 工具参数
        
    Returns:
        ToolResult: 执行结果
    """
    import time
    start_time = time.time()
    
    params = params or {}
    
    # 查找工具
    tool_def = TOOL_REGISTRY.get(tool_name)
    if not tool_def:
        return ToolResult(
            success=False,
            tool_name=tool_name,
            error=f"Tool '{tool_name}' not found",
            execution_time=time.time() - start_time
        )
    
    # 获取函数
    fn = tool_def.get("fn")
    if not fn:
        return ToolResult(
            success=False,
            tool_name=tool_name,
            error="Tool function not defined",
            execution_time=time.time() - start_time
        )
    
    # 执行
    try:
        result = fn(**params)
        
        # 统一返回类型
        if isinstance(result, ToolResult):
            result.tool_name = tool_name
            result.execution_time = time.time() - start_time
            return result
        
        return ToolResult(
            success=True,
            tool_name=tool_name,
            result=result,
            execution_time=time.time() - start_time
        )
        
    except Exception as e:
        return ToolResult(
            success=False,
            tool_name=tool_name,
            error=str(e),
            execution_time=time.time() - start_time
        )


def list_tools(category: Optional[str] = None) -> List[Dict]:
    """列出工具"""
    if category:
        return [
            {"name": name, **tool}
            for name, tool in TOOL_REGISTRY.items()
            if tool.get("category") == category
        ]
    return [{"name": name, **tool} for name, tool in TOOL_REGISTRY.items()]


def list_categories() -> List[str]:
    """列出所有类别"""
    categories = set()
    for tool in TOOL_REGISTRY.values():
        if "category" in tool:
            categories.add(tool["category"])
    return sorted(list(categories))


def get_tool_info(tool_name: str) -> Optional[Dict]:
    """获取工具信息"""
    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        return None
    
    return {
        "name": tool_name,
        "category": tool.get("category"),
        "description": tool.get("description", ""),
        "params": tool.get("params", [])
    }


# ═══════════════════════════════════════════════════════════════════════════
# 工具统计
# ═══════════════════════════════════════════════════════════════════════════

TOOL_STATS = {
    "total": len(TOOL_REGISTRY),
    "by_category": {}
}

for tool in TOOL_REGISTRY.values():
    cat = tool.get("category", "unknown")
    TOOL_STATS["by_category"][cat] = TOOL_STATS["by_category"].get(cat, 0) + 1


__all__ = [
    # 核心类
    "ToolResult",
    # 执行函数
    "execute_tool",
    "list_tools",
    "list_categories",
    "get_tool_info",
    # 注册表
    "TOOL_REGISTRY",
    "TOOL_STATS",
    # 各子系统工具
    "JUDGMENT_TOOLS",
    "MEMORY_TOOLS",
    "PERCEPTION_TOOLS",
    "EMOTION_TOOLS",
    "ACTION_TOOLS",
    "GOAL_TOOLS",
    "OUTPUT_TOOLS",
    "EVOLUTION_TOOLS",
]
