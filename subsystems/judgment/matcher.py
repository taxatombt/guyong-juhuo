#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
matcher.py — Juhuo 规则Matcher

灵感来自Codex Rust的Matcher模式

更灵活的规则匹配:
- 按优先级排序
- 支持正则表达式
- 返回匹配结果和原因
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class MatchLevel(Enum):
    """匹配级别"""
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    DANGER = "danger"
    BLOCK = "block"


@dataclass
class MatchResult:
    """匹配结果"""
    matched: bool
    level: MatchLevel
    rule_name: str
    reason: str
    matched_text: str = ""


@dataclass
class MatcherRule:
    """Matcher规则"""
    name: str
    pattern: str
    level: MatchLevel
    reason: str
    enabled: bool = True
    priority: int = 0


class Matcher:
    """
    规则Matcher - 灵感来自Codex
    
    使用方式:
    matcher = Matcher()
    matcher.add_rule("dangerous_delete", r"rm\s+-rf", MatchLevel.DANGER, "危险删除")
    result = matcher.match("rm -rf /tmp/*")
    """

    def __init__(self):
        self.rules: List[MatcherRule] = []
        self._init_default_rules()

    def _init_default_rules(self):
        """初始化默认规则"""
        # 危险操作
        self.add_rule("dangerous_delete", r"rm\s+-rf", MatchLevel.BLOCK, "递归强制删除（危险）")
        self.add_rule("privilege_escalation", r"sudo\s+", MatchLevel.WARNING, "提权操作")
        self.add_rule("system_modify", r"(chmod\s+777|chown\s+)", MatchLevel.WARNING, "系统权限修改")
        
        # 网络操作
        self.add_rule("network_fetch", r"(curl|wget)\s+", MatchLevel.CAUTION, "网络请求")
        self.add_rule("api_key_expose", r"(api_key|apikey|secret|password)\s*=\s*['\"]?\w+", MatchLevel.BLOCK, "密钥泄露风险")
        
        # 进程操作
        self.add_rule("kill_process", r"kill\s+-(9|TERM)", MatchLevel.WARNING, "强制终止进程")
        self.add_rule("fork_bomb", r":\(\)\{.*:\|:&\}*", MatchLevel.BLOCK, "Fork炸弹")
        
        # 文件操作
        self.add_rule("overwrite_etc", r"(>|>>)\s*/etc/", MatchLevel.DANGER, "修改系统文件")
        self.add_rule("write_sudoers", r"(>|>>)\s*/etc/sudoers", MatchLevel.BLOCK, "修改sudoers")
        
        # Git操作
        self.add_rule("git_force_push", r"git\s+push\s+.*\s+-f", MatchLevel.WARNING, "强制推送")
        self.add_rule("git_dangerous", r"git\s+.*--force", MatchLevel.CAUTION, "强制操作")

    def add_rule(
        self,
        name: str,
        pattern: str,
        level: MatchLevel,
        reason: str,
        priority: int = 0,
    ):
        """添加规则"""
        rule = MatcherRule(
            name=name,
            pattern=pattern,
            level=level,
            reason=reason,
            priority=priority,
        )
        self.rules.append(rule)
        # 按优先级排序
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def match(self, text: str) -> MatchResult:
        """
        匹配文本
        
        返回第一个匹配的规则结果
        """
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            match = re.search(rule.pattern, text, re.IGNORECASE)
            if match:
                return MatchResult(
                    matched=True,
                    level=rule.level,
                    rule_name=rule.name,
                    reason=rule.reason,
                    matched_text=match.group(),
                )
        
        return MatchResult(
            matched=False,
            level=MatchLevel.SAFE,
            rule_name="",
            reason="无风险",
        )

    def match_all(self, text: str) -> List[MatchResult]:
        """匹配所有规则"""
        results = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            match = re.search(rule.pattern, text, re.IGNORECASE)
            if match:
                results.append(MatchResult(
                    matched=True,
                    level=rule.level,
                    rule_name=rule.name,
                    reason=rule.reason,
                    matched_text=match.group(),
                ))
        
        return results

    def get_highest_level(self, results: List[MatchResult]) -> MatchLevel:
        """获取最高风险级别"""
        if not results:
            return MatchLevel.SAFE
        
        level_order = [
            MatchLevel.SAFE,
            MatchLevel.CAUTION,
            MatchLevel.WARNING,
            MatchLevel.DANGER,
            MatchLevel.BLOCK,
        ]
        
        max_idx = 0
        for r in results:
            idx = level_order.index(r.level) if r.level in level_order else 0
            if idx > max_idx:
                max_idx = idx
        
        return level_order[max_idx]

    def should_block(self, text: str) -> Tuple[bool, str]:
        """判断是否应该阻断"""
        results = self.match_all(text)
        highest = self.get_highest_level(results)
        
        if highest == MatchLevel.BLOCK:
            reasons = [r.reason for r in results if r.level == MatchLevel.BLOCK]
            return True, "; ".join(reasons)
        
        return False, ""


# ── 全局Matcher实例 ────────────────────────────────────────────────
_matcher: Optional[Matcher] = None


def get_matcher() -> Matcher:
    global _matcher
    if _matcher is None:
        _matcher = Matcher()
    return _matcher


def check_safe(text: str) -> Tuple[bool, str]:
    """快捷函数：安全检查"""
    return get_matcher().should_block(text)


def match_rules(text: str) -> List[MatchResult]:
    """快捷函数：匹配所有规则"""
    return get_matcher().match_all(text)
