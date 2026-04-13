#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hub.py — Juhuo 统一入口

所有子系统通过这一个模块访问，无需记住各模块路径。

使用示例：
    from hub import Juhuo, think

    hub = Juhuo()
    
    # 十维判断
    result = hub.judgment.check10d("安装npm包")
    
    # 好奇心检测
    triggered = hub.curiosity.trigger_from_low_confidence(result)
    
    # 格式化输出
    formatted = hub.output.format_report(result)
    
    # 快捷函数
    think("用户想要一个Flutter App")
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Dict, Any, List


# ─── 路径配置 ───────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"

# 新数据分层结构
MEMORY_FAST_DIR  = DATA_DIR / "memory" / "fast"
MEMORY_SLOW_DIR  = DATA_DIR / "memory" / "slow"
EVOLUTIONS_DIR   = DATA_DIR / "evolutions"
METRICS_DIR      = DATA_DIR / "metrics"
CHECKPOINTS_DIR  = DATA_DIR / "checkpoints"


# ─── 子系统封装 ──────────────────────────────────────────────────────────────

class JudgmentSystem:
    """
    封装 judgment 模块。
    
    真实 API: check10d(), route(), format_report(), format_structured(),
              detect_task_types(), get_task_complexity()
    """
    def __init__(self):
        from judgment import check10d, route, format_report, format_structured
        from judgment import detect_task_types, get_task_complexity
        from judgment import get_low_confidence_dimensions, metacognitive_review
        self._check10d = check10d
        self._route = route
        self._format_report = format_report
        self._format_structured = format_structured
        self._detect = detect_task_types
        self._complexity = get_task_complexity
        self._low_conf = get_low_confidence_dimensions
        self._meta = metacognitive_review

    def check10d(self, input_text: str, agent_profile: str = None, complexity: str = "auto") -> Dict[str, Any]:
        """十维判断决策。"""
        return self._check10d(input_text, agent_profile=agent_profile, complexity=complexity)

    def route(self, input_text: str) -> str:
        """路径路由（P/A/B/C）。"""
        return self._route(input_text)

    def format_report(self, result: dict) -> str:
        """格式化判断报告。"""
        return self._format_report(result)

    def format_structured(self, result: dict) -> Dict[str, Any]:
        """结构化输出。"""
        return self._format_structured(result)

    def detect_task_types(self, input_text: str) -> List[str]:
        """检测任务类型。"""
        return self._detect(input_text)

    def get_complexity(self, input_text: str) -> str:
        """获取任务复杂度。"""
        return self._complexity(input_text)

    def low_confidence_dims(self, result: dict) -> List[str]:
        """获取低置信度维度。"""
        return self._low_conf(result)

    def metacognitive_review(self, result: dict) -> str:
        """元认知复盘。"""
        return self._meta(result)


class CuriositySystem:
    """
    封装 curiosity 模块。
    
    真实 API: CuriosityEngine, trigger_from_low_confidence(),
              trigger_from_causal_mismatch(), full_report()
    """
    def __init__(self):
        from curiosity import curiosity_engine, CuriosityEngine
        from curiosity import trigger_from_low_confidence, trigger_from_causal_mismatch
        from curiosity import full_report, get_top_open, get_daily_list
        self._engine = curiosity_engine
        self._trigger_low = trigger_from_low_confidence
        self._trigger_causal = trigger_from_causal_mismatch
        self._full_report = full_report
        self._top_open = get_top_open
        self._daily = get_daily_list

    def trigger_from_low_confidence(self, judgment_result: dict) -> Optional[dict]:
        """根据判断结果低置信度触发好奇心探索。"""
        return self._trigger_low(judgment_result)

    def trigger_from_causal_mismatch(self, judgment_result: dict, causal_memory: dict) -> Optional[dict]:
        """根据因果记忆不匹配触发好奇心探索。"""
        return self._trigger_causal(judgment_result, causal_memory)

    def full_report(self) -> str:
        """生成完整好奇心报告。"""
        return self._full_report()

    def top_open_questions(self, limit: int = 5) -> List[str]:
        """获取未解决的好奇心问题。"""
        return self._top_open(limit)

    def daily_trigger_count(self) -> int:
        """今日触发次数。"""
        return len(self._daily())


