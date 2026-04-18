#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
causal_memory.py — 聚活因果记忆模块
**独特技术设计（聚活独有）：**

1. **快慢双流架构**
   - 快路径：每次判断完成 → 即时写入因果事件节点
   - 慢路径：每日一次批量扫描 → 自动推断跨事件因果链
   - 快负责记录，慢负责推理，符合人类记忆形成规律

2. **时间衰减置信度**
   - 越老的记忆，置信度缓慢衰减 → 符合人类遗忘规律
   - 衰减公式：`confidence *= exp(-days / 365)` → 一年衰减一半
   - 经常被访问的记忆不衰减（复习强化）

3. **个人因果优先级**
   - 你的个人因果链接权重 = 通用知识 × 1.5 → 优先相信你亲身经历
   - 哪怕这个因果在通用知识里是错的，只要它是你踩坑总结的，就优先用它
   - 这才是"你的"记忆，不是通用知识库

Reference:
- MAGMA Temporal Resonant Graph Memory + 顾庸x方案
- OpenSpace (HKUDS) 启发：三级进化模式 / 质量监控 / 级联更新
- 核心设计：这是**你的个人因果记忆**，不是通用知识图谱
"""

import json
import math
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import difflib

from .types import (
    CausalEvent,
    CausalLink,
    CausalLinkQuality,
    CausalRelation,
    EvolutionType,
    EvolutionSuggestion,
    CausalStats,
)

# P3改进：四道压缩叠加（借鉴Claude Code TS）
from .compressor import fast_compress, slow_compress, compress_for_context

# 集成自我模型更新（延迟导入，避免循环依赖）
# self_model → causal_memory → self_model 循环
# 用法：from causal_memory.causal_memory import update_from_feedback as _lazy_update
_update_from_feedback = None  # 延迟初始化

# 相似度阈值
SIMILARITY_THRESHOLD = 0.65
# 最大时间差（三个月内视为相关）
MAX_DAYS_DELTA = 90
# 时间衰减半衰期（天数）→ 这么多天衰减一半
DECAY_HALF_LIFE = 365
# 个人因果权重加成 → 亲身经历加成50%
PERSONAL_CAUSAL_BONUS = 0.5

# JSONL 备份路径（供导出/调试，不作主力存储）
_CAUSAL_DIR = Path(__file__).parent
CAUSAL_EVENTS_FILE = str(_CAUSAL_DIR / "causal_events.jsonl")
CAUSAL_LINKS_FILE  = str(_CAUSAL_DIR / "causal_links.jsonl")


def init():
    """初始化 SQLite 表（幂等）"""
    _init_db()


def _next_event_id() -> int:
    """获取下一个事件ID"""
    events = load_all_events()
    if not events:
        return 1
    return max(e["event_id"] for e in events) + 1


def _next_link_id() -> int:
    """获取下一个链接ID"""
    links = load_all_links()
    if not links:
        return 1
    return max(l.link_id for l in links) + 1


def _task_similarity(a: str, b: str) -> float:
    """计算两个任务描述的相似度"""
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def load_all_events() -> List[dict]:
    """从 SQLite 加载所有事件"""
    import sqlite3
    db_path = Path(__file__).parent.parent / "data" / "causal_memory" / "events.db"
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM events ORDER BY event_id DESC LIMIT 1000").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _db_path():
    return Path(__file__).parent.parent / "data" / "causal_memory" / "events.db"


def _init_db():
    """初始化 SQLite 表（幂等）+ 增量迁移旧 schema）"""
    import sqlite3
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS causal_links (
            link_id INTEGER PRIMARY KEY,
            from_event_id INTEGER,
            to_event_id INTEGER,
            relation TEXT,
            confidence REAL,
            timestamp TEXT,
            inferred INTEGER,
            evolution_type TEXT,
            parent_link_id INTEGER,
            quality_json TEXT
        )""")
        # 迁移旧 schema（缺少字段的表）
        for col, dtype in [("parent_link_id", "INTEGER"), ("quality_json", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE causal_links ADD COLUMN {col} {dtype}")
            except sqlite3.OperationalError:
                pass  # 列已存在
        conn.execute("CREATE INDEX IF NOT EXISTS ix_links_from ON causal_links(from_event_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_links_to ON causal_links(to_event_id)")
        conn.commit()
    finally:
        conn.close()


def _links_from_rows(rows: List) -> List[CausalLink]:
    """将 SQLite rows 转换为 CausalLink 对象"""
    links = []
    for r in rows:
        quality_data = json.loads(r["quality_json"]) if r["quality_json"] else {}
        quality = CausalLinkQuality(
            applied_count=quality_data.get("applied_count", 0),
            success_count=quality_data.get("success_count", 0),
            failed_count=quality_data.get("failed_count", 0),
            last_checked=quality_data.get("last_checked"),
            needs_revalidation=quality_data.get("needs_revalidation", False),
            dependent_link_ids=quality_data.get("dependent_link_ids", []),
        )
        links.append(CausalLink(
            link_id=r["link_id"],
            from_event_id=r["from_event_id"],
            to_event_id=r["to_event_id"],
            relation=r["relation"],
            confidence=r["confidence"],
            timestamp=r["timestamp"],
            inferred=bool(r["inferred"]),
            evolution_type=r["evolution_type"],
            parent_link_id=r["parent_link_id"],
            quality=quality,
        ))
    return links


def load_all_links() -> List[CausalLink]:
    """从 SQLite 加载所有因果链接"""
    _init_db()
    import sqlite3
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM causal_links ORDER BY link_id").fetchall()
        return _links_from_rows(rows)
    finally:
        conn.close()


def _save_link(link: CausalLink):
    """保存单条链接到 SQLite"""
    import sqlite3
    _init_db()
    conn = sqlite3.connect(str(_db_path()))
    try:
        quality_json = json.dumps({
            "applied_count": link.quality.applied_count,
            "success_count": link.quality.success_count,
            "failed_count": link.quality.failed_count,
            "last_checked": link.quality.last_checked,
            "needs_revalidation": link.quality.needs_revalidation,
            "dependent_link_ids": link.quality.dependent_link_ids,
        })
        conn.execute("""INSERT OR REPLACE INTO causal_links
            (link_id,from_event_id,to_event_id,relation,confidence,timestamp,inferred,evolution_type,parent_link_id,quality_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (link.link_id, link.from_event_id, link.to_event_id, link.relation,
             link.confidence, link.timestamp, int(link.inferred), link.evolution_type,
             link.parent_link_id, quality_json))
        conn.commit()
    finally:
        conn.close()


def _rewrite_links(links: List[CausalLink]):
    """全量重写 causal_links 表"""
    import sqlite3
    _init_db()
    conn = sqlite3.connect(str(_db_path()))
    try:
        conn.execute("DELETE FROM causal_links")
        for link in links:
            _save_link(link)
    finally:
        conn.close()


def record_event(
    event_type: str,
    description: str = None,
    what_happened: str = None,
    why_i_think_so: str = None,
    outcome: str = None,
    judgment_summary: dict = None,
    tags: List[str] = None,
    chain_id: str = None,
) -> int:
    """
    【闭环Step1 专用】judgment verdict 写入 causal_memory（SQLite后端）

    写入 {data}/causal_memory/events.db，字段满足 check_and_trigger_self_model_update 的查询条件。
    """
    import sqlite3
    db_path = Path(__file__).parent.parent / "data" / "causal_memory" / "events.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 确保表存在
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY,
            timestamp TEXT,
            category TEXT,
            description TEXT,
            task TEXT,
            why_i_think_so TEXT,
            outcome TEXT,
            dimensions TEXT,
            judgment_summary TEXT,
            tags TEXT,
            chain_id TEXT
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_events_task ON events(task)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_events_outcome ON events(outcome)")
        conn.commit()
    finally:
        conn.close()

    # 插入事件
    conn = sqlite3.connect(str(db_path))
    try:
        max_id = conn.execute("SELECT MAX(event_id) FROM events").fetchone()[0] or 0
        event_id = max_id + 1
        dims = judgment_summary.get("dims", []) if judgment_summary else []
        conn.execute("""INSERT INTO events
            (event_id,timestamp,category,description,task,why_i_think_so,outcome,dimensions,judgment_summary,tags,chain_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (event_id, datetime.now().isoformat(), event_type, description or "", what_happened or "",
             why_i_think_so or "", outcome, json.dumps(dims, ensure_ascii=False),
             json.dumps(judgment_summary or {}, ensure_ascii=False),
             json.dumps(tags or [], ensure_ascii=False), chain_id))
        conn.commit()
        return event_id
    finally:
        conn.close()


def _record_event_to_sqlite(event: dict):
    """log_causal_event 的 SQLite 后端（find_similar_events 可立即搜到）"""
    import sqlite3
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY,
            timestamp TEXT,
            category TEXT,
            description TEXT,
            task TEXT,
            why_i_think_so TEXT,
            outcome TEXT,
            dimensions TEXT,
            judgment_summary TEXT,
            tags TEXT,
            chain_id TEXT
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_events_task ON events(task)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_events_outcome ON events(outcome)")
        conn.commit()
    finally:
        conn.close()
    # 写入（upsert by event_id）
    dims = {
        "complexity": event.get("complexity"),
        "dimensions_checked": event.get("dimensions_checked"),
        "must_check": event.get("must_check", []),
        "important": event.get("important", []),
        "skipped": event.get("skipped", []),
        "agent_profile": event.get("agent_profile"),
        "decision": event.get("decision"),
    }
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""INSERT OR REPLACE INTO events
            (event_id,timestamp,category,description,task,why_i_think_so,outcome,dimensions,judgment_summary,tags,chain_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (event["event_id"], event["timestamp"], "judgment",
             event.get("feedback", ""), event["task"], "",
             json.dumps(event.get("outcome"), ensure_ascii=False),
             json.dumps(dims, ensure_ascii=False), "", "", None))
        conn.commit()
    finally:
        conn.close()


def log_causal_event(task: str, result: Dict, decision: str, feedback: Optional[str] = None, outcome: Optional[bool] = None) -> Dict:
    """
    快路径：记录一次判断作为因果事件
    - outcome: True=决策成功/正确, False=决策失败/错误
    """
    init()
    
    event = {
        "event_id": _next_event_id(),
        "timestamp": datetime.now().isoformat(),
        "task": task,
        "complexity": result.get("complexity"),
        "dimensions_checked": result.get("meta", {}).get("checked", 0),
        "must_check": result.get("must_check", []),
        "important": result.get("important", []),
        "skipped": result.get("skipped", []),
        "agent_profile": result.get("agent_profile", {}).get("name") if result.get("agent_profile") else None,
        "decision": decision,
        "feedback": feedback,
        "outcome": outcome,
    }

    # 主力写 SQLite（与 load_all_events / find_similar_events 共用同一存储）
    _record_event_to_sqlite(event)
    # JSONL 备份（不依赖，可选）
    try:
        with open(CAUSAL_EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # 立即搜索相似历史事件，如果找到就建立潜在因果链接
    similar_events = find_similar_events(task, max_results=3)
    for prev_event in similar_events:
        if prev_event["event_id"] != event["event_id"]:
            add_causal_link(
                from_event_id=prev_event["event_id"],
                to_event_id=event["event_id"],
                relation=CausalRelation.SIMILAR_TASK.value,
                confidence=_task_similarity(prev_event["task"], task),
                inferred=False,
            )

    # 更新自我模型
    if _update_from_feedback and feedback:
        _update_from_feedback(feedback)

    return event


def add_causal_link(
    from_event_id: int,
    to_event_id: int,
    relation: str,
    confidence: float,
    inferred: bool = False,
) -> CausalLink:
    """Add a new causal link"""
    init()
    link = CausalLink(
        link_id=_next_link_id(),
        from_event_id=from_event_id,
        to_event_id=to_event_id,
        relation=relation,
        confidence=confidence,
        timestamp=datetime.now().isoformat(),
        inferred=inferred,
        evolution_type=EvolutionType.CAPTURED.value,
        quality=CausalLinkQuality(),
    )

    _save_link(link)
    return link


def capture_causal_link(
    from_event_id: int,
    to_event_id: int,
    relation: str,
    confidence: float,
    inferred: bool = True,
) -> CausalLink:
    """Capture a new causal link (alias for add_causal_link, matches OpenSpace naming)"""
    return add_causal_link(from_event_id, to_event_id, relation, confidence, inferred)


def find_similar_events(task: str, max_results: int = 3) -> List[dict]:
    """Find similar events by task description"""
    events = load_all_events()
    if not events:
        return []
    
    scored = [
        (e, _task_similarity(task, e["task"]))
        for e in events
    ]
    scored = [(e, s) for e, s in scored if s >= SIMILARITY_THRESHOLD]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    return [e for e, s in scored[:max_results]]


def record_application_result(link_id: int, outcome: bool):
    """
    Record application result for quality metrics
    outcome: True=应用成功（预测正确/符合个人一致性）, False=失败
    """
    all_links = load_all_links()
    for link in all_links:
        if link.link_id == link_id:
            # 这次应用的结果就是事件的outcome
            link.quality.record_application(outcome)
            updated = True
            break

    if updated:
        _rewrite_links(all_links)


def mark_cascade_revalidation(link_id: int):
    """
    标记依赖此链接的所有上游链接需要重新验证
    借鉴 OpenSpace 级联进化：基础链接改变 → 所有依赖它的都要重新验证
    """
    all_links = load_all_links()
    link = next((l for l in all_links if l.link_id == link_id), None)
    if not link:
        return

    # 遍历所有链接，找到依赖此链接的
    for other_link in all_links:
        if link.link_id in other_link.quality.dependent_link_ids:
            if not other_link.quality.needs_revalidation:
                other_link.quality.mark_needs_revalidation()

    # 也标记当前链接
    link.quality.mark_needs_revalidation()

    _rewrite_links(all_links)


def fix_causal_link(
    link_id: int,
    new_confidence: Optional[float] = None,
    new_relation: Optional[str] = None,
) -> CausalLink:
    """
    FIX 模式：就地修正现有因果链接
    对应 OpenSpace FIX 进化模式
    """
    all_links = load_all_links()
    link = next((l for l in all_links if l.link_id == link_id), None)
    if not link:
        raise ValueError(f"Link {link_id} not found")

    # 聚活身份锁：核心知识不能自动修正
    # 这里因果记忆的核心知识就是你亲身经历的，不锁定（允许修正）
    # 锁定只在顶层身份价值观

    if new_confidence is not None:
        link.confidence = new_confidence
    if new_relation is not None:
        link.relation = new_relation

    link.evolution_type = EvolutionType.FIX.value
    link.quality.last_checked = datetime.now().isoformat()

    _rewrite_links(all_links)
    return link


def derive_causal_link(
    parent_link_id: int,
    from_event_id: int,
    to_event_id: int,
    relation: str,
    confidence: float,
) -> CausalLink:
    """
    DERIVED 模式：从父链接衍生特定场景版本
    对应 OpenSpace DERIVED 进化模式
    """
    all_links = load_all_links()
    parent = next((l for l in all_links if l.link_id == parent_link_id), None)
    if not parent:
        raise ValueError(f"Parent link {parent_link_id} not found")

    new_link = add_causal_link(
        from_event_id=from_event_id,
        to_event_id=to_event_id,
        relation=relation,
        confidence=confidence,
    )
    # 继承质量统计
    new_link.quality.dependent_link_ids = parent.quality.dependent_link_ids.copy()
    if parent_link_id not in new_link.quality.dependent_link_ids:
        new_link.quality.dependent_link_ids.append(parent_link_id)
    new_link.evolution_type = EvolutionType.DERIVED.value
    _save_link(new_link)  # 保存继承后的质量统计

    return new_link


def suggest_evolution() -> List[EvolutionSuggestion]:
    """
    扫描所有链接，建议需要进化的链接
    借鉴 OpenSpace 三种触发：低成功率/需要重新验证/依赖改变
    """
    all_links = load_all_links()
    suggestions = []

    for link in all_links:
        # 锁定的链接不建议进化（聚活身份锁）
        if hasattr(link.quality, 'is_locked') and link.quality.is_locked:
            continue

        # 触发条件1：需要重新验证（级联标记）
        if link.quality.needs_revalidation:
            suggestions.append(EvolutionSuggestion(
                link_id=link.link_id,
                evolution_type=EvolutionType.FIX,
                reason="标记为需要重新验证（级联更新）",
                current_confidence=link.confidence,
                depends_on_changed=True,
            ))
            continue

        # 触发条件2：应用次数 >= 3，成功率 < 0.5
        if link.quality.applied_count >= 3 and link.quality.success_rate < 0.5:
            suggestions.append(EvolutionSuggestion(
                link_id=link.link_id,
                evolution_type=EvolutionType.FIX,
                reason=f"低成功率 ({link.quality.success_rate:.1%}), {link.quality.failed_count}/{link.quality.applied_count} 次失败",
                current_confidence=link.confidence,
            ))

    return suggestions


def get_links_needing_revalidation() -> List[CausalLink]:
    """获取所有需要重新验证的链接"""
    all_links = load_all_links()
    return [l for l in all_links if l.quality.needs_revalidation]


def _apply_time_decay(confidence: float, last_used: str) -> float:
    """
    聚活独特技术：时间衰减置信度
    越老的记忆，置信度越低 → 符合人类遗忘规律
    衰减公式：confidence *= exp(-days / (2 * half_life))
    """
    if not last_used:
        return confidence
    try:
        last_dt = datetime.fromisoformat(last_used)
        days = (datetime.now() - last_dt).days
        decay = math.exp(-days / (2 * DECAY_HALF_LIFE))
        return confidence * decay
    except:
        return confidence


def _calculate_effective_confidence(link: CausalLink) -> float:
    """
    聚活独特技术：计算有效置信度
    - 应用时间衰减
    - 个人亲身经历加成 → 你的经验比通用知识重要
    """
    conf = link.confidence
    # 时间衰减
    conf = _apply_time_decay(conf, link.quality.last_used)
    # 个人因果加成（亲身经历不是推断出来的）
    if not link.inferred:
        conf *= (1 + PERSONAL_CAUSAL_BONUS)
    # 成功率调整
    if link.quality.applied_count > 0:
        conf *= link.quality.success_rate
    return min(conf, 1.0)


def recall_causal_history(task: str, max_events: int = 3) -> Dict:
    """
    聚活因果召回（独特技术：时间衰减+个人优先级）
    
    返回 {
        "similar_events": [...],  # 相似历史事件（按相似度排序）
        "causal_chains": [...],   # 指向这些事件的因果链接（按有效置信度排序）
        "closed_loop_chains": [...],  # 来自 closed_loop 的最新判断链（独立来源）
        "summary": str            # 自然语言总结给判断系统
    }
    
    数据源：
    - causal_memory 自己的事件存储（历史积累、因果链接）
    - closed_loop.get_recent_chains()（最新判断闭环数据，两者打通）
    """
    # Debug
    if not isinstance(max_events, int):
        print(f"DEBUG: recall_causal_history: max_events is {type(max_events)} = {max_events}")
        max_events = 3
    
    # ── 数据源 1：closed_loop 的最新判断链（打通后的新数据源）───────────
    closed_loop_chains = []
    try:
        from judgment.closed_loop import get_recent_chains
        raw_chains = get_recent_chains(limit=max_events)
        for c in raw_chains:
            closed_loop_chains.append({
                "chain_id": c["chain_id"],
                "task": c["task"],
                "corrected": c["corrected"],
                "source": "closed_loop",
            })
    except Exception:
        pass  # closed_loop 不可用则跳过
    
    # ── 数据源 2：causal_memory 自己的事件存储 ─────────────────────────
    similar = find_similar_events(task, max_events)
    if not similar:
        parts = ["没有找到相似的历史事件，无法提供因果参考。"]
        if closed_loop_chains:
            parts.append("[Closed Loop 判断链]")
            for c in closed_loop_chains[:3]:
                parts.append(f"  [{'已验证' if c.get('corrected') else '待验证'}] {c['chain_id']}: {c.get('task', '')[:40]}")
        return {
            "similar_events": [],
            "causal_chains": [],
            "closed_loop_chains": closed_loop_chains,
            "summary": "\n".join(parts),
        }
    
    links = load_all_links()
    relevant_links = []
    event_ids = [e["event_id"] for e in similar]
    
    for link in links:
        if link.from_event_id in event_ids or link.to_event_id in event_ids:
            # 计算有效置信度（聚活独特技术）
            link.effective_confidence = _calculate_effective_confidence(link)
            relevant_links.append(link)
    
    # 聚活独特排序：按有效置信度降序 → 个人高置信度因果排在前面
    relevant_links.sort(key=lambda l: getattr(l, 'effective_confidence', 0), reverse=True)
    
    # 生成自然语言总结
    summary_parts = []
    for i, event in enumerate(similar):
        outcome_str = ""
        if event.get("outcome") is True:
            outcome_str = "，上次决策正确"
        elif event.get("outcome") is False:
            outcome_str = "，上次决策错误"
        
        summary_parts.append(f"- 类似任务：{event['task'][:60]}{'...' if len(event['task'])>60 else ''}{outcome_str}")
        
        # 添加因果链接质量提示
        for link in relevant_links:
            if link.from_event_id == event["event_id"]:
                if link.quality.applied_count > 0:
                    summary_parts[-1] += f"（该模式成功率 {link.quality.success_rate:.1%}，{link.quality.applied_count} 次应用）"
                if link.quality.needs_revalidation:
                    summary_parts[-1] += " ⚠️ 需要重新验证"
    
    summary = "\n".join(summary_parts)
    
    return {
        "similar_events": similar,
        "causal_chains": [l.to_dict() for l in relevant_links],
        "closed_loop_chains": closed_loop_chains,
        "summary": summary,
    }


def infer_daily_causal_chains() -> int:
    """
    聚活独特技术：快慢双流 → 慢路径每日扫描推断跨事件因果链
    快路径只记录事件和直接链接，慢路径批量找潜在因果关系，自动补全图谱
    
    返回：新添加的链接数
    """
    init()
    events = load_all_events()
    if len(events) < 2:
        return 0
    
    new_links = 0

    # 按时间排序 → 因果有方向
    events.sort(key=lambda x: x["timestamp"])

    # 遍历所有事件对，找潜在因果关系
    # 时间复杂度 O(n²) 但n不大（每天几个事件）可以接受
    for i, e1 in enumerate(events):
        e1_time = datetime.fromisoformat(e1["timestamp"])
        # 只看时间在e1之后的事件
        for e2 in events[i+1:]:
            e2_time = datetime.fromisoformat(e2["timestamp"])
            delta_days = (e2_time - e1_time).days
            if delta_days > MAX_DAYS_DELTA:
                continue  # 太久远，不太可能直接影响
            
            # 任务相似度高 → 很可能有因果影响
            sim = _task_similarity(e1["task"], e2["task"])
            if sim >= SIMILARITY_THRESHOLD:
                # 检查链接是否已存在
                all_links = load_all_links()
                exists = any(
                    (l.from_event_id == e1["event_id"] and 
                     l.to_event_id == e2["event_id"]) 
                    for l in all_links
                )
                if not exists:
                    capture_causal_link(
                        from_event_id=e1["event_id"],
                        to_event_id=e2["event_id"],
                        relation=CausalRelation.INFLUENCES.value,
                        confidence=sim * 0.8,  # 推断置信度打八折
                        inferred=True,  # 慢路径推断标记
                    )
                    new_links += 1

    # 推断完了，统计低质量链接给进化建议
    return new_links


def get_stats() -> CausalStats:
    """获取因果记忆统计信息"""
    events = load_all_events()
    links = load_all_links()
    return CausalStats(
        total_events=len(events),
        total_links=len(links),
        inferred_links=sum(1 for l in links if l.inferred),
        personal_links=sum(1 for l in links if not l.inferred),
        avg_confidence=sum(l.confidence for l in links) / max(1, len(links)),
        low_quality_links=sum(1 for l in links if l.quality.applied_count >= 3 and l.quality.success_rate < 0.5),
    )


def get_statistics() -> CausalStats:
    """别名兼容 __init__.py 导出"""
    return get_stats()


def scan_low_quality_links() -> List[CausalLink]:
    """扫描低质量链接（对应 OpenSpace 指标监控）"""
    all_links = load_all_links()
    return [
        l for l in all_links
        if l.quality.applied_count >= 3 and l.quality.success_rate < 0.5
    ]


def update_link_quality_for_event(event_id: int, outcome: bool):
    """更新链接质量（事件结果）"""
    all_links = load_all_links()
    updated = False
    for link in all_links:
        if link.to_event_id == event_id or link.from_event_id == event_id:
            if hasattr(link.quality, 'record_application'):
                link.quality.record_application(outcome)
                updated = True
    
    if updated:
        for link in all_links:
            _save_link(link)  # 主力写 SQLite
        # JSONL 备份（不阻塞主流程）
        try:
            with open(CAUSAL_LINKS_FILE, "w", encoding="utf-8") as f:
                for link in all_links:
                    f.write(json.dumps(link.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass
    return updated


def inject_to_judgment_input(task: str) -> str:
    """
    聚活因果记忆注入到判断输入：
    返回自然语言总结，注入到 judgment 输入
    
    同时包含 causal_memory 历史积累和 closed_loop 最新判断链。
    
    P3改进：使用四道压缩叠加
    安全：使用 ContextFence 围栏包装，防止记忆被误当用户输入
    """
    recall_result = recall_causal_history(task, max_events=3)
    
    parts = []
    
    # 四道压缩：先压缩recall_result
    if recall_result.get("summary"):
        # 快流：snippet提取
        compressed = fast_compress(recall_result["summary"])
        parts.append(compressed.content)
    
    # 附加 closed_loop 最新链（使用micro压缩）
    cl_chains = recall_result.get("closed_loop_chains", [])
    if cl_chains:
        cl_lines = ["[Closed Loop 判断链]"]
        for c in cl_chains[:3]:
            status = "已验证" if c.get("corrected") else "待验证"
            # micro压缩
            chain_text = f"  [{status}] {c['chain_id']}: {c.get('task', '')[:50]}"
            compressed = fast_compress(chain_text)
            cl_lines.append(compressed.content)
        parts.append("\n".join(cl_lines))
    
    content = "\n\n".join(parts) if parts else ""
    
    # ── 安全：ContextFence 围栏包装 ──────────────────────────────
    if content:
        try:
            from judgment.context_fence import ContextFence
            fence = ContextFence()
            return fence.wrap(content, context_type="causal_memory")
        except Exception:
            pass  # fallback: 返回原文
    return content


def check_and_trigger_self_model_update(
    task: str,
    dimensions: List[str],
    correct: bool,
    pattern_key: str = None,
) -> dict:
    """
    【闭环Step2】causal_memory → self_model 触发器

    检查同类 verdict pattern（相同 dimensions + 相似 task 文本）
    是否累积达到阈值。达到阈值时触发 self_model.update_from_feedback，
    让自我模型学习"我在哪些情况下会判断错误/成功"。

    Args:
        task: 任务文本
        dimensions: 涉及的维度列表
        correct: 判定是否正确
        pattern_key: 可选，手动指定 pattern key

    Returns:
        {"triggered": bool, "count": int, "threshold": int, "result": ...}
    """
    import hashlib

    PATTERN_THRESHOLD = 2  # 同一 pattern 出现 2 次就触发

    events = load_all_events()
    dims_key = "|".join(sorted(dimensions)) if dimensions else "none"

    # 生成 pattern key
    if pattern_key is None:
        task_hash = hashlib.md5(task.encode("utf-8")).hexdigest()[:8]
        pattern_key = f"{dims_key}:{task_hash}"

    # 找同类 verdict 事件（相同 dimensions + 相似 task）
    similar_events = [
        e
        for e in events
        if e.get("category") == "judgment_verdict"
        and e.get("outcome") is not None
        and "|".join(sorted(e.get("dimensions", []))) == dims_key
        and _task_similarity(task, e.get("task", "")) >= SIMILARITY_THRESHOLD
    ]

    count = len(similar_events)

    if count >= PATTERN_THRESHOLD:
        # 提取错误维度（correct=False 时哪些维度出了问题）
        wrong_dims = [d for d in dimensions if d]

        # 构建反馈事件，送给 self_model
        feedback_event = {
            "source": "causal_memory_pattern_detector",
            "pattern_key": pattern_key,
            "feedback_type": (
                "judgment_repeated_mistake" if not correct else "judgment_repeated_success"
            ),
            "task_sample": task[:200],
            "dimensions": dimensions,
            "wrong_dimensions": wrong_dims if not correct else [],
            "correct": correct,
            "occurrence_count": count,
            "similar_events_summary": [
                {
                    "event_id": e.get("event_id"),
                    "outcome": e.get("outcome"),
                    "task": e.get("task", "")[:80],
                }
                for e in similar_events[-5:]  # 最近 5 条
            ],
        }

        # 延迟导入 self_model（避免循环依赖）
        global _update_from_feedback
        if _update_from_feedback is None:
            try:
                from self_model.self_model import update_from_feedback as _uf
                _update_from_feedback = _uf
            except Exception:
                _update_from_feedback = False

        if _update_from_feedback:
            try:
                result = _update_from_feedback(feedback_event)
                return {
                    "triggered": True,
                    "count": count,
                    "threshold": PATTERN_THRESHOLD,
                    "pattern_key": pattern_key,
                    "result": result,
                }
            except Exception as e:
                return {
                    "triggered": False,
                    "count": count,
                    "threshold": PATTERN_THRESHOLD,
                    "pattern_key": pattern_key,
                    "error": str(e),
                }
        else:
            return {
                "triggered": False,
                "count": count,
                "threshold": PATTERN_THRESHOLD,
                "pattern_key": pattern_key,
                "error": "update_from_feedback not available",
            }

    return {
        "triggered": False,
        "count": count,
        "threshold": PATTERN_THRESHOLD,
        "pattern_key": pattern_key,
    }