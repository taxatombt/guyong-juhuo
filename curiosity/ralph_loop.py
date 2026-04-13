#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ralph_loop.py — Ralph 自引用反馈循环

集成来源：Ralph Wiggum 自引用循环 → curiosity/
设计原则：
- completion promise 驱动：达到目标才退出，否则继续
- 自引用反馈循环检测：防止 AI 在自己身上打转
- Ralph Wiggum 特色：自我指涉检测

使用方式：
    from curiosity.ralph_loop import RalphLoop

    loop = RalphLoop(promise=lambda: len(discovered) >= 5, max_iterations=20)
    result = loop.run()
"""

from typing import Callable, Optional, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RalphState:
    iteration: int
    has_new_info: bool
    promise_met: bool
    deadlock: bool
    message: str


class RalphLoop:
    def __init__(
        self,
        promise: Callable[[], bool],
        max_iterations: int = 20,
        patience: int = 3,
        on_check: Optional[Callable[[int, RalphState], None]] = None,
    ):
        self.promise = promise
        self.max_iterations = max_iterations
        self.patience = patience
        self.on_check = on_check
        self._iter_count = 0
        self._no_new_info_streak = 0
        self._history: List[RalphState] = []

    def step(self, has_new_info: bool = True, meta: Optional[str] = None) -> RalphState:
        self._iter_count += 1
        deadlock = self._is_deadlock()
        if not has_new_info:
            self._no_new_info_streak += 1
        else:
            self._no_new_info_streak = 0
        try:
            promise_met = self.promise()
        except Exception:
            promise_met = False
        state = RalphState(
            iteration=self._iter_count,
            has_new_info=has_new_info,
            promise_met=promise_met,
            deadlock=deadlock,
            message=f"iter={self._iter_count} new={has_new_info} deadlock={deadlock} promise={promise_met}"
            + (f" META={meta[:30]}" if meta else ""),
        )
        self._history.append(state)
        if self.on_check:
            self.on_check(self._iter_count, state)
        return state

    def _is_deadlock(self) -> bool:
        if len(self._history) < self.patience:
            return False
        return all(not s.has_new_info for s in self._history[-self.patience:])

    def run(self) -> RalphState:
        while True:
            if self._iter_count >= self.max_iterations:
                return self.step(has_new_info=False, meta="max_iter")
            if self.promise():
                return self.step(has_new_info=True, meta="promise_done")
            if self._is_deadlock():
                return self.step(has_new_info=False, meta="DEADLOCK")
            break

    def report(self) -> str:
        lines = [f"Ralph Report — {self._iter_count}/{self.max_iterations} iterations"]
        lines += [f"  {s.message}" for s in self._history[-5:]]
        return "\n".join(lines)
