#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
life_cycle_hooks.py — Juhuo 生命周期钩子

灵感来自Hermes的9个钩子，Juhuo实现关键的几个:

1. prefetch_all(query)      ✅ 每轮前背景召回
2. on_turn_start()          ✅ 新Turn开始
3. on_session_end()         ✅ 会话结束
4. on_pre_compress()        ✅ 压缩前
5. on_memory_write()         ✅ 写入时
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

from judgment.judgment_db import get_conn
from judgment.stop_hook import get_stop_hook, finalize_session
from judgment.context_fence import build_judgment_context


@dataclass
class HookContext:
    """钩子上下文"""
    session_id: str
    turn_count: int = 0
    total_judgments: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)


class LifeCycleHooks:
    """
    生命周期钩子编排器
    
    使用方式:
    hooks = LifeCycleHooks()
    context = hooks.prefetch_all("用户当前任务")
    hooks.on_turn_start()
    # ... 判断逻辑 ...
    hooks.on_memory_write(...)  # 写入时
    hooks.on_session_end()       # 会话结束
    """

    def __init__(self, session_id: str = None):
        self.session_id = session_id or f"s_{int(datetime.now().timestamp()*1000)}"
        self.turn_count = 0
        self.hooks_enabled = True
        
        # 各模块召回器
        self._causal_recaller = None
        self._fitness_recaller = None
        self._instinct_recaller = None

    # ── 钩子1: prefetch_all ─────────────────────────────────────────
    def prefetch_all(self, query: str) -> Dict[str, Any]:
        """
        每轮前背景召回
        
        从各模块召回相关上下文:
        - causal_memory: 相似历史
        - fitness: 维度准确率
        - instinct: 相关教训
        """
        if not self.hooks_enabled:
            return {}
        
        context = {}
        
        # 1. 因果记忆召回
        try:
            from causal_memory.causal_memory import recall_causal_history
            causal = recall_causal_history(query, max_events=3)
            context["causal_memory"] = causal
        except Exception:
            context["causal_memory"] = {}
        
        # 2. Fitness召回
        try:
            from judgment.fitness_evolution import get_fitness
            fitness = get_fitness()
            context["fitness"] = fitness.get_stats()
            context["low_confidence_dims"] = fitness.get_low_confidence_dims()
        except Exception:
            context["fitness"] = {}
        
        # 3. Instinct召回
        try:
            from judgment.stop_hook import get_instincts
            instincts = get_instincts(min_confidence=0.6, limit=5)
            context["instinct"] = instincts
        except Exception:
            context["instinct"] = []
        
        # 4. Self-model召回
        try:
            from self_model.self_model import get_self_warnings
            warnings = get_self_warnings()
            context["self_model"] = {"warnings": warnings}
        except Exception:
            context["self_model"] = {}
        
        # 5. 构建围栏上下文
        try:
            fenced_context = build_judgment_context(
                causal_memory=context.get("causal_memory"),
                self_model=context.get("self_model"),
                instinct=context.get("instinct"),
                fitness=context.get("fitness"),
            )
            context["fenced_context"] = fenced_context
        except Exception:
            context["fenced_context"] = ""
        
        return context

    # ── 钩子2: on_turn_start ────────────────────────────────────────
    def on_turn_start(self) -> Dict:
        """
        新Turn开始
        
        递增turn_count，清理临时状态
        """
        self.turn_count += 1
        
        return {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "timestamp": datetime.now().isoformat(),
        }

    # ── 钩子3: on_memory_write ─────────────────────────────────────
    def on_memory_write(
        self,
        module: str,
        data: Dict,
        event_type: str = "judgment",
    ) -> bool:
        """
        写入记忆时触发
        
        用途:
        - 验证写入数据的合法性
        - 触发关联模块的同步
        """
        if not self.hooks_enabled:
            return True
        
        try:
            # 安全扫描
            if module == "judgment":
                from judgment.context_fence import get_fence
                fence = get_fence()
                for key, value in data.items():
                    if isinstance(value, str):
                        threats = fence.scan_threats(value)
                        if threats:
                            print(f"[Hook警告] 检测到{len(threats)}个安全威胁")
                            return False
            
            # 触发关联模块
            if event_type == "judgment":
                # judgment写入 → 触发curiosity同步
                try:
                    from curiosity.curiosity_engine import trigger_from_judgment
                    trigger_from_judgment(data)
                except Exception:
                    pass
            
            return True
        
        except Exception as e:
            print(f"[Hook错误] on_memory_write: {e}")
            return False

    # ── 钩子4: on_pre_compress ─────────────────────────────────────
    def on_pre_compress(self, context: str) -> str:
        """
        压缩前触发
        
        用途:
        - 保护关键信息不被压缩掉
        - 提取需要保留的片段
        """
        if not self.hooks_enabled:
            return context
        
        try:
            from causal_memory.compressor import fast_compress
            
            # 识别需要保护的内容
            protected_patterns = [
                r'\[重要\].*?(?=\n|$)',
                r'判断链.*?已验证',
                r'准确率.*?\d+%',
            ]
            
            protected = []
            for pattern in protected_patterns:
                import re
                matches = re.findall(pattern, context)
                protected.extend(matches)
            
            # 返回需要保护的内容摘要
            if protected:
                return "[保护片段]\n" + "\n".join(protected[:5])
            
            return context
        
        except Exception:
            return context

    # ── 钩子5: on_session_end ───────────────────────────────────────
    def on_session_end(self) -> Dict:
        """
        会话结束
        
        执行:
        - finalize_session生成instinct
        - 保存会话统计
        - 清理临时状态
        """
        if not self.hooks_enabled:
            return {}
        
        result = {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "timestamp": datetime.now().isoformat(),
        }
        
        # 1. Stop Hook生成instinct
        try:
            instincts = finalize_session()
            result["instincts_generated"] = len(instincts)
        except Exception:
            result["instincts_generated"] = 0
        
        # 2. 保存会话统计
        try:
            with get_conn() as c:
                c.execute("""
                    INSERT OR IGNORE INTO session_stats
                    (session_id, turn_count, total_judgments, ended_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    self.session_id,
                    self.turn_count,
                    result.get("total_judgments", 0),
                    datetime.now().isoformat(),
                ))
                c.commit()
        except Exception:
            pass
        
        # 3. 重置状态
        self.turn_count = 0
        
        return result


# ── 数据库表 ───────────────────────────────────────────────────────
def init_hook_db():
    """初始化钩子相关表"""
    with get_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS session_stats (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                turn_count INTEGER,
                total_judgments INTEGER,
                ended_at TEXT
            );
        """)
        c.commit()


# ── 全局实例 ────────────────────────────────────────────────────────
_global_hooks: Optional[LifeCycleHooks] = None


def get_lifecycle_hooks() -> LifeCycleHooks:
    global _global_hooks
    if _global_hooks is None:
        _global_hooks = LifeCycleHooks()
    return _global_hooks


def prefetch_all(query: str) -> Dict[str, Any]:
    """快捷函数：每轮前召回"""
    return get_lifecycle_hooks().prefetch_all(query)


def on_session_end() -> Dict:
    """快捷函数：会话结束"""
    return get_lifecycle_hooks().on_session_end()


init_hook_db()
