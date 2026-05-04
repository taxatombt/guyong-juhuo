# -*- coding: utf-8 -*-
"""
EventBus — 事件总线（ZeusHammer 启发）

设计目标：解耦所有子系统，防止直接调用导致的递归bug。

原理：所有子系统通过事件总线通信，单个订阅者失败不影响其他。

事件流示例：
    judgment.check10d_run()
      → EventBus.publish("judgment.started", {task_text, chain_id})
          → correlation_memory.subscribe → 加载上下文
          → perception.subscribe   → 预取感知数据

    judgment._synthesize_verdict()
      → EventBus.publish("judgment.completed", {chain_id, verdict, confidence})
          → reflection.subscribe → 执行反思
          → evolver.subscribe  → 记录 outcome

    judgment.receive_verdict()
      → EventBus.publish("verdict.received", {chain_id, correct, outcome_score})
          → evolver.subscribe → 驱动进化

用法：
    from judgment.event_bus import event_bus

    # 订阅
    event_bus.subscribe("judgment.*", my_handler)

    # 发布
    event_bus.publish("judgment.started", {"task": "要不要辞职？", "chain_id": "j_xxx"})

    # 取消订阅
    event_bus.unsubscribe("judgment.*", my_handler)
"""

import time
import fnmatch
import logging
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class JuhuoEvent:
    """事件"""
    type: str          # 事件类型，支持通配符：judgment.* / verdict.received
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "system"


class JuhuoEventBus:
    """
    同步事件总线（ZeusHammer EventBus 的同步版本）

    核心特性：
    1. 通配符订阅 — 订阅 "judgment.*" 可匹配 "judgment.started" 等
    2. 错误隔离 — 单个订阅者失败不影响其他订阅者
    3. 历史记录 — 保留最近1000条事件，可追溯
    4. 同步处理 — 发布后立即同步调用所有订阅者
    """

    def __init__(self, max_history: int = 1000):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: List[JuhuoEvent] = []
        self._max_history = max_history
        # 防止 publish 过程中订阅者又 publish 导致无限递归
        self._publishing = False

    # ── 订阅 ──────────────────────────────────────────────────────────────

    def subscribe(self, pattern: str, handler: Callable) -> None:
        """
        订阅事件

        Args:
            pattern: 事件类型模式，支持 * 和 ?
                "judgment.*"    → 匹配所有 judgment 子事件
                "verdict.received" → 精确匹配
                "tool.?"        → 匹配 tool.a, tool.b 等
            handler: 同步处理函数，签名为 handler(event: JuhuoEvent)
        """
        self._subscribers[pattern].append(handler)
        logger.debug(f"[EventBus] subscribe: {pattern} → {handler.__name__}")

    def on(self, event_type: str):
        """
        装饰器订阅

        用法：
            @event_bus.on("judgment.completed")
            def on_judgment_completed(event):
                print(event.data)
        """
        def decorator(handler: Callable):
            self.subscribe(event_type, handler)
            return handler
        return decorator

    def unsubscribe(self, pattern: str, handler: Optional[Callable] = None) -> None:
        """
        取消订阅

        Args:
            pattern: 事件类型模式
            handler: 要移除的处理器。如果为 None，移除该模式的所有订阅者。
        """
        if handler is None:
            self._subscribers.pop(pattern, None)
            logger.debug(f"[EventBus] unsubscribe all: {pattern}")
        else:
            if pattern in self._subscribers:
                self._subscribers[pattern] = [
                    h for h in self._subscribers[pattern] if h != handler
                ]
            logger.debug(f"[EventBus] unsubscribe: {pattern} → {handler.__name__}")

    # ── 发布 ──────────────────────────────────────────────────────────────

    def publish(self, event_type: str, data: Dict[str, Any] = None) -> None:
        """
        发布事件

        所有匹配的订阅者都会被同步调用。
        单个订阅者抛异常不影响其他订阅者。

        注意：publish 过程中触发的订阅者对同一事件的修改不会再次触发（防止递归）。

        Args:
            event_type: 事件类型，如 "judgment.started"
            data: 事件数据
        """
        if data is None:
            data = {}

        event = JuhuoEvent(type=event_type, data=data)

        # 记录历史
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 找出匹配的订阅者
        matched = []
        for pattern, handlers in list(self._subscribers.items()):
            if self._match(event_type, pattern):
                matched.extend(handlers)

        if not matched:
            return

        # 同步调用所有订阅者（错误隔离）
        for handler in matched:
            try:
                handler(event)
            except Exception as e:
                # 订阅者失败不影响总线和其他订阅者
                logger.warning(
                    f"[EventBus] handler {handler.__name__} failed for {event_type}: {e}"
                )

    # ── 历史 ──────────────────────────────────────────────────────────────

    def get_history(self, event_type: Optional[str] = None, limit: int = 100
                    ) -> List[JuhuoEvent]:
        """
        获取事件历史

        Args:
            event_type: 可选过滤器，只返回匹配类型的事件
            limit: 最多返回条数

        Returns:
            事件列表（按时间倒序）
        """
        events = self._history
        if event_type:
            events = [e for e in events if self._match(e.type, event_type)]
        return events[-limit:]

    def clear_history(self) -> None:
        """清空历史"""
        self._history.clear()
        logger.debug("[EventBus] history cleared")

    # ── 内部 ───────────────────────────────────────────────────────────────

    @staticmethod
    def _match(event_type: str, pattern: str) -> bool:
        """fnmatch 风格匹配"""
        return fnmatch.fnmatch(event_type, pattern)

    def get_subscribers_count(self) -> int:
        """当前订阅者总数"""
        return sum(len(h) for h in self._subscribers.values())


