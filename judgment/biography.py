# biography.py — 途径1：生平事实层（用户自述信息）
# 位置：judgment/biography.py（与 experiences.py 同目录）
# 数据：data/causal_memory/events.db
import json, re
from pathlib import Path
_DB_PATH = Path(__file__).parent.parent / "data" / "causal_memory" / "events.db"

def _age(m): return m.group(1) + "岁"
def _age_born(m): return m.group(1) + "年出生"
def _career_job(m): return m.group(1)
def _career_where(m): return "在" + m.group(1) + "工作"
def _career_type(m): return m.group(1)
def _family_status(m): return m.group(1)
def _family_child(m): return m.group(1) + "孩子"
def _family_partner(m): return "有伴侣"
def _fin_income(m): return m.group(1) + m.group(2)
def _fin_house(m): return m.group(1) + "房子"
def _fin_car(m): return m.group(1) + "车"
def _fin_savings(m): return m.group(1) + m.group(2)
def _loc_in(m): return "在" + m.group(1)
def _loc_city(m): return m.group(1) + "定居"
def _loc_hometown(m): return "老家在" + m.group(1)
def _health_poor(m): return "健康状况一般"
def _values_pers(m): return "性格" + m.group(2)
def _values_risk(m): return m.group(1)
def _values_pursue(m): return "追求" + m.group(1)
def _edu_deg(m): return m.group(1) + "学历"
def _edu_grad(m): return "毕业于" + m.group(1)

_BIO_PATTERNS = [
    ("age", r"(\d{2,3})\s*岁", _age),
    ("age", r"(\d{4})\s*年\s*生", _age_born),
    ("career", r"(程序员|产品经理|设计师|销售|市场|运营|HR|老师|医生|律师|公务员)", _career_job),
    ("career", r"在([\w公司]{2,10})(?:工作|上班|任职)", _career_where),
    ("career", r"(打工|自由职业|创业)", _career_type),
    ("family", r"(已婚|单身|离婚|二婚)", _family_status),
    ("family", r"(有|没有)孩子", _family_child),
    ("family", r"(老公|老婆|丈夫|妻子)", _family_partner),
    ("finance", r"(年薪|年收入|月收入)(?:大概|大约|大|约)(\d+万?)", _fin_income),
    ("finance", r"(有|没有)房子", _fin_house),
    ("finance", r"(有|没有)车", _fin_car),
    ("finance", r"(存款|积蓄)(?:大概|大约|大|约)(\d+万?)", _fin_savings),
    ("finance", r"(存款|积蓄)(\d+万)", _fin_savings),
    ("location", r"在([^，。,.]{2,6})(?:工作|生活|居住)", _loc_in),
    ("location", r"(北京|上海|深圳|广州|杭州|成都|武汉|南京|西安)", _loc_city),
    ("location", r"老家在([^，。,.]{2,6})", _loc_hometown),
    ("health", r"(身体|健康)不太好", _health_poor),
    ("values", r"性格(比较?|较)?(内向|外向|理性|感性|保守|激进)", _values_pers),
    ("values", r"(风险厌恶|风险偏好|保守型|激进型)", _values_risk),
    ("values", r"追求(自由|稳定|财富|成长)", _values_pursue),
    ("education", r"(本科|硕士|博士|大专|高中|初中)学历?", _edu_deg),
    ("education", r"毕业于([\u4e00-\u9fa5]{2,10})(?:大学|学院|学校|)", _edu_grad),
    ("education", r"毕业于?([^，。,.]{2,15})(?:大学|学校)", _edu_grad),
]
_CAT_DISPLAY = {"age":"年龄","career":"职业","family":"家庭","finance":"财务","location":"所在地","health":"健康","values":"性格/价值观","education":"学历"}
def _ensure_table():
    import sqlite3
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS biographical_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                fact TEXT NOT NULL,
                importance INTEGER DEFAULT 1,
                source TEXT DEFAULT 'user',
                tags TEXT,
                mentions INTEGER DEFAULT 1,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bio_cat ON biographical_facts(category)")
    finally:
        conn.close()

def extract_from_text(text: str) -> list:
    facts = []
    seen = set()
    for cat, regex, fn in _BIO_PATTERNS:
        for m in re.finditer(regex, text):
            d = fn(m)
            if d and (cat, d) not in seen:
                seen.add((cat, d))
                facts.append({"category": cat, "fact": d})
    return facts

def log(fact: str, category: str, importance: int = 1,
        source: str = "user", tags: list = None) -> int:
    _ensure_table()
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        n = conn.execute(
            "UPDATE biographical_facts SET mentions=mentions+1 "
            "WHERE category=? AND fact=?", (category, fact)).rowcount
        if n == 0:
            cur = conn.execute(
                "INSERT INTO biographical_facts (category,fact,importance,source,tags) "
                "VALUES (?,?,?,?,?)",
                (category, fact, importance, source,
                 json.dumps(tags or [], ensure_ascii=False)))
            conn.commit()
            return cur.lastrowid
        else:
            conn.commit()
            return -1
    finally:
        conn.close()

def log_batch(facts: list, source: str = "auto") -> int:
    added = 0
    for item in facts:
        r = log(item["fact"], item["category"], source=source)
        if r > 0:
            added += 1
    return added

def get_all() -> list:
    _ensure_table()
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT category,fact,importance,mentions,source "
            "FROM biographical_facts "
            "ORDER BY importance*mentions DESC").fetchall()]
    finally:
        conn.close()

def get_context(max_facts: int = 10) -> str:
    _ensure_table()
    import sqlite3
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT category,fact FROM biographical_facts "
            "ORDER BY importance*mentions DESC LIMIT ?",
            (max_facts,)).fetchall()
    finally:
        conn.close()
    if not rows:
        return ""
    lines = ["\n【用户背景】"]
    current_cat = None
    for r in rows:
        disp = _CAT_DISPLAY.get(r["category"], r["category"])
        if disp != current_cat:
            lines.append(f"  [{disp}]")
            current_cat = disp
        lines.append(f"    · {r['fact']}")
    return "\n".join(lines)

def format_profile() -> str:
    facts = get_all()
    if not facts:
        return "(暂无用户背景信息)"
    lines = ["=== 用户画像 ==="]
    by_cat = {}
    for f in facts:
        cat = _CAT_DISPLAY.get(f["category"], f["category"])
        by_cat.setdefault(cat, []).append(f)
    for cat, items in by_cat.items():
        lines.append(f"\n[{cat}]")
        for item in items:
            lines.append(f"  · {item['fact']} (来源:{item['source']}, 命中:{item['mentions']})")
    return "\n".join(lines)
