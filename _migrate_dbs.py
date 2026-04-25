"""
P0-1: Consolidate 3 DBs into 1 (data/juhuo.db)

State of play (before migration):
- judgment_db has: 36 judgments, 86 verdict_outcomes, 40 experiences (distinct from juhuo.db's 88)
- insights.db: FULLY REDUNDANT (insights table already in juhuo.db)
- juhuo.db: canonical, 1628KB, has evolution data + 88 experiences

Migration steps:
1. Backup all 3 DBs
2. Migrate experiences from judgment_db (that don't exist in juhuo.db by task_hash)
3. Migrate judgments from judgment_db -> juhuo.db (juhuo.db has 0)
4. Migrate verdict_outcomes from judgment_db -> juhuo.db (juhuo.db has 0)
5. Update seed_verdicts.py to use juhuo.db (no data loss)
6. Update insight_tracker.py to use juhuo.db (insights.db becomes orphaned)
7. Update judgment_db.py _DB path (cosmetic - get_conn() already delegates)
8. Delete insights.db
"""

import sqlite3, os, shutil, datetime
from pathlib import Path

SRC_MAIN = Path('E:/juhuo/data/juhuo.db')
SRC_JDG = Path('E:/juhuo/data/judgment_data/juhuo_judgment.db')
SRC_INS = Path('E:/juhuo/data/insights.db')
BACKUP_DIR = Path('E:/juhuo/data/_db_backup')
os.makedirs(BACKUP_DIR, exist_ok=True)

def backup(path, tag):
    if not path.exists():
        print(f"  SKIP (not found): {path}")
        return
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{tag}_{ts}.db"
    shutil.copy2(path, backup_path)
    sz = os.path.getsize(backup_path) // 1024
    print(f"  Backup: {backup_path} ({sz}KB)")

print("=== Step 0: Backup ===")
backup(SRC_MAIN, "juhuo")
backup(SRC_JDG, "judgment")
backup(SRC_INS, "insights")

conn_main = sqlite3.connect(str(SRC_MAIN))
conn_jdg = sqlite3.connect(str(SRC_JDG))

def rowcount(conn, table):
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except:
        return "ERR"

print("\n=== Step 1: Migrate experiences ===")
n_main = rowcount(conn_main, "experiences")
n_jdg = rowcount(conn_jdg, "experiences")
print(f"  Before: juhuo={n_main}, judgment_db={n_jdg}")

# Get existing task_hashes from main
main_hashes = {r[0] for r in conn_main.execute(
    "SELECT task_hash FROM experiences WHERE task_hash IS NOT NULL"
).fetchall()}
print(f"  Existing task_hashes in juhuo.db: {len(main_hashes)}")

# Check judgment_db experiences schema
j_cols = [r[1] for r in conn_jdg.execute("PRAGMA table_info(experiences)").fetchall()]
m_cols = [r[1] for r in conn_main.execute("PRAGMA table_info(experiences)").fetchall()]
print(f"  judgment_db experiences cols: {j_cols}")
print(f"  juhuo.db experiences cols: {len(m_cols)} cols")

# Add missing columns to main if needed
for col in ['action_channel', 'tool_calls', 'execution_result', 
            'perception_summary', 'behavior_id', 'source', 
            'task_embedding', 'chain_id', 'actual_action', 'updated_at']:
    if col not in m_cols:
        try:
            conn_main.execute(f"ALTER TABLE experiences ADD COLUMN {col}")
            print(f"  Added column: {col}")
        except:
            pass

# Insert new rows from judgment_db (only those with unique task_hash)
added_exp = 0
for row in conn_jdg.execute("SELECT * FROM experiences").fetchall():
    jdg_cols = [r[1] for r in conn_jdg.execute("PRAGMA table_info(experiences)").fetchall()]
    # Get task_hash (index varies by schema)
    task_hash_idx = jdg_cols.index('task_hash') if 'task_hash' in jdg_cols else None
    if task_hash_idx is None:
        continue
    task_hash = row[task_hash_idx]
    if task_hash and task_hash not in main_hashes:
        # Build insert with all columns from main
        vals = []
        for col in m_cols:
            if col == 'id':
                continue  # autoincrement
            if col in jdg_cols:
                vals.append(row[jdg_cols.index(col)])
            else:
                vals.append(None)
        try:
            placeholders = ','.join(['?' for _ in m_cols if _ != 'id'])
            cols = ','.join([c for c in m_cols if c != 'id'])
            conn_main.execute(
                f"INSERT INTO experiences ({cols}) VALUES ({placeholders})",
                vals
            )
            added_exp += 1
        except Exception as e:
            pass  # Skip duplicates or constraint errors

conn_main.commit()
n_main_after = rowcount(conn_main, "experiences")
print(f"  After: juhuo={n_main_after} (added {n_main_after - n_main})")

print("\n=== Step 2: Migrate judgments ===")
n_main = rowcount(conn_main, "judgments")
n_jdg = rowcount(conn_jdg, "judgments")
print(f"  Before: juhuo={n_main}, judgment_db={n_jdg}")

# Add missing user_id column
try:
    conn_main.execute("ALTER TABLE judgments ADD COLUMN user_id TEXT DEFAULT 'default'")
except:
    pass