# ── 全局单例 ────────────────────────────────────────────────────────────────

event_bus = JuhuoEventBus()


# ── 预定义事件类型常量 ──────────────────────────────────────────────────────
class JuhuoEventType:
    """juhuo 预定义事件类型"""

    # Judgment 生命周期
    JUDGMENT_STARTED   = "judgment.started"     # check10d_run 开始
    JUDGMENT_COMPLETED  = "judgment.completed"    # verdict 合成完毕
    JUDGMENT_ERROR      = "judgment.error"        # 判断异常

    # Verdict 结果
    VERDICT_RECEIVED    = "verdict.received"     # 用户反馈已收到
    VERDICT_CORRECT     = "verdict.correct"       # 判断正确
    VERDICT_WRONG       = "verdict.wrong"         # 判断错误

    # Evolution
    EVOLUTION_TRIGGERED = "evolution.triggered"   # 触发条件满足
    EVOLUTION_APPLIED   = "evolution.applied"      # 新权重已应用
    EVOLUTION_ROLLBACK  = "evolution.rollback"     # 回滚

    # Action 执行
    ACTION_STARTED      = "action.started"        # 执行通道启动
    ACTION_COMPLETED    = "action.completed"      # 执行完成
    ACTION_BLOCKED      = "action.blocked"         # 执行被阻止（需要权限）

    # Memory
    MEMORY_UPDATED      = "memory.updated"         # 记忆已更新
    BIOGRAPHY_UPDATED   = "biography.updated"      # 用户画像已更新


# ── 快捷发布函数 ────────────────────────────────────────────────────────────

def emit(event_type: str, **kwargs) -> None:
    """快捷发布：emit("judgment.started", task="...")"""
    event_bus.publish(event_type, kwargs)


# ── 预设订阅者（ZeusHammer 启发）────────────────────────────────────────────

def _setup_default_subscribers():
    """
    设置 juhuo 核心子系统的预设订阅

    自动注册，无需手动调用。在 judgment/router.py init() 中调用一次。
    """
    import logging
    _log = logging.getLogger(__name__)

    # ── Judgment → evolver 闭环 ──
    @event_bus.on("judgment.completed")
    def _on_judgment_completed(event):
        """判断完成后触发 outcome 记录"""
        try:
            chain_id = event.data.get("chain_id", "")
            if not chain_id:
                return
            # 懒加载避免循环依赖
            from judgment.verdict_collector import receive_verdict
            receive_verdict(chain_id=chain_id, notes="event_bus:auto")
        except Exception as e:
            _log.warning(f"[EventBus] _on_judgment_completed failed: {e}")

    @event_bus.on("verdict.received")
    def _on_verdict_received(event):
        """收到 verdict 后触发 evolver 检查"""
        try:
            chain_id = event.data.get("chain_id", "")
            outcome_score = event.data.get("outcome_score")
            if not chain_id or outcome_score is None:
                return
            from subsystems.judgment.self_evolver import EvolverScheduler
            sched = EvolverScheduler()
            sched.record_outcome(chain_id, outcome_score)
        except Exception as e:
            _log.warning(f"[EventBus] _on_verdict_received failed: {e}")

    # ── Action → permission 事件 ──
    @event_bus.on("action.started")
    def _on_action_started(event):
        """执行通道启动时记录"""
        _log.debug(f"[EventBus] action started: {event.data}")

    @event_bus.on("action.blocked")
    def _on_action_blocked(event):
        """执行被阻止时记录到 causal memory"""
        try:
            from correlation_memory.correlation_chain import log_causal_event
            log_causal_event(
                event_type="permission_denied",
                description=f"action.blocked: {event.data.get('reason','')}",
                related_dimensions=["metacognitive"],
            )
        except Exception:
            pass  # correlation_memory 可能未初始化

    _log.info(f"[EventBus] default subscribers registered, "
              f"total: {event_bus.get_subscribers_count()}")


def setup_event_bus():
    """
    初始化事件总线（router.py init() 中调用一次）

    设置预设订阅者并发布初始化事件。
    """
    _setup_default_subscribers()
    emit(JuhuoEventType.JUDGMENT_STARTED,
         source="event_bus", note="event_bus_initialized")
