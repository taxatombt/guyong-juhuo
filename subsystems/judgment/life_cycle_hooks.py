#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
life_cycle_hooks.py — Juhuo 生命周期钩子完整版

Hermes 9个钩子完整实现:

1. build_system_prompt()     ✅ 收集系统提示块
2. prefetch_all(query)       ✅ 每轮前背景召回
3. sync_all(user, asst)      ✅ 每轮后异步写入
4. on_turn_start()           ✅ 新Turn开始
5. on_session_end()          ✅ 会话结束
6. on_pre_compress()         ✅ 压缩前
7. on_memory_write()         ✅ 写入时
8. on_delegation()           ✅ 子Agent完成通知
9. on_turn_end()             ✅ Turn结束
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from threading import Thread
import queue

from .judgment_db import get_conn
from .pre_tool_hook import PreToolUseOutcome


@dataclass
class HookContext:
    session_id: str
    turn_count: int = 0
    total_judgments: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)


@dataclass
class DelegationResult:
    agent_id: str
    task: str
    result: Any
    success: bool
    duration: float


class LifeCycleHooks:
    """
    生命周期钩子编排器
    
    使用方式:
    hooks = LifeCycleHooks()
    
    # 会话开始
    system_prompt = hooks.build_system_prompt()
    
    # 每轮
    hooks.on_turn_start()
    context = hooks.prefetch_all(query)
    # ... 判断逻辑 ...
    hooks.on_turn_end()
    
    # 异步写入
    hooks.sync_all(user_msg, assistant_msg)
    
    # 子Agent
    result = hooks.on_delegation("sub_agent", task, lambda: do_task())
    
    # 会话结束
    hooks.on_session_end()
    """

    def __init__(self, session_id: str = None):
        self.session_id = session_id or f"s_{int(datetime.now().timestamp()*1000)}"
        self.turn_count = 0
        self.hooks_enabled = True
        self._sync_queue = queue.Queue()
        self._delegation_handlers: List[Callable] = []
        
        # 初始化各模块召回器
        self._init_recallers()

    def _init_recallers(self):
        """初始化召回器（延迟导入避免循环依赖）"""
        self._causal_recaller = None
        self._fitness_recaller = None
        self._instinct_recaller = None

    # ── 钩子1: build_system_prompt ─────────────────────────────────
    def build_system_prompt(self) -> str:
        """
        会话开始：收集系统提示块
        """
        parts = [
            "你是一个深度思考的AI Agent。",
        ]
        
        # 从各模块收集系统提示
        try:
            from self_model.self_model import get_self_description
            self_desc = get_self_description()
            if self_desc:
                parts.append(f"\n[自我认知]\n{self_desc}")
        except:
            pass
        
        try:
            from .fitness_evolution import get_fitness_stats
            stats = get_fitness_stats()
            if stats.get("overall_accuracy", 0) > 0:
                parts.append(f"\n[判断准确率] {stats['overall_accuracy']:.1%}")
        except:
            pass
        
        return "\n".join(parts)

    # ── 钩子2: prefetch_all ────────────────────────────────────────
    def prefetch_all(self, query: str) -> Dict[str, Any]:
        """
        每轮前背景召回
        """
        if not self.hooks_enabled:
            return {}
        
        context = {}
        
        # 因果记忆召回
        try:
            from causal_memory.causal_memory import recall_causal_history
            causal = recall_causal_history(query, max_events=3)
            context["causal_memory"] = causal
        except:
            context["causal_memory"] = {}
        
        # Fitness召回
        try:
            from .fitness_evolution import get_fitness
            fitness = get_fitness()
            context["fitness"] = fitness.get_stats()
            context["low_confidence_dims"] = fitness.get_low_confidence_dims()
        except:
            context["fitness"] = {}
        
        # Instinct召回
        try:
            from .stop_hook import get_instincts
            instincts = get_instincts(min_confidence=0.6, limit=5)
            context["instinct"] = instincts
        except:
            context["instinct"] = []
        
        # 构建围栏上下文
        try:
            from .context_fence import build_judgment_context
            fenced_context = build_judgment_context(
                causal_memory=context.get("causal_memory"),
                instinct=context.get("instinct"),
                fitness=context.get("fitness"),
            )
            context["fenced_context"] = fenced_context
        except:
            context["fenced_context"] = ""
        
        return context

    # ── 钩子3: on_turn_start ───────────────────────────────────────
    def on_turn_start(self) -> HookContext:
        """
        新Turn开始
        """
        self.turn_count += 1
        
        ctx = HookContext(
            session_id=self.session_id,
            turn_count=self.turn_count,
            timestamp=datetime.now().isoformat(),
        )
        
        return ctx

    # ── 钩子4: on_turn_end ─────────────────────────────────────────
    def on_turn_end(self, user_msg: str = "", assistant_msg: str = "") -> Dict:
        """
        Turn结束：准备同步
        """
        return {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "user_msg_preview": user_msg[:100] if user_msg else "",
            "assistant_msg_preview": assistant_msg[:100] if assistant_msg else "",
            "timestamp": datetime.now().isoformat(),
        }

    # ── 钩子5: sync_all ────────────────────────────────────────────
    def sync_all(self, user_msg: str = "", assistant_msg: str = ""):
        """
        每轮后异步写入
        
        非阻塞，放入队列
        """
        self._sync_queue.put({
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "user_msg": user_msg,
            "assistant_msg": assistant_msg,
            "timestamp": datetime.now().isoformat(),
        })
        
        # 异步处理（简单实现）
        Thread(target=self._process_sync_queue, daemon=True).start()

    def _process_sync_queue(self):
        """处理同步队列"""
        try:
            while not self._sync_queue.empty():
                item = self._sync_queue.get_nowait()
                self._sync_to_db(item)
        except:
            pass

    def _sync_to_db(self, item: Dict):
        """写入数据库"""
        try:
            with get_conn() as c:
                c.execute("""
                    INSERT OR IGNORE INTO turn_sync 
                    (session_id, turn_count, user_msg, assistant_msg, synced_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    item["session_id"],
                    item["turn_count"],
                    item.get("user_msg", "")[:1000],
                    item.get("assistant_msg", "")[:1000],
                    item["timestamp"],
                ))
                c.commit()
        except:
            pass

    # ── 钩子6: on_memory_write ─────────────────────────────────────
    def on_memory_write(self, module: str, data: Dict, event_type: str = "judgment") -> bool:
        """
        写入记忆时触发
        """
        if not self.hooks_enabled:
            return True
        
        try:
            # 安全扫描
            if module == "judgment":
                from .context_fence import get_fence
                fence = get_fence()
                for key, value in data.items():
                    if isinstance(value, str):
                        threats = fence.scan_threats(value)
                        if threats:
                            print(f"[Hook警告] {module}写入检测到{len(threats)}个威胁")
                            return False
            
            # 触发关联模块
            if event_type == "judgment":
                try:
                    # 1. curiosity ← judgment
                    from curiosity.curiosity_engine import trigger_from_judgment
                    trigger_from_judgment(data)
                except:
                    pass
                
                try:
                    # 2. emotion ← judgment
                    from emotion_system.emotion_system import EmotionSystem
                    emotion_sys = EmotionSystem()
                    task_text = data.get("task", data.get("task_text", ""))
                    emotion_result = emotion_sys.detect_emotion(task_text)
                    
                    if emotion_result and emotion_result.get("is_signal"):
                        # 3. emotion → curiosity（情绪触发好奇心）
                        try:
                            from curiosity.curiosity_engine import activate_from_emotion
                            activate_from_emotion(emotion_result)
                        except:
                            pass
                except:
                    pass
                
                # 4. 反馈 → 4类记忆（judgment完成后保存反馈）
                try:
                    outcome = data.get("outcome", data.get("feedback"))
                    if outcome:
                        # 判断是否正确
                        outcome_type = "correct" if outcome in ("success", True) else "incorrect"
                        
                        # 保存反馈记忆
                        from memory_system import save_feedback_memory, MemoryEngine
                        engine = MemoryEngine()
                        
                        # 判断是否值得保存
                        if engine.is_worth_saving(data.get("task", "")):
                            save_feedback_memory(
                                content=f"判断「{data.get('task', '')[:50]}」的结果是{outcome_type}",
                                outcome=outcome_type,
                                trigger_context=data.get("task", ""),
                            )
                except:
                    pass
            
            return True
        except Exception as e:
            print(f"[Hook错误] on_memory_write: {e}")
            return False

    # ── 钩子7: on_pre_compress ─────────────────────────────────────
    def on_pre_compress(self, context: str) -> str:
        """压缩前触发：保护关键信息"""
        if not self.hooks_enabled:
            return context
        
        try:
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
            
            if protected:
                return "[保护片段]\n" + "\n".join(protected[:5])
            return context
        except:
            return context

    # ── 钩子8: on_delegation ────────────────────────────────────────
    def on_delegation(
        self, 
        agent_id: str, 
        task: str, 
        callable_fn: Callable,
        timeout: float = 300.0,
    ) -> DelegationResult:
        """
        子Agent完成通知
        
        用于:
        - 追踪子Agent执行
        - 收集子Agent结果
        - 触发相关闭环
        """
        start_time = datetime.now().timestamp()
        success = False
        result = None
        
        try:
            result = callable_fn()
            success = True
        except Exception as e:
            result = str(e)
        finally:
            duration = datetime.now().timestamp() - start_time
        
        delegation_result = DelegationResult(
            agent_id=agent_id,
            task=task[:200],
            result=result,
            success=success,
            duration=duration,
        )
        
        # 触发handlers
        for handler in self._delegation_handlers:
            try:
                handler(delegation_result)
            except:
                pass
        
        # 保存到数据库
        self._save_delegation(delegation_result)
        
        return delegation_result

    def register_delegation_handler(self, handler: Callable):
        """注册delegation处理器"""
        self._delegation_handlers.append(handler)

    def _save_delegation(self, result: DelegationResult):
        """保存delegation结果"""
        try:
            with get_conn() as c:
                c.execute("""
                    INSERT OR IGNORE INTO delegation_results
                    (agent_id, task, success, duration, result, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    result.agent_id,
                    result.task,
                    1 if result.success else 0,
                    result.duration,
                    str(result.result)[:500] if result.result else "",
                    datetime.now().isoformat(),
                ))
                c.commit()
        except:
            pass

    # ── 钩子9: on_session_end ───────────────────────────────────────
    def on_session_end(self) -> Dict:
        """会话结束"""
        if not self.hooks_enabled:
            return {}
        
        result = {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Stop Hook生成instinct
        try:
            from .stop_hook import finalize_session
            instincts = finalize_session()
            result["instincts_generated"] = len(instincts)
        except:
            result["instincts_generated"] = 0
        
        # 保存会话统计
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
        except:
            pass
        
        self.turn_count = 0
        return result

    # ── 钩子10: on_pre_action ────────────────────────────────────────
    def on_pre_action(self, tool_name: str, args: Dict, command: str = "") -> PreToolUseOutcome:
        """
        Codex启发: 动作执行前安全检查
        
        检测:
        - 危险命令
        - 权限问题
        - 频率限制
        """
        try:
            from .pre_tool_hook import get_pre_hook, PreToolUseRequest
            hook = get_pre_hook()
            request = PreToolUseRequest(
                tool_name=tool_name,
                args=args,
                command=command,
                session_id=self.session_id,
            )
            return hook.check(request)
        except Exception as e:
            print(f"[Hook错误] on_pre_action: {e}")
            from .pre_tool_hook import PreToolUseOutcome, HookAction
            return PreToolUseOutcome(action=HookAction.ALLOW, should_block=False)

    # ── 钩子11: on_post_action ───────────────────────────────────────
    def on_post_action(self, tool_name: str, success: bool, output: str = "", error: str = "", duration_ms: float = 0.0):
        """
        Codex启发: 动作执行后记录
        """
        try:
            from .pre_tool_hook import get_post_hook, PostToolUseResult
            hook = get_post_hook()
            result = PostToolUseResult(
                tool_name=tool_name,
                success=success,
                output=output,
                error=error,
                duration_ms=duration_ms,
            )
            hook.record(result)
        except Exception as e:
            print(f"[Hook错误] on_post_action: {e}")


# ── 数据库表 ─────────────────────────────────────────────────────
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
            
            CREATE TABLE IF NOT EXISTS turn_sync (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                turn_count INTEGER,
                user_msg TEXT,
                assistant_msg TEXT,
                synced_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS delegation_results (
                id INTEGER PRIMARY KEY,
                agent_id TEXT,
                task TEXT,
                success INTEGER,
                duration REAL,
                result TEXT,
                created_at TEXT
            );
        """)
        c.commit()


# ── 全局实例 ──────────────────────────────────────────────────────
_global_hooks: Optional[LifeCycleHooks] = None

def get_lifecycle_hooks() -> LifeCycleHooks:
    global _global_hooks
    if _global_hooks is None:
        _global_hooks = LifeCycleHooks()
    return _global_hooks

def build_system_prompt() -> str:
    """快捷函数：构建系统提示"""
    return get_lifecycle_hooks().build_system_prompt()

def prefetch_all(query: str) -> Dict[str, Any]:
    """快捷函数：每轮前召回"""
    return get_lifecycle_hooks().prefetch_all(query)

def on_turn_start() -> HookContext:
    """快捷函数：Turn开始"""
    return get_lifecycle_hooks().on_turn_start()

def on_session_end() -> Dict:
    """快捷函数：会话结束"""
    return get_lifecycle_hooks().on_session_end()

def on_delegation(agent_id: str, task: str, fn: Callable, timeout: float = 300.0) -> DelegationResult:
    """快捷函数：子Agent委托"""
    return get_lifecycle_hooks().on_delegation(agent_id, task, fn, timeout)

# ── Codex钩子 ──────────────────────────────────────────────────────
from .pre_tool_hook import PreToolUseOutcome

def on_pre_action(tool_name: str, args: Dict, command: str = "") -> PreToolUseOutcome:
    """Codex启发: 动作执行前安全检查"""
    return get_lifecycle_hooks().on_pre_action(tool_name, args, command)

def on_post_action(tool_name: str, success: bool, output: str = "", error: str = "", duration_ms: float = 0.0):
    """Codex启发: 动作执行后记录"""
    return get_lifecycle_hooks().on_post_action(tool_name, success, output, error, duration_ms)

init_hook_db()