class CausalMemorySystem:
    """
    封装 causal_memory 模块。
    
    真实 API: causal_memory.log_causal_event(), recall_causal_history(),
              infer_daily_causal_chains()
    """
    def __init__(self, data_dir: Path = DATA_DIR):
        from causal_memory import causal_memory as _cm
        from causal_memory import CausalEvent, CausalLink
        self._cm = _cm
        self._CausalEvent = CausalEvent
        self._CausalLink = CausalLink
        self._cm.init()  # 使用模块级文件路径初始化

    def log(self, event_type: str, description: str,
            causes: list = None, effects: list = None,
            tags: list = None) -> dict:
        """记录因果事件。"""
        return self._cm.log_causal_event(event_type, description, causes, effects, tags)

    def recall(self, query: str, limit: int = 5) -> List[dict]:
        """召回因果记忆。"""
        return self._cm.recall_causal_history(query, limit)

    def infer_chains(self) -> List[dict]:
        """推断因果链。"""
        return self._cm.infer_daily_causal_chains()

    def find_similar(self, description: str) -> List[dict]:
        """查找相似事件。"""
        return self._cm.find_similar_events(description)

    def add_link(self, cause_id: str, effect_id: str,
                 relation: str, quality: str = "inferred") -> dict:
        """添加因果链接。"""
        return self._cm.add_causal_link(cause_id, effect_id, relation, quality)

    @property
    def causal_memory(self):
        return self._cm


class OutputSystem:
    """
    封装 output_system 模块。
    
    真实 API: ConversationFormatter, Priority
    """
    def __init__(self):
        from output_system import ConversationFormatter, Priority
        self._fmt = ConversationFormatter()
        self._Priority = Priority

    def add(self, content: str, priority: int = 0) -> None:
        """添加一行输出。"""
        from output_system import FormattedLine
        self._fmt.add(FormattedLine(content=content, priority=priority))

    def format(self) -> List[str]:
        """格式化所有已添加的行（按优先级排序）。"""
        return self._fmt.format()

    def clear(self) -> None:
        """清除所有行。"""
        self._fmt.clear()

    @property
    def Priority(self):
        return self._Priority


class EmotionSystem:
    """
    封装 emotion_system 模块。
    
    真实 API: emotion_system.EmotionSystem
    """
    def __init__(self, data_dir: Path = MEMORY_FAST_DIR):
        from emotion_system import EmotionSystem as _ES
        self._sys = _ES()  # 模块级存储路径

    def track(self, role: str, content: str) -> dict:
        return self._sys.track(role, content)

    def get_last_emotion(self) -> dict:
        return self._sys.get_last_emotion()

    def adapt_reply(self, reply: str) -> str:
        return self._sys.adapt_reply(reply)

    def should_calm_down(self) -> bool:
        return self._sys.should_calm_down()


class FeedbackSystem:
    """
    封装 feedback_system 模块。
    
    真实 API: Feedback, add_feedback
    """
    def __init__(self, log_dir: Path = MEMORY_FAST_DIR):
        from feedback_system import Feedback, add_feedback
        self._Feedback = Feedback
        self._add = add_feedback

    def record(self, judgment_id: str, event_id: int, feedback_text: str,
              is_correct: bool = None, related_skill_id: str = None) -> dict:
        """记录一条反馈。"""
        return self._add(
            judgment_id=judgment_id,
            event_id=event_id,
            feedback_text=feedback_text,
            is_correct=is_correct,
            related_skill_id=related_skill_id,
        )

    def load_recent(self, limit: int = 50) -> List[dict]:
        from feedback_system import load_feedback_history
        return load_feedback_history(str(self._log_path), limit)


