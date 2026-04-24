# -*- coding: utf-8 -*-
"""
ToolPermission — 工具权限策略（Claude Managed Agents API 启发）

设计目标：为 ActionExecutor 的执行通道增加权限控制。
类似 Claude Managed Agents API 的 always_allow / always_ask 机制。

核心场景：
    executor.execute_via_hermes(task="rm -rf /", ...)
      → permission.check("EXECUTE_SHELL", {"command": "rm -rf /"})
          → 返回 DENY（危险命令，直接阻止）

    executor.execute_via_hermes(task="git status", ...)
      → permission.check("EXECUTE_SHELL", {"command": "git status"})
          → 返回 ASK（需要用户确认）

用法：
    from action_system.tool_permission import permission

    # 检查权限
    result = permission.check("EXECUTE_SHELL", {"command": "rm -rf /"})
    if result.level == PermissionLevel.DENY:
        print(f"阻止：{result.reason}")
    elif result.level == PermissionLevel.ASK:
        confirm = input(f"确认执行？{result.reason} [y/N]: ")
        if confirm.lower() == "y":
            permission.confirm("EXECUTE_SHELL", {"command": "rm -rf /"})

    # 设置默认策略
    permission.set_default(PermissionLevel.ASK)
    permission.set_tool_level("READ", PermissionLevel.ALWAYS_ALLOW)
"""

import re
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable

logger = logging.getLogger(__name__)


# ── 权限级别 ────────────────────────────────────────────────────────────────

class PermissionLevel(Enum):
    """
    权限级别（与 Claude Managed Agents API 对齐）

    ALWAYS_ALLOW — 自动放行，不询问
    ASK          — 暂停，等待用户确认
    DENY         — 直接阻止，不询问
    """
    ALWAYS_ALLOW = "always_allow"
    ASK          = "ask"
    DENY         = "deny"


@dataclass
class PermissionResult:
    """权限检查结果"""
    level: PermissionLevel
    reason: str
    tool_type: str
    tool_args: Dict[str, Any]
    requires_confirmation: bool
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


# ── 危险模式检测器 ──────────────────────────────────────────────────────────

class DangerMatcher:
    """
    危险命令模式匹配器

    检测到危险操作时直接 DENY。
    类似 Codex Matcher 模式。
    """

    BLOCK_PATTERNS = [
        (re.compile(r'rm\s+-rf\s+/\s*$'), "rm -rf / 根目录删除，直接阻止"),
        (re.compile(r'rm\s+-rf\s+/\w+\s*$'), "rm -rf /xxx 递归删除，直接阻止"),
        (re.compile(r':\(\)\{\s*:\|:&\s*\};:'), "Fork bomb，直接阻止"),
        (re.compile(r'dd\s+if='), "dd 写入原始设备，直接阻止"),
        (re.compile(r'mkfs\.'), "格式化文件系统，直接阻止"),
        (re.compile(r'format\s+[a-z]:', re.I), "Windows 格式化命令，直接阻止"),
        (re.compile(r'curl\s+.*\|\s*sh'), "curl|sh（eval攻击），直接阻止"),
        (re.compile(r'wget\s+.*\|\s*sh'), "wget|sh，直接阻止"),
        (re.compile(r'chmod\s+-R\s+777\s+/etc'), "chmod 777 /etc，直接阻止"),
        (re.compile(r'chmod\s+-R\s+777\s+/usr'), "chmod 777 /usr，直接阻止"),
        (re.compile(r'sudo\s+rm\s+-rf'), "sudo rm -rf，直接阻止"),
        (re.compile(r'git\s+push\s+--force'), "git force push，直接阻止"),
        (re.compile(r'git\s+push\s+--all'), "git push --all，直接阻止"),
    ]

    WARN_PATTERNS = [
        (re.compile(r'rm\s+-rf'), "递归删除文件"),
        (re.compile(r'rm\s+[Rr]\s+'), "强制删除文件"),
        (re.compile(r'del\s+/[SFQR]'), "Windows 强制删除"),
        (re.compile(r'chmod\s+777'), "777 权限开放"),
        (re.compile(r'chmod\s+000'), "000 权限锁定"),
        (re.compile(r'sudo\s+'), "sudo 提权执行"),
        (re.compile(r'\|\s*bash'), "管道到 bash"),
        (re.compile(r'\|\s*sh'), "管道到 sh"),
        (re.compile(r'exec\s+'), "exec 执行"),
        (re.compile(r'eval\s+'), "eval 执行"),
        (re.compile(r'shutdown', re.I), "关机命令"),
        (re.compile(r'reboot', re.I), "重启命令"),
        (re.compile(r'halt', re.I), "停止系统"),
        (re.compile(r'kill\s+-9'), "强制杀死进程"),
        (re.compile(r'killall', re.I), "杀死所有进程"),
        (re.compile(r'pkill', re.I), "模式匹配杀进程"),
        (re.compile(r'drop\s+database', re.I), "删除数据库"),
        (re.compile(r'drop\s+table', re.I), "删除数据表"),
        (re.compile(r'truncate\s+', re.I), "清空表数据"),
        (re.compile(r'DELETE\s+FROM\s+\w+\s+WHERE\s+1=1', re.I), "无条件删除所有行"),
        (re.compile(r'git\s+reset\s+--hard', re.I), "git reset --hard（可能丢失工作区）"),
        (re.compile(r'git\s+clean\s+-fd', re.I), "git clean 强制清理未追踪文件"),
    ]

    @classmethod
    def match(cls, command: str) -> Optional[PermissionResult]:
        if not command:
            return None

        for pattern, reason in cls.BLOCK_PATTERNS:
            if pattern.search(command):
                return PermissionResult(
                    level=PermissionLevel.DENY,
                    reason=reason,
                    tool_type="EXECUTE_SHELL",
                    tool_args={"command": command},
                    requires_confirmation=False,
                    warnings=[reason],
                )

        warnings = []
        for pattern, reason in cls.WARN_PATTERNS:
            if pattern.search(command):
                warnings.append(reason)

        if warnings:
            return PermissionResult(
                level=PermissionLevel.ASK,
                reason=f"检测到 {len(warnings)} 个警告操作",
                tool_type="EXECUTE_SHELL",
                tool_args={"command": command},
                requires_confirmation=True,
                warnings=warnings,
                suggestions=[f"在执行前确认：{w}" for w in warnings],
            )

        return None


