#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evolution_tools.py — Evolution 子系统工具
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class EvolutionToolResult:
    success: bool
    result: Any = None
    error: Optional[str] = None


def tool_trigger_evolution(reason: str) -> EvolutionToolResult:
    """触发进化"""
    try:
        from evolver import trigger_evolution
        result = trigger_evolution(reason)
        return EvolutionToolResult(success=True, result={"evolved": result})
    except Exception as e:
        return EvolutionToolResult(success=False, error=str(e))


def tool_get_fitness_baseline() -> EvolutionToolResult:
    """获取健康度基线"""
    try:
        from judgment import get_fitness_baseline
        baseline = get_fitness_baseline()
        return EvolutionToolResult(success=True, result=baseline)
    except Exception as e:
        return EvolutionToolResult(success=False, error=str(e))


def tool_update_fitness(metric: str, value: float) -> EvolutionToolResult:
    """更新健康度"""
    try:
        from evolver import update_fitness
        update_fitness(metric, value)
        return EvolutionToolResult(success=True, result={"updated": True})
    except Exception as e:
        return EvolutionToolResult(success=False, error=str(e))


def tool_run_benchmark() -> EvolutionToolResult:
    """运行基准测试"""
    try:
        from evolver import run_benchmark
        results = run_benchmark()
        return EvolutionToolResult(success=True, result=results)
    except Exception as e:
        return EvolutionToolResult(success=False, error=str(e))


def tool_validate_evolution(evolution_id: str) -> EvolutionToolResult:
    """验证进化"""
    try:
        from evolver import validate_evolution
        valid, report = validate_evolution(evolution_id)
        return EvolutionToolResult(success=True, result={"valid": valid, "report": report})
    except Exception as e:
        return EvolutionToolResult(success=False, error=str(e))


def tool_get_evolution_history(limit: int = 10) -> EvolutionToolResult:
    """获取进化历史"""
    try:
        from evolver import get_evolution_history
        history = get_evolution_history(limit)
        return EvolutionToolResult(success=True, result={"count": len(history), "history": history})
    except Exception as e:
        return EvolutionToolResult(success=False, error=str(e))


EVOLUTION_TOOLS = {
    "trigger_evolution": {"fn": tool_trigger_evolution, "params": ["reason"]},
    "get_fitness_baseline": {"fn": tool_get_fitness_baseline, "params": []},
    "update_fitness": {"fn": tool_update_fitness, "params": ["metric", "value"]},
    "run_benchmark": {"fn": tool_run_benchmark, "params": []},
    "validate_evolution": {"fn": tool_validate_evolution, "params": ["evolution_id"]},
    "get_evolution_history": {"fn": tool_get_evolution_history, "params": ["limit"]},
}

__all__ = ["EvolutionToolResult", "EVOLUTION_TOOLS"]