class ActionSignalSystem:
    """
    封装 action_signal 模块。
    
    真实 API: generate_action_signals(), format_for_robot(),
              ActionSignal, ActionSignalList
    """
    def __init__(self):
        from action_signal import (
            generate_action_signals,
            format_for_robot,
            ActionSignal,
            ActionSignalList,
        )
        self._gen = generate_action_signals
        self._fmt = format_for_robot
        self._Signal = ActionSignal
        self._SignalList = ActionSignalList

    def generate(self, action_plan, session_id: str = "default") -> list:
        """从 ActionPlan 生成行动信号列表。"""
        return self._gen(action_plan, session_id)

    def for_robot(self, signals) -> str:
        """将信号格式化为机器人输出。"""
        return self._fmt(signals)

    @property
    def ActionSignal(self):
        return self._Signal

    @property
    def ActionSignalList(self):
        return self._SignalList


# ─── 新增子系统 ─────────────────────────────────────────────────────────────

class RalphSystem:
    """
    封装 curiosity/ralph_loop.py — Ralph 自引用循环检测。

    Ralph Wiggum 风格：completion promise 驱动，达到目标才退出。
    """
    def __init__(self):
        from curiosity.ralph_loop import RalphLoop, RalphState
        self._RalphLoop = RalphLoop
        self._RalphState = RalphState

    def create(self, promise, max_iterations: int = 20, patience: int = 3):
        """
        创建 RalphLoop 实例。
        promise: Callable[[], bool] — 返回 True 表示完成
        """
        return self._RalphLoop(promise=promise, max_iterations=max_iterations, patience=patience)

    def detect_loop(self, iterations: list, threshold: int = 3) -> bool:
        """从迭代历史检测是否陷入死循环。"""
        consecutive = 0
        for item in reversed(iterations):
            if item.get("new_info", True):
                break
            consecutive += 1
        return consecutive >= threshold

    def report(self, loop) -> str:
        return loop.report()

    @property
    def RalphState(self):
        return self._RalphState


