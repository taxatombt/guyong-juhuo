#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pre_tool_hook.py — Juhuo PreToolUse安全钩子

灵感来自Codex Rust的PreToolUse钩子

在动作执行前进行安全检测:
- 危险命令检测
- 权限检查
- 阈值限制
"""

import re, time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from judgment.matcher import check_safe, MatchLevel, get_matcher
from judgment.judgment_db import get_conn


class HookAction(Enum):
    """钩子动作"""
    ALLOW = "allow"
    BLOCK = "block"
    WARN = "warn"
    VERIFY = "verify"


@dataclass
class PreToolUseRequest:
    """
    工具执行前请求 - 灵感来自Codex PreToolUseRequest
    """
    tool_name: str
    args: Dict[str, Any]
    cwd: str = ""
    command: str = ""  # 如果是shell命令
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PreToolUseOutcome:
    """
    工具执行前结果 - 灵感来自Codex PreToolUseOutcome
    """
    action: HookAction
    should_block: bool
    block_reason: str = ""
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class PreToolHook:
    """
    PreToolUse钩子 - Codex风格的安全检测
    
    检测流程:
    1. 危险命令匹配
    2. 权限检查
    3. 频率限制
    4. 阈值检测
    """

    def __init__(self):
        self.tool_limits: Dict[str, int] = {
            "execute": 100,      # 执行次数限制
            "delete": 10,        # 删除次数限制
            "write": 50,        # 写入次数限制
            "network": 20,      # 网络请求限制
        }
        self.tool_counts: Dict[str, int] = {}  # 当前计数
        self.last_reset = datetime.now()

    def check(self, request: PreToolUseRequest) -> PreToolUseOutcome:
        """
        执行安全检查
        
        返回:
        - ALLOW: 允许执行
        - BLOCK: 阻断
        - WARN: 警告但允许
        - VERIFY: 需要验证
        """
        warnings = []
        suggestions = []
        should_block = False
        block_reason = ""

        # 1. 危险命令检测
        if request.command:
            blocked, reason = check_safe(request.command)
            if blocked:
                should_block = True
                block_reason = f"危险命令: {reason}"
                return PreToolUseOutcome(
                    action=HookAction.BLOCK,
                    should_block=True,
                    block_reason=block_reason,
                )
            
            # 警告检测
            matcher = get_matcher()
            results = matcher.match_all(request.command)
            for r in results:
                if r.level == MatchLevel.WARNING:
                    warnings.append(f"警告: {r.reason}")
                elif r.level == MatchLevel.CAUTION:
                    suggestions.append(f"建议: {r.reason}")

        # 2. 工具频率限制
        tool_type = self._detect_tool_type(request.tool_name)
        if tool_type in self.tool_limits:
            self.tool_counts[tool_type] = self.tool_counts.get(tool_type, 0) + 1
            
            if self.tool_counts[tool_type] > self.tool_limits[tool_type]:
                warnings.append(f"工具{tool_type}使用频率过高: {self.tool_counts[tool_type]}次")
                if tool_type in ["delete", "execute"]:
                    should_block = True
                    block_reason = f"{tool_type}操作超限"

        # 3. 权限检查
        if request.command:
            priv_issues = self._check_privileges(request.command)
            warnings.extend(priv_issues)

        # 4. 重置计数器（每小时）
        if datetime.now() - self.last_reset > timedelta(hours=1):
            self.tool_counts = {}
            self.last_reset = datetime.now()

        # 5. 决定动作
        if should_block:
            action = HookAction.BLOCK
        elif warnings:
            action = HookAction.WARN
        elif suggestions:
            action = HookAction.VERIFY
        else:
            action = HookAction.ALLOW

        return PreToolUseOutcome(
            action=action,
            should_block=should_block,
            block_reason=block_reason,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _detect_tool_type(self, tool_name: str) -> str:
        """检测工具类型"""
        tool_name = tool_name.lower()
        
        if any(k in tool_name for k in ["delete", "remove", "rm"]):
            return "delete"
        elif any(k in tool_name for k in ["write", "create", "edit", "save"]):
            return "write"
        elif any(k in tool_name for k in ["exec", "run", "shell", "bash", "terminal"]):
            return "execute"
        elif any(k in tool_name for k in ["http", "fetch", "download", "curl"]):
            return "network"
        
        return "other"

    def _check_privileges(self, command: str) -> List[str]:
        """检查权限问题"""
        warnings = []
        
        if re.search(r"sudo\s+", command):
            warnings.append("检测到sudo提权操作")
        
        if re.search(r"chmod\s+777", command):
            warnings.append("检测到777权限设置（不安全）")
        
        if re.search(r"(>|>>)\s*/etc/", command):
            warnings.append("尝试修改系统文件")
        
        return warnings


@dataclass
class PostToolUseResult:
    """工具执行后结果"""
    tool_name: str
    success: bool
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class PostToolHook:
    """
    PostToolUse钩子 - Codex风格的结果记录
    
    记录工具执行结果
    """

    def record(self, result: PostToolUseResult):
        """记录执行结果"""
        try:
            with get_conn() as c:
                c.execute("""
                    INSERT INTO tool_executions 
                    (tool_name, success, output, error, duration_ms, executed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    result.tool_name,
                    1 if result.success else 0,
                    result.output[:500],
                    result.error[:500],
                    result.duration_ms,
                    result.timestamp,
                ))
                c.commit()
        except Exception as e:
            print(f"[PostToolHook] record error: {e}")


# ── 数据库表 ──────────────────────────────────────────────────────
def init_tool_hook_db():
    """初始化工具钩子表"""
    with get_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS tool_executions (
                id INTEGER PRIMARY KEY,
                tool_name TEXT,
                success INTEGER,
                output TEXT,
                error TEXT,
                duration_ms REAL,
                executed_at TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_tool_name ON tool_executions(tool_name);
            CREATE INDEX IF NOT EXISTS idx_executed_at ON tool_executions(executed_at);
        """)
        c.commit()


# ── 全局实例 ──────────────────────────────────────────────────────
_pre_hook: Optional[PreToolHook] = None
_post_hook: Optional[PostToolHook] = None


def get_pre_hook() -> PreToolHook:
    global _pre_hook
    if _pre_hook is None:
        _pre_hook = PreToolHook()
    return _pre_hook


def get_post_hook() -> PostToolHook:
    global _post_hook
    if _post_hook is None:
        _post_hook = PostToolHook()
    return _post_hook


def pre_action_check(tool_name: str, args: Dict, command: str = "") -> PreToolUseOutcome:
    """快捷函数：动作执行前检查"""
    request = PreToolUseRequest(
        tool_name=tool_name,
        args=args,
        command=command,
    )
    return get_pre_hook().check(request)


def post_action_record(tool_name: str, success: bool, output: str = "", error: str = "", duration_ms: float = 0.0):
    """快捷函数：动作执行后记录"""
    result = PostToolUseResult(
        tool_name=tool_name,
        success=success,
        output=output,
        error=error,
        duration_ms=duration_ms,
    )
    get_post_hook().record(result)


init_tool_hook_db()