# ── 权限策略管理器 ──────────────────────────────────────────────────────────

class ToolPermissionPolicy:
    """
    工具权限策略管理器

    三层控制：
    1. 工具级别覆盖 — 显式设置的最高优先级
    2. 工具级别默认 — 每个工具类型的默认策略
    3. 全局默认 — 未配置工具的兜底策略

    默认分级：
    - 读/查/判断/分析 → ALWAYS_ALLOW
    - 写/编辑/Shell/网络 → ASK
    - 删除/执行代码/系统配置 → DENY
    """

    DEFAULT_TOOL_LEVELS: Dict[str, PermissionLevel] = {
        # 安全操作 — 自动放行
        "READ":           PermissionLevel.ALWAYS_ALLOW,
        "SEARCH":         PermissionLevel.ALWAYS_ALLOW,
        "BROWSE":         PermissionLevel.ALWAYS_ALLOW,
        "JUDGMENT":       PermissionLevel.ALWAYS_ALLOW,
        "ANALYZE":        PermissionLevel.ALWAYS_ALLOW,

        "BENCHMARK":      PermissionLevel.ALWAYS_ALLOW,

        # 写入操作 — 需要确认
        "WRITE":          PermissionLevel.ASK,
        "EDIT":           PermissionLevel.ASK,
        "EXECUTE_SHELL":  PermissionLevel.ALWAYS_ALLOW,
        "WEB_REQUEST":    PermissionLevel.ASK,
        "SEND_MESSAGE":   PermissionLevel.ASK,

        # 危险操作 — 默认阻止
        "DELETE":         PermissionLevel.DENY,
        "EXECUTE_CODE":   PermissionLevel.DENY,
        "SYSTEM_CONFIG":  PermissionLevel.DENY,
        "NETWORK_DANGER": PermissionLevel.DENY,
    }

    def __init__(self):
        self._default_level = PermissionLevel.ASK
        self._tool_overrides: Dict[str, PermissionLevel] = {}
        self._confirmation_cache: Dict[str, float] = {}
        self._on_ask_handlers: List[Callable] = []

    def set_default(self, level: PermissionLevel) -> None:
        self._default_level = level
        logger.info(f"[Permission] default → {level.value}")

    def set_tool_level(self, tool_type: str, level: PermissionLevel) -> None:
        self._tool_overrides[tool_type] = level
        logger.info(f"[Permission] {tool_type} → {level.value}")

    def get_tool_level(self, tool_type: str) -> PermissionLevel:
        return (self._tool_overrides.get(tool_type)
                or self.DEFAULT_TOOL_LEVELS.get(tool_type)
                or self._default_level)

    def on_ask(self, handler: Callable) -> None:
        self._on_ask_handlers.append(handler)

    def check(self, tool_type: str,
              tool_args: Dict[str, Any] = None) -> PermissionResult:
        if tool_args is None:
            tool_args = {}

        level = self.get_tool_level(tool_type)

        # EXECUTE_SHELL 走危险模式检测
        if tool_type == "EXECUTE_SHELL" and "command" in tool_args:
            cmd = tool_args.get("command", "")
            danger = DangerMatcher.match(cmd)
            if danger:
                return danger

            if level == PermissionLevel.DENY:
                return PermissionResult(
                    level=PermissionLevel.DENY,
                    reason=f"{tool_type} 策略为 DENY",
                    tool_type=tool_type, tool_args=tool_args,
                    requires_confirmation=False)
            if level == PermissionLevel.ASK:
                return PermissionResult(
                    level=PermissionLevel.ASK,
                    reason=f"需要确认：{tool_type}",
                    tool_type=tool_type, tool_args=tool_args,
                    requires_confirmation=True)
            return PermissionResult(
                level=PermissionLevel.ALWAYS_ALLOW,
                reason=f"{tool_type} 策略为 ALWAYS_ALLOW",
                tool_type=tool_type, tool_args=tool_args,
                requires_confirmation=False)

        if level == PermissionLevel.DENY:
            return PermissionResult(
                level=PermissionLevel.DENY,
                reason=f"{tool_type} 策略为 DENY",
                tool_type=tool_type, tool_args=tool_args,
                requires_confirmation=False)
        if level == PermissionLevel.ASK:
            return PermissionResult(
                level=PermissionLevel.ASK,
                reason=f"需要确认：{tool_type}",
                tool_type=tool_type, tool_args=tool_args,
                requires_confirmation=True)
        return PermissionResult(
            level=PermissionLevel.ALWAYS_ALLOW,
            reason=f"{tool_type} 策略为 ALWAYS_ALLOW",
            tool_type=tool_type, tool_args=tool_args,
            requires_confirmation=False)

    def confirm(self, tool_type: str,
                tool_args: Dict[str, Any] = None,
                cache_ttl: int = 300) -> None:
        if tool_args is None:
            tool_args = {}
        key = f"{tool_type}:{str(tool_args)}"
        self._confirmation_cache[key] = time.time() + cache_ttl
        logger.info(f"[Permission] confirmed: {key}")
        for h in self._on_ask_handlers:
            try:
                h(tool_type, tool_args, confirmed=True)
            except Exception as e:
                logger.warning(f"[Permission] on_ask handler failed: {e}")

    def deny(self, tool_type: str,
             tool_args: Dict[str, Any] = None) -> None:
        if tool_args is None:
            tool_args = {}
        logger.info(f"[Permission] denied: {tool_type}")
        for h in self._on_ask_handlers:
            try:
                h(tool_type, tool_args, confirmed=False)
            except Exception as e:
                logger.warning(f"[Permission] on_ask handler failed: {e}")

    def is_cached_confirmed(self, tool_type: str,
                            tool_args: Dict[str, Any] = None) -> bool:
        if tool_args is None:
            tool_args = {}
        key = f"{tool_type}:{str(tool_args)}"
        if key not in self._confirmation_cache:
            return False
        if time.time() > self._confirmation_cache[key]:
            del self._confirmation_cache[key]
            return False
        return True

    def clear_cache(self) -> None:
        self._confirmation_cache.clear()


# ── 全局单例 ────────────────────────────────────────────────────────────────

permission = ToolPermissionPolicy()


# ── 集成异常 ────────────────────────────────────────────────────────────────

class PermissionRequired(Exception):
    """需要用户确认的异常"""
    pass


class PermissionDenied(Exception):
    """操作被权限策略阻止的异常"""
    pass


# ── ActionExecutor 集成函数 ─────────────────────────────────────────────────

def check_action_permission(tool_type: str,
                            tool_args: Dict[str, Any] = None) -> PermissionResult:
    """
    ActionExecutor 执行前的权限检查

    用法（在 action_executor.py 中）：
        result = check_action_permission("EXECUTE_SHELL", {"command": cmd})
        if result.level == PermissionLevel.DENY:
            raise PermissionDenied(f"阻止：{result.reason}")
        if result.level == PermissionLevel.ASK:
            if not permission.is_cached_confirmed(tool_type, tool_args):
                raise PermissionRequired(f"需要确认：{result.reason}")
    """
    return permission.check(tool_type, tool_args)
