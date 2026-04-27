#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
perception/summary.py — 感知汇聚层

从所有感知来源（web/scraping/rss/email/experiences）汇聚信息，
生成结构化摘要，供 UnifiedProfile L3 使用。
TTL=7天，按 relevance×recency×priority 排序。

使用：
  from perception.summary import get_perception_summary, get_recent_topics
  summary = get_perception_summary(task_topic=None, limit=20)
"""

from __future__ import annotations
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import sqlite3, os

_DB = os.path.join(os.path.dirname(__file__), "..", "data", "juhuo.db")


@dataclass
class PerceptionEntry:
    source: str; topic: str; content: str
    url: str = ""; priority: int = 3
    recency: float = 1.0; relevance: float = 0.5
    created_at: Optional[str] = None

    def to_prompt_fragment(self) -> str:
        tag = f"[{self.source.upper()}]"
        if self.url: tag += f" {self.url[:60]}"
        rt = "新" if self.recency > 0.7 else ("旧" if self.recency < 0.3 else "")
        return f"{tag} {rt} {self.topic}: {self.content[:300]}"


@dataclass
class PerceptionSummary:
    task_topic: Optional[str]; entries: List[PerceptionEntry]
    total_count: int; sources: Dict[str, int]
    newest_age_hours: float; prompt_context: str = ""

    def to_prompt(self, max_chars: int = 2000) -> str:
        if not self.entries: return ""
        lines, by_src = ["【感知上下文】"], {}
        for e in self.entries: by_src.setdefault(e.source, []).append(e)
        for src, ents in by_src.items():
            lines.append(f"  [{src.upper()}] {len(ents)}条")
            for e in ents[:3]: lines.append(f"    - {e.topic}: {e.content[:200]}")
        result = "\n".join(lines)
        return result[:max_chars] + ("..." if len(result) > max_chars else "")


def _conn():
    c = sqlite3.connect(os.path.abspath(_DB), timeout=10)
    c.row_factory = sqlite3.Row; return c


def _recency(s: str, ttl: int = 7) -> float:
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        if hasattr(dt,"tzinfo") and dt.tzinfo: dt = dt.replace(tzinfo=None)
        return max(0.0, min(1.0, 1.0 - (datetime.now()-dt).total_seconds()/(ttl*86400)))
    except: return 0.5


def _rel(task: str, topic: str, content: str) -> float:
    if not task: return 0.5
    tw,low,high = set(task),set(topic),set(content)
    overlap = len(tw&low)+len(tw&high)*0.5
    return min(1.0, overlap/max(len(tw),1))


def _age_hours(s: str) -> float:
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        if hasattr(dt,"tzinfo") and dt.tzinfo: dt = dt.replace(tzinfo=None)
        return (datetime.now()-dt).total_seconds()/3600
    except: return 999999.0


def get_perception_summary(task_topic: Optional[str]=None, limit: int=20,
                           ttl_days: int=7, min_priority: int=0) -> PerceptionSummary:
    entries, sources, newest = [], {}, 999999.0
    cutoff = (datetime.now()-timedelta(days=ttl_days)).isoformat()

    # 1. perception_intents 表
    with _conn() as c:
        rows = c.execute("""
            SELECT source,topic,content,url,priority,created_at FROM perception_intents
            WHERE created_at>=? AND priority>=?
            ORDER BY priority DESC,created_at DESC LIMIT ?""",
            (cutoff,min_priority,limit)).fetchall()
        for r in rows:
            rec = _recency(r["created_at"],ttl_days)
            rel = _rel(task_topic or "",r["topic"],r["content"])
            e = PerceptionEntry(source=r["source"] or "web",topic=r["topic"] or "",
                content=r["content"] or "",url=r["url"] or "",
                priority=r["priority"] or 3,recency=rec,relevance=rel,
                created_at=r["created_at"])
            entries.append(e)
            sources[e.source]=sources.get(e.source,0)+1
            ah=_age_hours(r["created_at"])
            if ah<newest: newest=ah

    # 2. experiences.perception_summary
    if len(entries) < limit:
        with _conn() as c:
            rows2 = c.execute("""
                SELECT task_text,perception_summary,outcome_score,created_at FROM experiences
                WHERE perception_summary IS NOT NULL AND perception_summary!='' AND created_at>=?
                ORDER BY outcome_score DESC,created_at DESC LIMIT ?""",
                (cutoff, limit//3)).fetchall()
            for r in rows2:
                rec=_recency(r["created_at"],ttl_days)
                rel=_rel(task_topic or "",r["task_text"] or "",r["perception_summary"] or "")
                e = PerceptionEntry(source="experience",
                    topic=(r["task_text"] or "历史判断")[:100],
                    content=r["perception_summary"] or "",priority=3,
                    recency=rec,relevance=rel,created_at=r["created_at"])
                entries.append(e)
                sources["experience"]=sources.get("experience",0)+1

    # 3. 综合排序
    entries.sort(key=lambda x: x.relevance*0.5+x.recency*0.3+(x.priority/5.0)*0.2, reverse=True)
    entries=entries[:limit]

    prompt_ctx = PerceptionSummary(task_topic=task_topic,entries=entries,
        total_count=len(entries),sources=sources,
        newest_age_hours=newest,prompt_context="").to_prompt()

    return PerceptionSummary(task_topic=task_topic,entries=entries,
        total_count=len(entries),sources=sources,
        newest_age_hours=newest,prompt_context=prompt_ctx)


def get_recent_topics(limit: int=20, ttl_days: int=14) -> List[Dict[str,Any]]:
    cutoff = (datetime.now()-timedelta(days=ttl_days)).isoformat()
    with _conn() as c:
        rows = c.execute("""
            SELECT topic,source,priority,created_at FROM perception_intents
            WHERE created_at>=? ORDER BY created_at DESC LIMIT ?""",
            (cutoff,limit)).fetchall()
    result = []
    for r in rows:
        result.append({"topic":r["topic"],"source":r["source"],
            "priority":r["priority"],"created_at":r["created_at"],
            "age_days":round(_age_hours(r["created_at"])/24,1)})
    return result
