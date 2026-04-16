#!/usr/bin/env python3
"""检查数据库表结构"""
import sys
sys.path.insert(0, ".")

from judgment.judgment_db import get_conn

with get_conn() as c:
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables:", tables)
    
    for t in tables:
        schema = c.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{t}'").fetchone()
        if schema:
            print(f"\n{t}:\n{schema[0]}")
