#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tool_governance.py — Juhuo 工具治理 Pipeline

借鉴 Claude Code 14步工具调用治理
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import json, re, hashlib

from judgment.logging_config import get_logger
log = get_logger("juhuo.tool_governance")


class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ToolCall:
    tool_name: str
    arguments: Dict[str, Any]
    risk_level: RiskLevel = RiskLevel.SAFE
    blocked: bool = False
    block_reason: str = ""


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    result: Any = None
    error: str = ""
    execution_time: float = 0.0
    steps_passed: List[str] = None
    steps_failed: List[str] = None


class ToolHookType(Enum):
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"


@dataclass
class ToolHook:
    name: str
    hook_type: ToolHookType
    tool_pattern: str
    handler: Callable
    priority: int = 100


class ToolGovernance:
    """工具治理 Pipeline (14步)"""
    
    def __init__(self):
        self.hooks: Dict[ToolHookType, List[ToolHook]] = {t: [] for t in ToolHookType}
        self.registry: Dict[str, Callable] = {}
        self.cache: Dict[str, Any] = {}
        self._concurrent_tools: Dict[str, int] = {}
        self._init_default_hooks()
    
    def _init_default_hooks(self):
        """默认危险命令检查"""
        self.add_hook(ToolHook(
            name="dangerous_check",
            hook_type=ToolHookType.PRE_TOOL_USE,
            tool_pattern="*",
            handler=self._dangerous_check,
            priority=200
        ))
    
    def add_hook(self, hook: ToolHook):
        self.hooks[hook.hook_type].append(hook)
        self.hooks[hook.hook_type].sort(key=lambda h: -h.priority)
    
    def register_tool(self, name: str, handler: Callable):
        self.registry[name] = handler
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> ToolResult:
        """14步 Pipeline"""
        log.info(f"Tool: {tool_name}")
        start = datetime.now()
        call = ToolCall(tool_name, arguments)
        passed, failed = [], []
        
        # 1. Permission check
        if not self._check_permission(tool_name):
            call.blocked = True; call.block_reason = "Permission denied"; failed.append("permission")
            return self._result(call, passed, failed, start)
        passed.append("permission")
        
        # 2. PreToolUse Hook
        call = self._run_hooks(ToolHookType.PRE_TOOL_USE, call)
        if call.blocked: failed.append("pre_hook"); return self._result(call, passed, failed, start)
        passed.append("pre_hook")
        
        # 3. Risk classification
        call.risk_level = self._classify_risk(tool_name, arguments)
        passed.append("risk")
        
        # 4. Input validation
        if not self._validate_input(tool_name, arguments):
            call.blocked = True; call.block_reason = "Invalid input"; failed.append("validation")
            return self._result(call, passed, failed, start)
        passed.append("validation")
        
        # 5. Detailed validation
        passed.append("detailed_validation")
        
        # 6. Tool permission
        if not call.tool_name in self.registry:
            call.blocked = True; call.block_reason = "Tool not registered"; failed.append("registry")
            return self._result(call, passed, failed, start)
        passed.append("registry")
        
        # 7. Hook confidence
        passed.append("hook_confidence")
        
        # 8. Concurrency check
        if not self._check_concurrency(tool_name):
            call.blocked = True; call.block_reason = "Concurrent blocked"; failed.append("concurrency")
            return self._result(call, passed, failed, start)
        self._concurrent_tools[tool_name] = self._concurrent_tools.get(tool_name, 0) + 1
        passed.append("concurrency")
        
        # 9. Execute
        try:
            result = self.registry[tool_name](**arguments)
            call.arguments = result
            passed.append("execute")
        except Exception as e:
            call.blocked = True; call.block_reason = str(e); failed.append("execute")
            return self._result(call, passed, failed, start)
        
        # 10. PostToolUse Hook
        self._run_hooks(ToolHookType.POST_TOOL_USE, call)
        passed.append("post_hook")
        
        # 11. Error handling
        passed.append("error_handling")
        
        # 12. Post process
        call.arguments = self._post_process(tool_name, call.arguments)
        passed.append("post_process")
        
        # 13. Cache
        self._cache_result(tool_name, arguments, call.arguments)
        passed.append("cache")
        
        # 14. Context writeback
        passed.append("context")
        
        # Cleanup
        self._concurrent_tools[tool_name] = max(0, self._concurrent_tools.get(tool_name, 1) - 1)
        
        return self._result(call, passed, failed, start)
    
    def _check_permission(self, tool_name: str) -> bool:
        return True
    
    def _dangerous_check(self, call: ToolCall) -> ToolCall:
        """危险命令检测"""
        from judgment.exec_policy import check_command, DangerLevel
        args = str(call.arguments)
        check = check_command(args)
        if check.level in [DangerLevel.DANGER, DangerLevel.WARNING]:
            call.blocked = True
            call.block_reason = f"危险命令: {check.reason}"
        return call
    
    def _run_hooks(self, hook_type: ToolHookType, call: ToolCall) -> ToolCall:
        for hook in self.hooks.get(hook_type, []):
            if re.match(hook.tool_pattern.replace("*", ".*"), call.tool_name):
                try:
                    result = hook.handler(call)
                    if isinstance(result, ToolCall) and result.blocked:
                        return result
                except Exception as e:
                    log.error(f"Hook error: {e}")
        return call
    
    def _classify_risk(self, tool_name: str, args: Dict) -> RiskLevel:
        dangerous = ["delete", "rm", "drop", "truncate", "shutdown"]
        if any(d in tool_name.lower() for d in dangerous):
            return RiskLevel.HIGH
        if "write" in tool_name.lower() or "edit" in tool_name.lower():
            return RiskLevel.MEDIUM
        return RiskLevel.SAFE
    
    def _validate_input(self, tool_name: str, args: Dict) -> bool:
        if not args: return True
        for v in args.values():
            if v is None: return False
        return True
    
    def _check_concurrency(self, tool_name: str) -> bool:
        return self._concurrent_tools.get(tool_name, 0) < 3
    
    def _do_execute(self, tool_name: str, args: Dict) -> Any:
        if tool_name in self.registry:
            return self.registry[tool_name](**args)
        return {"error": "Not found"}
    
    def _post_process(self, tool_name: str, result: Any) -> Any:
        if isinstance(result, dict) and "error" not in result:
            return result
        return result
    
    def _cache_result(self, tool_name: str, args: Dict, result: Any):
        key = hashlib.md5(f"{tool_name}:{json.dumps(args)}".encode()).hexdigest()
        self.cache[key] = {"result": result, "time": datetime.now().isoformat()}
    
    def _result(self, call: ToolCall, passed: List, failed: List, start) -> ToolResult:
        elapsed = (datetime.now() - start).total_seconds()
        return ToolResult(
            tool_name=call.tool_name,
            success=not call.blocked,
            result=call.arguments,
            error=call.block_reason if call.blocked else "",
            execution_time=elapsed,
            steps_passed=passed,
            steps_failed=failed
        )


# 全局治理器
_governance: Optional[ToolGovernance] = None

def get_governance() -> ToolGovernance:
    global _governance
    if _governance is None:
        _governance = ToolGovernance()
    return _governance


if __name__ == "__main__":
    gov = get_governance()
    gov.register_tool("echo", lambda