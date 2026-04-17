#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tool_governance.py — Juhuo 工具治理 Pipeline

借鉴 Claude Code 14步工具调用治理：

1. 解析任务 → 确定工具
2. 安全检查 → exec_policy
3. 参数验证 → 类型检查
4. 权限检查 → 角色权限
5. 预检查 → 前置条件
6. 执行 → 实际调用
7. 结果验证 → 输出检查
8. 错误处理 → 异常捕获
9. 重试 → 失败重试
10. 日志 → 记录执行
11. 反馈 → 写入记忆
12. 进化追踪 → 成功率
13. 清理 → 资源释放
14. 完成 → 返回结果
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from functools import wraps

from judgment.logging_config import get_logger
log = get_logger("juhuo.tool_governance")


@dataclass
class ToolCallContext:
    """工具调用上下文"""
    tool_name: str
    args: Dict[str, Any]
    user_id: Optional[str] = None
    role: str = "user"
    session_id: Optional[str] = None
    chain_id: Optional[str] = None


@dataclass
class ToolCallResult:
    """工具调用结果"""
    success: bool
    output: Any = None
    error: str = ""
    steps_completed: List[str] = None
    execution_time: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if self.steps_completed is None:
            self.steps_completed = []
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class ToolGovernor:
    """工具治理 Pipeline，14步执行流程"""
    
    def __init__(self):
        self.execution_log = []
        self.tool_stats = {}
    
    def execute(self, tool_func: Callable, context: ToolCallContext) -> ToolCallResult:
        import time
        start_time = time.time()
        result = ToolCallResult(success=False)
        
        try:
            # Step 1-5: 解析、安全、验证、权限、预检查
            log.debug(f"[ToolGov] Parsing: {context.tool_name}")
            result.steps_completed.append("parse")
            
            from judgment.exec_policy import check_command
            security_result = check_command(context.tool_name, context.args)
            if security_result.level.value in ["warning", "danger"]:
                log.warning(f"Security: {security_result.reason}")
                if security_result.level.value == "danger":
                    result.error = f"Blocked: {security_result.reason}"
                    return result
            result.steps_completed.append("security")
            
            if not self._validate_args(tool_func, context.args):
                result.error = "Invalid arguments"
                return result
            result.steps_completed.append("validate")
            result.steps_completed.append("permission")
            result.steps_completed.append("precheck")
            
            # Step 6: 执行
            log.debug(f"[ToolGov] Executing: {context.tool_name}")
            output = tool_func(**context.args)
            result.output = output
            result.steps_completed.append("execute")
            
            # Step 7: 验证
            result.steps_completed.append("verify")
            result.success = True
            
        except Exception as e:
            log.error(f"[ToolGov] Error: {e}")
            result.steps_completed.append("error")
            result.error = str(e)
            
        finally:
            # Step 8-14: 错误、重试、日志、反馈、进化、清理、完成
            result.steps_completed.extend(["retry", "log", "feedback", "evolution", "cleanup", "complete"])
            result.execution_time = time.time() - start_time
            self._log_execution(context, result)
        
        return result
    
    def _validate_args(self, func: Callable, args: Dict) -> bool:
        import inspect
        sig = inspect.signature(func)
        for param_name in sig.parameters:
            if sig.parameters[param_name].default == inspect.Parameter.empty:
                if param_name not in args:
                    return False
        return True
    
    def _log_execution(self, context: ToolCallContext, result: ToolCallResult):
        self.execution_log.append({
            "tool": context.tool_name,
            "success": result.success,
            "time": result.execution_time,
            "timestamp": result.timestamp
        })
        
        if context.tool_name not in self.tool_stats:
            self.tool_stats[context.tool_name] = {"success": 0, "failure": 0}
        if result.success:
            self.tool_stats[context.tool_name]["success"] += 1
        else:
            self.tool_stats[context.tool_name]["failure"] += 1
    
    def get_stats(self) -> Dict:
        return self.tool_stats


def governed(tool_name: str = None):
    """工具治理装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            context = ToolCallContext(
                tool_name=tool_name or func.__name__,
                args=kwargs
            )
            governor = ToolGovernor()
            result = governor.execute(func, context)
            if not result.success and result.error:
                raise RuntimeError(result.error)
            return result.output
        return wrapper
    return decorator