class CollisionSystem:
    """
    封装 openspace/collision_detector.py — Skill 触发条件碰撞检测。

    检测 INCLUDE（包含）和 OVERLAP（重叠）两种碰撞。
    """
    def __init__(self):
        # 直接导入文件，避免 openspace/__init__.py 的 transitive 依赖问题
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "collision_detector",
            str(Path(__file__).parent / "openspace" / "collision_detector.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._Detector = mod.SkillCollisionDetector
        self._Collision = mod.Collision

    def create(self):
        return self._Detector()

    def detect(self, detector, skills: dict) -> list:
        """批量检测碰撞。"""
        detector.add_skill_dict(skills)
        return detector.detect_all()

    def format_report(self, collisions: list) -> str:
        if not collisions:
            return "[OK] 无碰撞"
        lines = [f"[!] 发现 {len(collisions)} 个碰撞:"]
        for c in collisions:
            lines.append(f"  [{c.type}] {c.skill_a} <-> {c.skill_b}: {c.detail}")
            lines.append(f"    共享词: {', '.join(c.shared)}")
        return "\n".join(lines)


class SecuritySystem:
    """
    封装 action_system/security_hook.py — 10种危险模式检测。

    检测：代码执行 / 管道bash / 递归删除 / XSS / SQL注入 / 反序列化等。
    """
    def __init__(self):
        from action_system.security_hook import SecurityHook, SecurityLevel
        self._Hook = SecurityHook
        self._Level = SecurityLevel

    def check(self, code: str) -> list:
        """检查代码危险模式。"""
        return self._Hook().check_code(code)

    def level_name(self, level: int) -> str:
        return self._Level.name(level)

    @property
    def SAFE(self) -> int: return self._Level.SAFE
    @property
    def LOW(self) -> int: return self._Level.LOW
    @property
    def MEDIUM(self) -> int: return self._Level.MEDIUM
    @property
    def HIGH(self) -> int: return self._Level.HIGH
    @property
    def CRITICAL(self) -> int: return self._Level.CRITICAL

    def format_findings(self, findings: list) -> str:
        """格式化检查结果。"""
        if not findings:
            return "[SAFE] 无危险模式"
        lines = [f"[!] 发现 {len(findings)} 个问题:"]
        for f in findings:
            lines.append(f"  [{f.level_name}] {f.name} (L{f.line_number})")
            lines.append(f"    -> {f.detail}")
        return "\n".join(lines)


class BenchmarkSystem:
    """
    封装 evolutions/benchmark.py — GDPVal Benchmark 效果衡量。

    衡量 Skill 进化带来的实际收益：Token 节省率 / 完成率变化 / 速度变化。
    """
    def __init__(self):
        from evolutions.benchmark import (
            BenchmarkResult, PhaseResult, BaseRunner, SimulatedRunner,
        )
        self._BenchmarkResult = BenchmarkResult
        self._PhaseResult = PhaseResult
        self._BaseRunner = BaseRunner
        self._SimulatedRunner = SimulatedRunner

    def create_benchmark(self, task_set_name: str, p1: dict, p2: dict):
        return self._BenchmarkResult(
            task_set_name=task_set_name,
            p1=self._PhaseResult(**p1),
            p2=self._PhaseResult(**p2),
        )

    @property
    def BaseRunner(self): return self._BaseRunner
    @property
    def SimulatedRunner(self): return self._SimulatedRunner


class ObserveSystem:
    """
    封装 feedback_system/observe_hook.py — 5层被动工具调用捕获。

    100% 工具调用捕获，不漏，不主动分析。
    5层自防：防止 observe_hook 自己observe自己。
    """
    def __init__(self):
        from feedback_system.observe_hook import ObserveHook, should_observe, ToolObservation
        self._Hook = ObserveHook
        self._should_observe = should_observe
        self._Observation = ToolObservation

    def create(self):
        return self._Hook()

    def should_observe(self, event: dict) -> bool:
        return self._should_observe(event)

    def on_tool_call(self, hook, tool: str, args: dict, result: str = "ok",
                     error: str = None, duration_ms: int = None) -> None:
        hook.on_tool_call(tool, args, result=result, error=error, duration_ms=duration_ms)

    def flush(self, hook) -> None:
        hook.flush()


class DiffTrackerSystem:
    """
    封装 causal_memory/diff_tracker.py — TurnDiffTracker 决策影响追踪。

    追踪每个决策（turn）→ 触发了哪些文件变更 → 因果推断。
    """
    def __init__(self):
        from causal_memory.diff_tracker import TurnDiffTracker, TurnDiff, FileChange
        self._Tracker = TurnDiffTracker
        self._TurnDiff = TurnDiff
        self._FileChange = FileChange

    def create(self, storage_path=None):
        from pathlib import Path
        return self._Tracker(storage_path=storage_path)

    def begin_turn(self, tracker, turn_id: str, decision_summary: str = "") -> None:
        tracker.begin_turn(turn_id, decision_summary)

    def log_change(self, tracker, tool: str, args: dict, before_hash: str = None,
                   after_hash: str = None) -> None:
        tracker.on_tool_call(tool, args, before_hash=before_hash, after_hash=after_hash)

    def save(self, tracker) -> None:
        tracker.save()


class SelfEvolverSystem:
    """
    封装 evolver/self_evolver.py — Self-Evolver 自动闭环。

    4 Phase：收集 → 分析 → 进化 → 输出。
    定时运行，从实际任务中学习。
    """
    def __init__(self):
        from evolver.self_evolver import SelfEvolver, DecisionRecord, EvolutionResult
        self._SelfEvolver = SelfEvolver
        self._DecisionRecord = DecisionRecord
        self._EvolutionResult = EvolutionResult

    def create(self) -> Any:
        return self._SelfEvolver()

    def run_cycle(self, evo=None) -> Any:
        if evo is None:
            evo = self._SelfEvolver()
        return evo.run_full_cycle()

    def cron_cycle(self, evo=None) -> str:
        if evo is None:
            evo = self._SelfEvolver()
        return evo.run_cron_cycle()

    def collect_decisions(self, limit: int = 50) -> list:
        evo = self._SelfEvolver()
        return evo.collect_recent_decisions(limit=limit)

    def summarize(self, evo=None) -> str:
        if evo is None:
            evo = self._SelfEvolver()
        return evo.summarize()


class SQLiteSystem:
    """
    封装 evolver/sqlite_schema.py — SQLite 数据分层。

    三张表：lessons / snapshots / health_metrics。
    WAL 模式，支持 crash recovery。
    """
    def __init__(self):
        from evolver.sqlite_schema import init_db, get_db, DB_FILE
        self._init_db = init_db
        self._get_db = get_db
        self._db_file = DB_FILE

    def init(self):
        """初始化数据库（创建表）。"""
        return self._init_db(str(self._db_file))

    def query(self, sql: str, params: tuple = ()) -> list:
        """执行查询，返回所有行。"""
        with self._get_db(str(self._db_file)) as conn:
            cur = conn.execute(sql, params)
            return cur.fetchall()

    def execute(self, sql: str, params: tuple = ()) -> None:
        """执行 DML（INSERT/UPDATE/DELETE）。"""
        with self._get_db(str(self._db_file)) as conn:
            conn.execute(sql, params)

    @property
    def db_file(self) -> Path:
        return self._db_file

    def summary(self) -> str:
        """各表行数摘要。"""
        lines = [f"SQLite DB: {self._db_file}"]
        with self._get_db(str(self._db_file)) as conn:
            for table in ["lessons", "snapshots", "health_metrics"]:
                try:
                    cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    lines.append(f"  {table}: {count} 条")
                except sqlite3.OperationalError:
                    lines.append(f"  {table}: (不存在)")
        return "\n".join(lines)


# ─── Juhuo Hub ───────────────────────────────────────────────────────────────

class Juhuo:
    """
    Juhuo 统一入口。
    
    所有子系统通过一个实例访问，延迟加载，按需初始化。
    
    示例：
        hub = Juhuo()
        
        # 十维判断
        result = hub.judgment.check10d("用户想要一个Flutter App")
        
        # 好奇心检测
        triggered = hub.curiosity.trigger_from_low_confidence(result)
        
        # 格式化输出
        formatted = hub.output.format_report(result)
        
        # 快捷函数
        think("安装npm包")
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        lazy: bool = True,
    ):
        self._data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._lazy = lazy

        self._judgment:    Optional[JudgmentSystem]      = None
        self._curiosity:   Optional[CuriositySystem]     = None
        self._causal:      Optional[CausalMemorySystem]  = None
        self._output:      Optional[OutputSystem]         = None
        self._emotion:     Optional[EmotionSystem]        = None
        self._feedback:    Optional[FeedbackSystem]        = None
        self._action_signal: Optional[ActionSignalSystem] = None
        self._ralph:       Optional[RalphSystem]         = None
        self._collision:   Optional[CollisionSystem]    = None
        self._security:    Optional[SecuritySystem]      = None
        self._benchmark:   Optional[BenchmarkSystem]     = None
        self._observe:     Optional[ObserveSystem]       = None
        self._diff_tracker: Optional[DiffTrackerSystem]   = None
        self._self_evolver: Optional[SelfEvolverSystem] = None
        self._sqlite:        Optional[SQLiteSystem]       = None

    # ── 属性访问（懒加载）─────────────────────────────────────────────────

    @property
    def judgment(self) -> JudgmentSystem:
        if self._judgment is None:
            self._judgment = JudgmentSystem()
        return self._judgment

    @property
    def curiosity(self) -> CuriositySystem:
        if self._curiosity is None:
            self._curiosity = CuriositySystem()
        return self._curiosity

    @property
    def causal(self) -> CausalMemorySystem:
        if self._causal is None:
            self._causal = CausalMemorySystem(self._data_dir)
        return self._causal

    @property
    def output(self) -> OutputSystem:
        if self._output is None:
            self._output = OutputSystem()
        return self._output

    @property
    def emotion(self) -> EmotionSystem:
        if self._emotion is None:
            self._emotion = EmotionSystem(self._data_dir / "memory" / "fast")
        return self._emotion

    @property
    def feedback(self) -> FeedbackSystem:
        if self._feedback is None:
            self._feedback = FeedbackSystem(self._data_dir / "memory" / "fast")
        return self._feedback

    @property
    def action_signal(self) -> ActionSignalSystem:
        if self._action_signal is None:
            self._action_signal = ActionSignalSystem()
        return self._action_signal

    @property
    def ralph(self) -> RalphSystem:
        if self._ralph is None:
            self._ralph = RalphSystem()
        return self._ralph

    @property
    def collision(self) -> CollisionSystem:
        if self._collision is None:
            self._collision = CollisionSystem()
        return self._collision

    @property
    def security(self) -> SecuritySystem:
        if self._security is None:
            self._security = SecuritySystem()
        return self._security

    @property
    def benchmark(self) -> BenchmarkSystem:
        if self._benchmark is None:
            self._benchmark = BenchmarkSystem()
        return self._benchmark

    @property
    def observe(self) -> ObserveSystem:
        if self._observe is None:
            self._observe = ObserveSystem()
        return self._observe

    @property
    def diff_tracker(self) -> DiffTrackerSystem:
        if self._diff_tracker is None:
            self._diff_tracker = DiffTrackerSystem()
        return self._diff_tracker

    @property
    def evolver(self) -> SelfEvolverSystem:
        if self._self_evolver is None:
            self._self_evolver = SelfEvolverSystem()
        return self._self_evolver

    @property
    def sqlite(self) -> SQLiteSystem:
        if self._sqlite is None:
            self._sqlite = SQLiteSystem()
        return self._sqlite

    # ── 快捷方法 ──────────────────────────────────────────────────────────

    def think(self, input_text: str) -> dict:
        """
        完整思考流程：判断 → 好奇心检测 → 元认知复盘。
        """
        result = self.judgment.check10d(input_text)

        # 好奇心检测
        triggered = self.curiosity.trigger_from_low_confidence(result)
        result["_curiosity_triggered"] = triggered

        return result

    # ── 数据路径属性 ───────────────────────────────────────────────────────

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    @property
    def memory_fast_dir(self) -> Path:
        return self._data_dir / "memory" / "fast"

    @property
    def memory_slow_dir(self) -> Path:
        return self._data_dir / "memory" / "slow"

    @property
    def evolutions_dir(self) -> Path:
        return self._data_dir / "evolutions"

    @property
    def metrics_dir(self) -> Path:
        return self._data_dir / "metrics"

    @property
    def checkpoints_dir(self) -> Path:
        return self._data_dir / "checkpoints"


# ─── 快捷函数 ────────────────────────────────────────────────────────────────

_hub_instance: Optional[Juhuo] = None


def get_hub(lazy: bool = True) -> Juhuo:
    """全局单例 Hub。"""
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = Juhuo(lazy=lazy)
    return _hub_instance


def think(input_text: str) -> dict:
    """快捷函数：判断 + 好奇心检测。"""
    return get_hub().think(input_text)


def check10d(input_text: str, profile: str = None) -> dict:
    """快捷函数：十维判断。"""
    return get_hub().judgment.check10d(input_text, profile=profile)
