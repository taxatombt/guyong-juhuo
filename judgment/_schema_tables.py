"""
judgment/_schema_tables.py — schema 定义和初始化

注意：不使用 _schema._get_db_conn()，因为 init_schema() 需要独立连接。
"""
import sqlite3
from pathlib import Path as _Path

_TABLE_DEFS = [
    ("dimension_beliefs",
     "dimension TEXT PRIMARY KEY, belief REAL DEFAULT 0.5, hit_count INTEGER DEFAULT 0, "
     "miss_count INTEGER DEFAULT 0, last_id TEXT, "
     "last_updated TEXT DEFAULT (datetime('now')), last_used TEXT"),
    ("judgment_snapshots",
     "id INTEGER, chain_id TEXT UNIQUE, ts REAL, task_hash TEXT, task_text TEXT, "
     "dimensions TEXT, weights TEXT, answers TEXT, confidence TEXT, complexity TEXT, "
     "emotion_label TEXT, causal_has_history INTEGER, outcome_auto REAL, corrected INTEGER, "
     "verdict TEXT, created_at TEXT DEFAULT (datetime('now')), PRIMARY KEY(id, chain_id)"),
    ("outcome_predictions",
     "id INTEGER, chain_id TEXT, predicted_action TEXT, predicted_consequence TEXT, "
     "expected_timeline TEXT, prediction_ts REAL, verified INTEGER, actual_action TEXT, "
     "actual_consequence TEXT, outcome_score REAL, verified_ts REAL, verifier TEXT, "
     "created_at TEXT DEFAULT (datetime('now')), PRIMARY KEY(id,chain_id)"),
    ("verdict_outcomes",
     "id INTEGER PRIMARY KEY, chain_id TEXT, task_text TEXT, correct INTEGER, "
     "notes TEXT, outcome_score REAL, created_at TEXT DEFAULT (datetime('now'))"),
    ("experiences",
     "id INTEGER PRIMARY KEY, user_id TEXT DEFAULT 'default', situation_type TEXT, "
     "task_hash TEXT, task_text TEXT, context TEXT, conclusion TEXT, confidence REAL, "
     "matched_keywords TEXT, outcome TEXT, outcome_notes TEXT, outcome_score REAL, "
     "verdict TEXT, created_at TEXT, action_channel TEXT, tool_calls TEXT, "
     "execution_result TEXT, perception_summary TEXT, behavior_id TEXT, "
     "source TEXT DEFAULT 'manual', "
     "task_embedding TEXT"),
    ("causal_chain",
     "id INTEGER PRIMARY KEY, chain_id TEXT, ts REAL, task_hash TEXT, task_text TEXT, "
     "dimensions TEXT, outcome REAL, corrected INTEGER, notes TEXT, created_at TEXT"),
    ("causal_events",
     "id INTEGER PRIMARY KEY, event_type TEXT, task_hash TEXT, task_text TEXT, "
     "situation_type TEXT, conclusion TEXT, outcome TEXT, outcome_score REAL, "
     "emotion_label TEXT, created_at TEXT, chain_id TEXT"),
    ("biographical_facts",
     "id INTEGER PRIMARY KEY, category TEXT, fact TEXT, importance INTEGER, "
     "source TEXT, tags TEXT, mentions INTEGER, last_seen TEXT, "
     "created_at TEXT, user_id TEXT DEFAULT 'default'"),
    ("dimension_stats",
     "id INTEGER PRIMARY KEY, dimension TEXT, correct_count INTEGER, "
     "total_count INTEGER, accuracy REAL, last_updated TEXT"),
    ("instinct_records",
     "id TEXT PRIMARY KEY, event_type TEXT, trigger TEXT, action TEXT, outcome TEXT, "
     "lesson TEXT, confidence REAL, use_count INTEGER, last_used TEXT, "
     "tags TEXT, created_at TEXT"),
    ("evolution_log",
     "id INTEGER PRIMARY KEY, chain_id TEXT, dimension TEXT, old_weight REAL, "
     "new_weight REAL, trigger TEXT, evidence TEXT, result TEXT, created_at TEXT"),
    ("evolution_records",
     "id INTEGER PRIMARY KEY, dimension TEXT, old_weight REAL, new_weight REAL, "
     "change_reason TEXT, evidence_count INTEGER, accuracy_delta REAL, "
     "created_at TEXT, verified INTEGER DEFAULT 0"),
    ("evolution_validation",
     "id INTEGER PRIMARY KEY, evolution_id TEXT, status TEXT, validated_at TEXT, "
     "validation_notes TEXT"),
    ("self_model",
     "id INTEGER PRIMARY KEY, dimension TEXT, current_weight REAL, "
     "confidence_score REAL, data_points INTEGER, trend TEXT, last_updated TEXT"),
    ("insights",
     "id INTEGER PRIMARY KEY, event_type TEXT, trigger TEXT, insight TEXT, "
     "importance REAL, tags TEXT, created_at TEXT, verified INTEGER DEFAULT 0"),
]


def _col_names(conn, table):
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    except:
        return []


def _rebuild_table(conn, table, new_def):
    """
    重建表：读旧数据 → 删表 → 按新schema建 → 按列名迁数据
    用于 verdict_outcomes（judgment_db 有18列旧版，data/juhuo.db 用6列新版）
    """
    old_cols = _col_names(conn, table)
    rows = []
    if old_cols:
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        except:
            rows = []
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(f"CREATE TABLE {table} ({new_def})")
    if not rows:
        conn.commit(); return
    new_cols = _col_names(conn, table)
    common = [c for c in new_cols if c in old_cols]
    if common:
        ph = ", ".join(["?"] * len(common))
        for row in rows:
            vals = [row[old_cols.index(c)] if c in old_cols else None for c in common]
            try:
                conn.execute(f"INSERT INTO {table} ({','.join(common)}) VALUES ({ph})", vals)
            except: pass
    conn.commit()


def init_schema(rebuild=True):
    """
    初始化 schema（幂等）。
    rebuild=True: verdict_outcomes 走 _rebuild_table（防止旧18列数据丢失）。
    使用独立连接，不影响调用者的线程本地连接。
    """
    db_path = _Path(__file__).parent.parent / "data" / "juhuo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        verdict_def = dict(_TABLE_DEFS)["verdict_outcomes"]
        _rebuild_table(conn, "verdict_outcomes", verdict_def)
        for table, defn in _TABLE_DEFS:
            if table == "verdict_outcomes":
                continue
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({defn})")
        conn.commit()
        n = len([r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()])
        print(f"[_schema] {n} tables in {db_path}")
    finally:
        conn.close()
