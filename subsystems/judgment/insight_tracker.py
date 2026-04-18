#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
insight_tracker.py — Token/成本/工具使用追踪
"""

from __future__ import annotations
import json, os, sqlite3, threading, time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

# ── 配置 ────────────────────────────────────────────────────────────
DATA_DIR = None
DB_PATH = None

def _init_paths():
    global DATA_DIR, DB_PATH
    if DATA_DIR is None:
        DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(DATA_DIR, exist_ok=True)
        DB_PATH = os.path.join(DATA_DIR, "insights.db")

# ── 常量 ────────────────────────────────────────────────────────────
class ET:
    INPUT_TOKEN = "INPUT_TOKEN"
    OUTPUT_TOKEN = "OUTPUT_TOKEN"
    COST_USD = "COST_USD"
    TOOL_CALL = "TOOL_CALL"
    ERROR = "ERROR"
    LATENCY_MS = "LATENCY_MS"
    VERDICT_CORRECT = "VERDICT_CORRECT"
    VERDICT_WRONG = "VERDICT_WRONG"

@dataclass
class Event:
    event_type: str
    value: float
    label: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

# ── 单例 ────────────────────────────────────────────────────────────
_insight = None
_lock = threading.Lock()

def insight_tracker() -> "InsightTracker":
    global _insight
    if _insight is None:
        with _lock:
            if _insight is None:
                _insight = InsightTracker()
    return _insight

class InsightTracker:
    def __new__(cls):
        if not hasattr(cls, "_instance") or cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        _init_paths()
        self._events: List[Event] = []
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_start = time.time()
        self._tool_counts: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._dims_accuracy: Dict[str, Dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
        self._verdict_count = 0
        self._verdict_correct = 0
        self._counter_lock = threading.Lock()
        self._total_input = 0
        self._total_output = 0
        self._total_cost = 0.0
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("CREATE TABLE IF NOT EXISTS insights (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, event_type TEXT, value REAL, label TEXT, timestamp TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS session_stats (session_id TEXT PRIMARY KEY, total_input_tokens INTEGER DEFAULT 0, total_output_tokens INTEGER DEFAULT 0, total_cost_usd REAL DEFAULT 0, total_tool_calls INTEGER DEFAULT 0, total_errors INTEGER DEFAULT 0, verdict_correct INTEGER DEFAULT 0, verdict_total INTEGER DEFAULT 0, accuracy REAL DEFAULT 0, started_at TEXT, updated_at TEXT)")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _save_event(self, event: Event):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute("INSERT INTO insights (session_id, event_type, value, label, timestamp) VALUES (?, ?, ?, ?, ?)", (self._session_id, event.event_type, event.value, event.label, event.timestamp.isoformat()))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _update_session_stats(self):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            accuracy = self._verdict_correct / self._verdict_count if self._verdict_count > 0 else 0
            conn.execute("INSERT OR REPLACE INTO session_stats (session_id, total_input_tokens, total_output_tokens, total_cost_usd, total_tool_calls, total_errors, verdict_correct, verdict_total, accuracy, started_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (self._session_id, self._total_input, self._total_output, self._total_cost, sum(self._tool_counts.values()), sum(self._error_counts.values()), self._verdict_correct, self._verdict_count, accuracy, datetime.fromtimestamp(self._session_start).isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def record_input(self, tokens: int, label: str = ""):
        with self._counter_lock:
            self._total_input += tokens
            self._events.append(Event(ET.INPUT_TOKEN, tokens, label))
            self._save_event(Event(ET.INPUT_TOKEN, tokens, label))

    def record_output(self, tokens: int, label: str = ""):
        with self._counter_lock:
            self._total_output += tokens
            self._events.append(Event(ET.OUTPUT_TOKEN, tokens, label))
            self._save_event(Event(ET.OUTPUT_TOKEN, tokens, label))

    def record_cost(self, cost_usd: float, label: str = ""):
        with self._counter_lock:
            self._total_cost += cost_usd
            self._save_event(Event(ET.COST_USD, cost_usd, label))

    def record_tool(self, tool_name: str, duration_ms: float = 0):
        with self._counter_lock:
            self._tool_counts[tool_name] += 1
            self._save_event(Event(ET.TOOL_CALL, 1, tool_name))
            if duration_ms > 0:
                self._save_event(Event(ET.LATENCY_MS, duration_ms, tool_name))

    def record_error(self, error_type: str):
        with self._counter_lock:
            self._error_counts[error_type] += 1
            self._save_event(Event(ET.ERROR, 1, error_type))

    def record_verdict(self, chain_id: str, correct: bool, dimensions: List[str] = None):
        with self._counter_lock:
            self._verdict_count += 1
            if correct:
                self._verdict_correct += 1
            event_type = ET.VERDICT_CORRECT if correct else ET.VERDICT_WRONG
            self._save_event(Event(event_type, 1, chain_id))
            if dimensions:
                for dim in dimensions:
                    self._dims_accuracy[dim]["total"] += 1
                    if correct:
                        self._dims_accuracy[dim]["correct"] += 1
            self._update_session_stats()

    def summary(self) -> dict:
        with self._counter_lock:
            accuracy = self._verdict_correct / self._verdict_count if self._verdict_count > 0 else 0
            dims_report = {}
            for dim, stats in self._dims_accuracy.items():
                acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                dims_report[dim] = {"correct": stats["correct"], "total": stats["total"], "accuracy": round(acc, 3)}
            return {
                "session_id": self._session_id,
                "total_input_tokens": self._total_input,
                "total_output_tokens": self._total_output,
                "total_tokens": self._total_input + self._total_output,
                "total_cost_usd": round(self._total_cost, 6),
                "tool_calls": dict(self._tool_counts),
                "errors": dict(self._error_counts),
                "verdict_correct": self._verdict_correct,
                "verdict_total": self._verdict_count,
                "accuracy": round(accuracy, 3),
                "dims_accuracy": dims_report,
                "session_duration_sec": round(time.time() - self._session_start, 1),
            }

    def __repr__(self):
        s = self.summary()
        return (f"InsightTracker(session={s['session_id']}, "
                f"tokens={s['total_tokens']}, cost=${s['total_cost_usd']:.4f}, "
                f"verdicts={s['verdict_correct']}/{s['verdict_total']} "
                f"({s['accuracy']:.1%}))")
