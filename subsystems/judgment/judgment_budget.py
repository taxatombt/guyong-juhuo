"""
subsystems/judgment/judgment_budget.py
=====================================
juhuo 判断预算保护机制
参考 Hermes Agent max_turns/max_cost 预算模型

防止：
- 无限递归（栈深度保护）
- verdict 数爆炸（会话上限）
- LLM 调用超时（时间保护）
"""
import threading
import time
import os
from functools import wraps
from typing import Optional

class BudgetExceeded(Exception):
    """预算耗尽时抛出"""
    pass

class JudgmentBudget:
    """
    判断预算管理器（TLS 线程局部存储）
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = object.__new__(cls)
                    instance._init(**kwargs)
                    cls._instance = instance
        return cls._instance

    def _init(self,
               max_depth: int = 20,
               max_verdicts_per_session: int = 50,
               max_time_s: float = 30.0,
               max_recursive_depth: int = 5):
        self._max_depth = max_depth
        self._max_verdicts = max_verdicts_per_session
        self._max_time = max_time_s
        self._max_recursive = max_recursive_depth
        self._tls = {}

    def _ctx(self):
        tid = threading.current_thread().ident
        if tid not in self._tls:
            self._tls[tid] = {
                "depth": 0,
                "verdict_count": 0,
                "verdicts": [],  # (fn_name, start_time)
                "start_time": time.time(),
            }
        return self._tls[tid]

    def enter(self, fn_name: str):
        """进入一个函数调用层"""
        ctx = self._ctx()
        ctx["depth"] += 1
        ctx["verdict_count"] += 1
        ctx["verdicts"].append((fn_name, time.time()))

        if ctx["depth"] > self._max_recursive:
            raise BudgetExceeded(
                f"[Budget] 递归深度 {ctx['depth']} > {self._max_recursive}，"
                f"fn={fn_name} — 可能存在循环调用"
            )

        elapsed = time.time() - ctx["start_time"]
        if elapsed > self._max_time:
            raise BudgetExceeded(
                f"[Budget] 会话耗时 {elapsed:.1f}s > {self._max_time}s"
            )

        if ctx["verdict_count"] > self._max_verdicts:
            raise BudgetExceeded(
                f"[Budget] verdict数 {ctx['verdict_count']} > {self._max_verdicts}"
            )

    def exit(self, fn_name: str):
        """离开一个函数调用层"""
        ctx = self._ctx()
        ctx["depth"] = max(0, ctx["depth"] - 1)

    def check(self) -> dict:
        """返回当前预算状态"""
        ctx = self._ctx()
        return {
            "depth": ctx["depth"],
            "verdict_count": ctx["verdict_count"],
            "elapsed_s": round(time.time() - ctx["start_time"], 1),
            "remaining_verdicts": max(0, self._max_verdicts - ctx["verdict_count"]),
        }

    def remaining_turns(self, total: int = 50) -> int:
        """返回 LLM 可见的剩余轮次（用于注入 prompt）"""
        ctx = self._ctx()
        used = ctx["verdict_count"]
        remaining = max(0, total - used)
        return remaining

    def reset(self):
        """重置当前线程的预算"""
        tid = threading.current_thread().ident
        if tid in self._tls:
            del self._tls[tid]

    @property
    def max_verdicts(self) -> int:
        return self._max_verdicts

    @property
    def max_recursive(self) -> int:
        return self._max_recursive

    @property
    def max_time(self) -> float:
        return self._max_time


# 全局单例
_budget_instance: Optional[JudgmentBudget] = None
_budget_lock = threading.Lock()


def get_budget(**kwargs) -> JudgmentBudget:
    global _budget_instance
    if _budget_instance is None:
        with _budget_lock:
            if _budget_instance is None:
                _budget_instance = JudgmentBudget(**kwargs)
    return _budget_instance


def budget_protected(fn):
    """装饰器：为函数添加预算保护"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        budget = get_budget()
        budget.enter(fn.__name__)
        try:
            return fn(*args, **kwargs)
        finally:
            budget.exit(fn.__name__)
    return wrapper


def check_budget() -> dict:
    """快速检查预算状态"""
    return get_budget().check()
