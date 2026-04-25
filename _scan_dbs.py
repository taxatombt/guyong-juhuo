import sqlite3

conn_main = sqlite3.connect('E:/juhuo/data/juhuo.db')
conn_jdg = sqlite3.connect('E:/juhuo/data/judgment_data/juhuo_judgment.db')

tables_both = [
    'judgments', 'experiences', 'evolution_log', 'evolution_validation',
    'session_stats', 'tool_executions', 'verdict_outcomes',
    'delegation_results', 'dimension_stats', 'fitness_records',
    'turn_sync', 'instinct_records'
]

print("=== Schema comparison for 'both' tables ===")
for t in tables_both:
    try:
        cur = conn_main.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{t}'")
        main_schema = cur.fetchone()
    except:
        main_schema = None
    try:
        cur = conn_jdg.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{t}'")
        jdg_schema = cur.fetchone()
    except:
        jdg_schema = None
    
    if main_schema and jdg_schema:
        same = "SAME" if main_schema[0] == jdg_schema[0] else "DIFF"
        if same == "DIFF":
            print(f"\n{'='*60}")
            print(f"{t}: {same}")
            print(f"MAIN schema:")
            print(main_schema[0])
            print(f"JUDGMENT schema:")
            print(jdg_schema[0])
    elif main_schema:
        print(f"{t}: ONLY in main")
    elif jdg_schema:
        print(f"{t}: ONLY in judgment")

print()
print("=== Record counts for 'both' tables ===")
for t in tables_both:
    try:
        c1 = conn_main.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    except:
        c1 = "ERR"
    try:
        c2 = conn_jdg.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    except:
        c2 = "ERR"
    if isinstance(c1, int) and isinstance(c2, int):
        status = "SAME" if c1 == c2 else f"DIFF(+{c2-c1})"
    else:
        status = "?"
    print(f"  {t}: main={c1}, judgment={c2} [{status}]")

print()
print("=== Record counts: judgment_db unique tables ===")
for t in ['judgment_records', 'verdict']:
    try:
        c = conn_jdg.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {c} records")
    except Exception as e:
        print(f"  {t}: ERR {e}")

conn_main.close()
conn_jdg.close()
