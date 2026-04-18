#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judgment/config.py — Production 配置集中管理

TODO 之一：Production config — BIAS=3, MIN_SAMPLES=5, COOLDOWN=24h

所有配置项统一在此：
- Self-Evolver 生产参数
- Benchmark 参数
- LLM 超参
- 数据库路径
- 进化配置
"""

from __future__ import annotations
import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════
# 路径配置
# ═══════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent.parent / "data"
EVOLUTIONS_DIR = DATA_DIR / "evolutions"
JUDGMENT_DATA_DIR = DATA_DIR / "judgment_data"
CONFIG_FILE = DATA_DIR / "judgment_config.json"

# ═══════════════════════════════════════════════════════════════════════════
# Self-Evolver 生产参数
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EvolverConfig:
    """Self-Evolver 进化参数"""
    bias_threshold: float = 0.7
    bias_consecutive: int = 3          # 连续3次错误触发
    accuracy_threshold: float = 0.4
    min_samples: int = 5                # 至少5个样本
    cooldown_hours: int = 24            # 冷却24小时
    validation_window: int = 10          # 验证窗口：进化后追踪10次
    accuracy_improvement_threshold: float = 0.05  # 提升阈值5%


@dataclass
class BenchmarkConfig:
    """GDPVal Benchmark 参数"""
    min_cases: int = 20                 # 最低案例数
    match_threshold: float = 0.5         # 通过阈值
    scenarios: list = field(default_factory=lambda: [
        "career", "finance", "relationship", "education",
        "health", "family", "investment", "migration", "life"
    ])


@dataclass
class LLMConfig:
    """LLM 调用参数"""
    max_tokens: int = 2048
    temperature: float = 0.7
    prompt_truncate: int = 6000


@dataclass
class JudgmentConfig:
    """判断系统总配置"""
    evolver: EvolverConfig = field(default_factory=EvolverConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    min_verdicts_for_evolution: int = 50  # 进化所需最低verdict数


# ═══════════════════════════════════════════════════════════════════════════
# 全局实例（懒加载）
# ═══════════════════════════════════════════════════════════════════════════

_config: Optional[JudgmentConfig] = None


def load_config() -> JudgmentConfig:
    """从 JSON 文件加载配置，不存在则返回默认值"""
    global _config
    if _config is not None:
        return _config
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            _config = JudgmentConfig(
                evolver=EvolverConfig(**data.get("evolver", {})),
                benchmark=BenchmarkConfig(**data.get("benchmark", {})),
                llm=LLMConfig(**data.get("llm", {})),
                min_verdicts_for_evolution=data.get("min_verdicts_for_evolution", 50),
            )
            return _config
        except Exception:
            pass
    
    _config = JudgmentConfig()
    return _config


def save_config(cfg: JudgmentConfig) -> None:
    """保存配置到 JSON 文件"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)


def get_evolver() -> EvolverConfig:
    """获取 Self-Evolver 配置"""
    return load_config().evolver


def get_benchmark() -> BenchmarkConfig:
    """获取 Benchmark 配置"""
    return load_config().benchmark


def get_llm() -> LLMConfig:
    """获取 LLM 配置"""
    return load_config().llm


# ═══════════════════════════════════════════════════════════════════════════
# 便捷常量（向后兼容）
# ═══════════════════════════════════════════════════════════════════════════

def _compat():
    """从 load_config() 读取兼容常量，供旧代码使用"""
    cfg = load_config()
    ev = cfg.evolver
    return {
        "BIAS_THRESHOLD": ev.bias_threshold,
        "BIAS_CONSECUTIVE": ev.bias_consecutive,
        "ACCURACY_THRESHOLD": ev.accuracy_threshold,
        "MIN_SAMPLES": ev.min_samples,
        "COOLDOWN_HOURS": ev.cooldown_hours,
        "VALIDATION_WINDOW": ev.validation_window,
        "ACCURACY_IMPROVEMENT_THRESHOLD": ev.accuracy_improvement_threshold,
        "MIN_VERDICTS_FOR_EVOLUTION": cfg.min_verdicts_for_evolution,
    }

# 导出兼容常量
_C = _compat()
BIAS_THRESHOLD = _C["BIAS_THRESHOLD"]
BIAS_CONSECUTIVE = _C["BIAS_CONSECUTIVE"]
ACCURACY_THRESHOLD = _C["ACCURACY_THRESHOLD"]
MIN_SAMPLES = _C["MIN_SAMPLES"]
COOLDOWN_HOURS = _C["COOLDOWN_HOURS"]
VALIDATION_WINDOW = _C["VALIDATION_WINDOW"]
ACCURACY_IMPROVEMENT_THRESHOLD = _C["ACCURACY_IMPROVEMENT_THRESHOLD"]
MIN_VERDICTS_FOR_EVOLUTION = _C["MIN_VERDICTS_FOR_EVOLUTION"]