# Migrate all from judgment_db
jdg_rows = conn_jdg.execute("SELECT * FROM judgments").fetchall()
j_cols = [r[1] for r in conn_jdg.execute("PRAGMA table_info(judgments)").fetchall()]
m_cols = [r[1] for r in conn_main.execute("PRAGMA table_info(judgments)").fetchall()]

added_jdg = 0
for row in jdg_rows:
    vals = []
    for col in m_cols:
        if col == 'id':
            continue
        if col in j_cols:
            vals.append(row[j_cols.index(col)])
        elif col == 'user_id':
            vals.append('default')
        else:
            vals.append(None)
    try:
        cols = ','.join([c for c in m_cols if c != 'id'])
        placeholders = ','.join(['?' for _ in cols.split(',')])
        conn_main.execute(f"INSERT OR IGNORE INTO judgments ({cols}) VALUES ({placeholders})", vals)
        added_jdg += 1
    except:
        pass

conn_main.commit()
n_main_after = rowcount(conn_main, "judgments")
print(f"  After: juhuo={n_main_after} (added {added_jdg})")

print("\n=== Step 3: Migrate verdict_outcomes ===")
n_main = rowcount(conn_main, "verdict_outcomes")
n_jdg = rowcount(conn_jdg, "verdict_outcomes")
print(f"  Before: juhuo={n_main}, judgment_db={n_jdg}")

# Add missing columns
for col in ['predicted_action', 'actual_action', 'outcome_score']:
    try:
        conn_main.execute(f"ALTER TABLE verdict_outcomes ADD COLUMN {col}")
    except:
        pass

jdg_rows = conn_jdg.execute("SELECT * FROM verdict_outcomes").fetchall()
j_cols = [r[1] for r in conn_jdg.execute("PRAGMA table_info(verdict_outcomes)").fetchall()]
m_cols = [r[1] for r in conn_main.execute("PRAGMA table_info(verdict_outcomes)").fetchall()]

added_vo = 0
for row in jdg_rows:
    vals = []
    for col in m_cols:
        if col == 'id':
            continue
        if col in j_cols:
            vals.append(row[j_cols.index(col)])
        else:
            vals.append(None)
    try:
        cols = ','.join([c for c in m_cols if c != 'id'])
        placeholders = ','.join(['?' for _ in cols.split(',')])
        conn_main.execute(f"INSERT OR IGNORE INTO verdict_outcomes ({cols}) VALUES ({placeholders})", vals)
        added_vo += 1
    except:
        pass

conn_main.commit()
n_main_after = rowcount(conn_main, "verdict_outcomes")
print(f"  After: juhuo={n_main_after} (added {added_vo})")

print("\n=== Step 4: Print final counts ===")
for t in ['experiences', 'judgments', 'verdict_outcomes', 'evolution_log', 'lessons', 'insights']:
    try:
        c = rowcount(conn_main, t)
        print(f"  {t}: {c}")
    except:
        print(f"  {t}: ERR")

conn_main.close()
conn_jdg.close()

print("\n=== Step 5: Update Python imports ===")

# Update seed_verdicts.py
f = 'E:/juhuo/judgment/seed_verdicts.py'
with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
    content = fh.read()
content = content.replace(
    'DB_PATH = DATA_DIR / "judgment_data" / "juhuo_judgment.db"',
    'DB_PATH = DATA_DIR / "juhuo.db"  # P0-1: consolidated into canonical DB'
)
with open(f, 'w', encoding='utf-8') as fh:
    fh.write(content)
print(f"  Updated: {f}")

# Update subsystems/judgment/insight_tracker.py
f = 'E:/juhuo/subsystems/judgment/insight_tracker.py'
with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
    content = fh.read()
content = content.replace(
    'DB_PATH = os.path.join(DATA_DIR, "insights.db")',
    'DB_PATH = os.path.join(DATA_DIR, "juhuo.db")  # P0-1: consolidated'
)
with open(f, 'w', encoding='utf-8') as fh:
    fh.write(content)
print(f"  Updated: {f}")

# Update subsystems/judgment/judgment_db.py (_DB path cosmetic)
f = 'E:/juhuo/subsystems/judgment/judgment_db.py'
with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
    content = fh.read()
content = content.replace(
    '_DB = _JD / "juhuo_judgment.db"',
    '_DB = _JD.parent / "juhuo.db"  # P0-1: canonical path'
)
with open(f, 'w', encoding='utf-8') as fh:
    fh.write(content)
print(f"  Updated: {f}")

print("\n=== Step 6: Delete redundant DBs ===")
if SRC_INS.exists():
    INS_BACKUP = BACKUP_DIR / f"insights_orphaned_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(SRC_INS, INS_BACKUP)
    os.remove(SRC_INS)
    print(f"  Deleted: {SRC_INS} (backup: {INS_BACKUP})")
else:
    print(f"  insights.db already gone")

# Keep judgment_db for now (it may still have other data we haven't checked)
# We'll delete it after verifying migration is complete
print(f"\n  NOTE: judgment_db KEPT for now - verify migration before deleting")
print(f"  Run: python -c \"import sqlite3; c=sqlite3.connect('E:/juhuo/data/juhuo.db'); print(c.execute('SELECT COUNT(*) FROM judgments').fetchone())\"")

print("\n=== DONE ===")
