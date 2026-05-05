"""
judgment/_schema.py — P0-1 统一 DB 连接

所有 judgment 相关模块从这儿获取 DB 连接。
thread-local 连接（各线程独立），RLock 防死锁。
"""
import sqlite3, threading
from pathlib import Path

_lock = threading.RLock()
_DB_PATH = None  # 懒初始化

# Per-thread connection storage
_tlocal = threading.local()


def _make_conn():
    """创建一个新的 DB 连接（线程安全）"""
    global _DB_PATH
    with _lock:
        if _DB_PATH is None:
            _DB_PATH = Path(__file__).parent.parent / "data" / "juhuo.db"
            _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            print(f"[_schema] DB at {_DB_PATH}")
    conn = sqlite3.connect(str(_DB_PATH), timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _get_db_conn():
    """返回当前线程的 DB 连接（各线程独立，永不 close）。"""
    if not hasattr(_tlocal, 'conn') or _tlocal.conn is None:
        _tlocal.conn = _make_conn()
    return _tlocal.conn


class _DbConnCtx:
    """
    返回 connection 的 context-manager wrapper。
    __enter__ 返回连接；__exit__ 提交事务（不断连接）。
    模拟 sqlite3.Connection 原生 with 行为，同时保证连接不被关闭。
    """
    def __enter__(self):
        conn = _get_db_conn()
        return conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        conn = _get_db_conn()
        if exc_type is None:
            conn.commit()
        else:
            try:
                conn.rollback()
            except Exception:
                pass
        return False  # 不吞异常


def close_conn():
    """显式关闭当前线程的连接"""
    if hasattr(_tlocal, 'conn') and _tlocal.conn:
        try:
            _tlocal.conn.close()
        except:
            pass
        _tlocal.conn = None
