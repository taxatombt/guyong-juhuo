#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n.py — Juhuo 多语言支持

支持：中文、English
"""

from __future__ import annotations
from typing import Dict, Callable
from dataclasses import dataclass
from enum import Enum
import gettext
import os

from judgment.logging_config import get_logger
log = get_logger("juhuo.i18n")


class Locale(Enum):
    ZH_CN = "zh_CN"
    EN_US = "en_US"


@dataclass
class Translations:
    """翻译字典"""
    locale: Locale
    translations: Dict[str, str]


# 内置翻译
TRANSLATIONS: Dict[Locale, Dict[str, str]] = {
    Locale.ZH_CN: {
        # CLI
        "cli.title": "⚖️ Juhuo 判断系统",
        "cli.input_placeholder": "输入问题让 Juhuo 帮助判断...",
        "cli.quit": "再见!",
        "cli.analysis": "正在分析",
        
        # 判断
        "judge.verdict": "建议",
        "judge.confidence": "置信度",
        "judge.chain_id": "Chain ID",
        
        # 维度
        "dim.cognitive": "认知心理学",
        "dim.game_theory": "博弈论",
        "dim.economic": "经济学",
        "dim.dialectical": "辩证唯物主义",
        "dim.emotional": "情绪智能",
        "dim.intuitive": "直觉/第六感",
        "dim.moral": "价值/道德",
        "dim.social": "社会意识",
        "dim.temporal": "时间折扣",
        "dim.metacognitive": "元认知",
        
        # 状态
        "status.title": "📊 Juhuo 状态",
        "status.belief": "置信度状态",
        "status.verdicts": "Verdict 统计",
        "status.total": "总判断数",
        "status.correct": "正确数",
        "status.wrong": "错误数",
        "status.accuracy": "准确率",
        "status.recent": "最近判断",
        
        # Benchmark
        "bench.title": "⚖️ Juhuo Benchmark",
        "bench.total": "总案例",
        "bench.passed": "通过",
        "bench.failed": "失败",
        "bench.accuracy": "准确率",
        "bench.strongest": "最强维度",
        "bench.weakest": "最弱维度",
        
        # Self-test
        "test.title": "🔍 Juhuo 自检",
        "test.pass": "通过",
        "test.fail": "失败",
        "test.warn": "警告",
        "test.ready": "系统就绪，可以启动!",
        "test.not_ready": "存在失败项，请修复后再试",
        
        # Error
        "error.empty_task": "任务不能为空",
        "error.no_api_key": "未配置 API Key",
        "error.judge_failed": "判断失败",
    },
    
    Locale.EN_US: {
        # CLI
        "cli.title": "⚖️ Juhuo Judgment System",
        "cli.input_placeholder": "Ask Juhuo for judgment...",
        "cli.quit": "Goodbye!",
        "cli.analysis": "Analyzing",
        
        # Judgment
        "judge.verdict": "Verdict",
        "judge.confidence": "Confidence",
        "judge.chain_id": "Chain ID",
        
        # Dimensions
        "dim.cognitive": "Cognitive",
        "dim.game_theory": "Game Theory",
        "dim.economic": "Economic",
        "dim.dialectical": "Dialectical",
        "dim.emotional": "Emotional",
        "dim.intuitive": "Intuitive",
        "dim.moral": "Moral",
        "dim.social": "Social",
        "dim.temporal": "Temporal",
        "dim.metacognitive": "Metacognitive",
        
        # Status
        "status.title": "📊 Juhuo Status",
        "status.belief": "Belief Status",
        "status.verdicts": "Verdict Stats",
        "status.total": "Total",
        "status.correct": "Correct",
        "status.wrong": "Wrong",
        "status.accuracy": "Accuracy",
        "status.recent": "Recent",
        
        # Benchmark
        "bench.title": "⚖️ Juhuo Benchmark",
        "bench.total": "Total Cases",
        "bench.passed": "Passed",
        "bench.failed": "Failed",
        "bench.accuracy": "Accuracy",
        "bench.strongest": "Strongest",
        "bench.weakest": "Weakest",
        
        # Self-test
        "test.title": "🔍 Juhuo Self-Test",
        "test.pass": "Pass",
        "test.fail": "Fail",
        "test.warn": "Warn",
        "test.ready": "System ready!",
        "test.not_ready": "Fix failures before starting",
        
        # Error
        "error.empty_task": "Task cannot be empty",
        "error.no_api_key": "No API Key configured",
        "error.judge_failed": "Judgment failed",
    }
}


class I18n:
    """国际化管理器"""
    
    def __init__(self, locale: Locale = None):
        if locale is None:
            # 自动检测
            lang = os.environ.get("LANG", os.environ.get("LC_ALL", ""))
            if "zh" in lang.lower():
                locale = Locale.ZH_CN
            else:
                locale = Locale.EN_US
        
        self.locale = locale
        self._ = TRANSLATIONS.get(locale, TRANSLATIONS[Locale.ZH_CN])
    
    def t(self, key: str, **kwargs) -> str:
        """翻译"""
        template = self._.get(key, key)
        if kwargs:
            return template.format(**kwargs)
        return template
    
    def set_locale(self, locale: Locale):
        """设置语言"""
        self.locale = locale
        self._ = TRANSLATIONS.get(locale, TRANSLATIONS[Locale.ZH_CN])


# 全局实例
_i18n: I18n = None

def get_i18n() -> I18n:
    global _i18n
    if _i18n is None:
        _i18n = I18n()
    return _i18n


# 快捷函数
def t(key: str, **kwargs) -> str:
    return get_i18n().t(key, **kwargs)


# CLI 增强 - 语言选择
def format_cli_output(text: str, locale: Locale = None) -> str:
    """格式化 CLI 输出"""
    if locale is None:
        locale = get_i18n().locale
    
    # 简单的占位符替换
    # 这里可以实现更复杂的模板逻辑
    return text
