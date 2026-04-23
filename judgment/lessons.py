"""judgment/lessons.py — 因果链教训层

教训 = 从判断结果中提取的具体规则，不是权重数字。

教训单位：
  "遇到X情况时，倾向于Y错误 → 应该Z"

例子：
  - [warning] all in时倾向高估胜率 → all in前查历史同类决策胜率
  - [causal] 焦虑时低估黑天鹅风险 → 焦虑时强制问最坏情况能否承受
  - [pattern] 买房时只收集支持买的证据 → 主动收集下跌历史/持有成本

教训来源：
  - experience: 自己的判断结果验证（outcome_score 反馈）
  - education: 行为经济学研究（通用，非隐私）
  - observation: 观察他人决策（匿名化后）
  - suffering: 自己踩过的坑
  - bias: 认知偏差识别
"""

from __future__ import annotations
import sqlite3, json, hashlib
from pathlib import Path

# DB 路径（统一 data/juhuo.db）
_DATA_DIR = Path(__file__).parent.parent / "data"
_DB = str(_DATA_DIR / "juhuo.db")


# ─────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────
LESSONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_type TEXT NOT NULL,
    domain TEXT NOT NULL,
    pattern TEXT NOT NULL,
    root_cause TEXT,
    correction TEXT NOT NULL,
    positive_cases TEXT,
    negative_cases TEXT,
    hit_count INTEGER DEFAULT 0,
    miss_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.5,
    source TEXT DEFAULT 'experience',
    tags TEXT,
    verified INTEGER DEFAULT 0,
    instance_signature TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    user_id TEXT DEFAULT 'default'
);
CREATE INDEX IF NOT EXISTS idx_lessons_domain ON lessons(domain);
CREATE INDEX IF NOT EXISTS idx_lessons_type ON lessons(lesson_type);
CREATE INDEX IF NOT EXISTS idx_lessons_conf ON lessons(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_lessons_sig ON lessons(instance_signature);
"""


def init(db: str = _DB) -> int:
    """初始化 lessons 表，返回现有行数"""
    conn = sqlite3.connect(db)
    for s in LESSONS_SCHEMA.strip().split(";"):
        s = s.strip()
        if s:
            conn.execute(s)
    conn.commit()
    cnt = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
    conn.close()
    return cnt


# ─────────────────────────────────────────────────────────────────
# 种子教训（行为经济学研究，不是隐私）
# ─────────────────────────────────────────────────────────────────
SEED_LESSONS = [
    ("warning",    "investment",    "all in时倾向高估胜率",
                   "all in前查历史同类决策胜率，不只看成功案例"),
    ("causal",     "investment",    "焦虑时低估黑天鹅风险",
                   "焦虑状态下决策前强制问：如果最坏情况发生，我能承受吗"),
    ("pattern",    "investment",    "买房时只收集支持买的证据",
                   "买房前主动收集反对理由：下跌历史/持有成本/空置率"),
    ("antifragile", "investment",   "小仓位试错比全押更安全",
                   "不确定时先小仓位验证假设，等趋势确认再加仓"),
    ("warning",    "career",        "辞职时低估沉没成本和失败概率",
                   "辞职前计算：6个月无收入+失败概率+家庭财务承受阈值"),
    ("pattern",    "career",        "跳槽时只看到新机会，忽视旧积累",
                   "跳槽前列出在现公司未来1-2年可能的成长路径和资源"),
    ("causal",     "career",        "焦虑时高估新工作的吸引力",
                   "焦虑想跳槽时等7天冷静期再做最终决定"),
    ("pattern",    "relationship",  "情绪激动时做关系重大决策",
                   "重大关系决策等2周冷静期再决定，避免情绪化"),
    ("bias",       "universal",     "自我报告的偏好与实际行为不一致",
                   "判断说自己会做某事时，回顾过去类似承诺的兑现率"),
    ("bias",       "universal",     "近因效应：最近情绪强烈影响判断",
                   "重要决策等24小时让情绪消退后再评估"),
    ("bias",       "universal",     "事后聪明偏差：结果倒推决策质量",
                   "好结果≠好决策，坏结果≠坏决策，分析决策过程而非结果"),
]


def seed_defaults(uid: str = "default", db: str = _DB) -> tuple:
    """播种默认教训，已存在则跳过"""
    conn = sqlite3.connect(db)
    cnt = conn.execute(
        "SELECT COUNT(*) FROM lessons WHERE source='education'").fetchone()[0]
    conn.close()
    if cnt > 0:
        return cnt, "already_seeded"
    saved = 0
    for t, d, p, c in SEED_LESSONS:
        try:
            save_lesson(t, d, p, c, source="education", uid=uid, db=db)
            saved += 1
        except Exception:
            pass
    return saved, "seeded"


# ─────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────
def save_lesson(
    ltype: str,
    domain: str,
    pattern: str,
    correction: str,
    pos: list = None,
    neg: list = None,
    root: str = None,
    source: str = "experience",
    tags: list = None,
    uid: str = "default",
    db: str = _DB,
) -> int:
    """保存一条教训（去重签名 = MD5(ltype:domain:pattern[:50]))"""
    sig = hashlib.md5(
        f"{ltype}:{domain}:{pattern[:50]}".encode()
    ).hexdigest()[:12]
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO lessons
               (lesson_type,domain,pattern,root_cause,correction,
                positive_cases,negative_cases,source,tags,instance_signature,user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (ltype, domain, pattern, root, correction,
             json.dumps(pos or [], ensure_ascii=False),
             json.dumps(neg or [], ensure_ascii=False),
             source, json.dumps(tags or [], ensure_ascii=False),
             sig, uid),
        )
        conn.commit()
        lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return lid
    except Exception as e:
        conn.close()
        raise e


def update_confidence(lesson_id: int, hit: bool, db: str = _DB) -> None:
    """更新教训验证次数 + 重新计算置信度"""
    conn = sqlite3.connect(db)
    r = conn.execute(
        "SELECT hit_count,miss_count FROM lessons WHERE id=?", (lesson_id,)
    ).fetchone()
    if r:
        hc, mc = (r[0] or 0), (r[1] or 0)
        hc += 1 if hit else 0
        mc += 0 if hit else 1
        conf = hc / (hc + mc) if (hc + mc) > 0 else 0.5
        conn.execute(
            "UPDATE lessons SET hit_count=?,miss_count=?,confidence=? WHERE id=?",
            (hc, mc, round(conf, 3), lesson_id),
        )
        conn.commit()
    conn.close()


def get_lessons(
    domain: str = None,
    min_conf: float = 0.0,
    limit: int = 20,
    db: str = _DB,
) -> list:
    """获取教训列表（供注入 prompt）"""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM lessons WHERE confidence>=?"
    p = [min_conf]
    if domain:
        q += " AND domain=?"
        p.append(domain)
    q += " ORDER BY confidence DESC LIMIT ?"
    p.append(limit)
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def lessons_to_prompt(
    domain: str = None,
    min_conf: float = 0.3,
    limit: int = 8,
    db: str = _DB,
) -> str:
    """生成教训 prompt 文本（注入 LLM 判断上下文）"""
    ls = get_lessons(domain=domain, min_conf=min_conf, limit=limit, db=db)
    if not ls:
        return ""
    lines = ["\n【历史教训（避免重复犯错）】"]
    for l in ls:
        bar = "#" * int(l["confidence"] * 5) + "-" * (
            5 - int(l["confidence"] * 5)
        )
        lines.append(
            f"- [{l['lesson_type']}] {l['pattern']} → {l['correction']} [{bar}]"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# 任务领域分类（复用于 experiences._classify，保持一致）
# ─────────────────────────────────────────────────────────────────
_TASK_DOMAIN_KEYWORDS = {
    "investment":   ["买房", "投资", "理财", "炒股", "基金", "存款", "保险",
                     "股市", "全仓", "all in", "梭哈", "理财", "股票", "数字货币"],
    "career":       ["辞职", "跳槽", "创业", "工作", "offer", "裁员", "加薪",
                     "升职", "求职", "面试", "职业", "打工"],
    "relationship": ["分手", "复合", "追求", "约会", "恋爱", "暧昧", "前任",
                     "结婚", "相亲", "感情", "离婚"],
    "family":       ["孩子", "父母", "亲戚", "彩礼", "房产证", "亲子", "养娃"],
    "migration":    ["移民", "留学", "搬家", "换城市", "回老家", "出国", "定居"],
    "health":       ["健康", "体检", "手术", "抑郁", "焦虑", "减肥", "戒烟",
                     "失眠", "心理", "压力"],
    "education":    ["读研", "读博", "考证", "考公", "培训", "MBA", "学历", "学校"],
    "finance":      ["借钱", "贷款", "负债", "债务", "信用", "房贷", "借款"],
}


def classify_task_domain(task_text: str) -> str:
    """从任务文本分类领域，用于 lesson 检索"""
    task_lower = task_text.lower()
    scores = {}
    for domain, kws in _TASK_DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in task_lower)
        if score > 0:
            scores[domain] = score
    if not scores:
        return "universal"
    return max(scores, key=scores.get)


# ─────────────────────────────────────────────────────────────────
# 从判断结果自动提取教训（规则版；生产环境建议用 MiniMax LLM）
# ─────────────────────────────────────────────────────────────────
_AUTO_EXTRACT_RULES = [
    # (trigger_keywords, is_success_pattern, ltype, domain, pattern, correction)
    (
        ["all in", "全仓", "梭哈"],
        False,
        "warning", "investment",
        "all in/全仓时倾向高估胜率，低估全输后果",
        "all in前查历史同类决策胜率分布，强制问最坏情况能否承受"
    ),
    (
        ["all in", "全仓", "梭哈"],
        True,
        "antifragile", "investment",
        "all in后胜出，通常因为有信息优势或风险预案",
        "下次all in前，确认自己相比上次是否真有更多信息优势"
    ),
    (
        ["焦虑", "担心", "不安", "压力"],
        False,
        "causal", "investment",
        "焦虑状态下低估风险、高估收益",
        "焦虑时强制等待24小时，让杏仁核平息后再评估"
    ),
    (
        ["买房", "购房"],
        False,
        "pattern", "investment",
        "买房决策时倾向只收集支持买的理由",
        "买房前主动查：历史下跌幅度、租金回报率、持有成本"
    ),
    (
        ["辞职", "跳槽", "裸辞"],
        False,
        "warning", "career",
        "辞职决策时低估沉没成本、失败概率和适应期压力",
        "辞职前计算：6个月无收入+业务失败概率+家庭财务承受阈值"
    ),
    (
        ["辞职", "跳槽", "裸辞"],
        True,
        "antifragile", "career",
        "跳槽/辞职后胜出，通常因为有清晰的方向或财务缓冲",
        "下次跳槽前确认：目标方向和财务缓冲是否和这次一样扎实"
    ),
    (
        ["分手", "离婚"],
        False,
        "pattern", "relationship",
        "情绪激动时（愤怒/悲伤）做关系重大决策",
        "重大关系决策等2周冷静期，等情绪消退后再评估"
    ),
    (
        ["创业"],
        False,
        "warning", "career",
        "创业决策时低估1年内失败概率（约70%）",
        "创业前确认：家庭财务能承受多久没收入？退出机制是什么？"
    ),
    (
        ["创业"],
        True,
        "antifragile", "career",
        "创业胜出，通常因为执行力强或赛道选对了时机",
        "记录这次成功的关键因素（运气 or 实力），下次评估更客观"
    ),
    (
        ["借钱", "贷款", "负债"],
        False,
        "pattern", "finance",
        "借钱/贷款决策时低估还款压力和意外事件概率",
        "借款前计算真实月还款额，问自己：失业6个月还能还吗？"
    ),
]


def extract_and_save_from_case(
    task_text: str,
    verdict: str,
    predicted_action: str,
    actual_action: str,
    outcome_score: float,
    dimensions: list = None,
    chain_id: str = None,
    user_id: str = "default",
    db: str = _DB,
) -> list:
    """
    从一个判断案例自动提取教训并写入 DB。

    逻辑：
    - outcome_score >= 0.5 → 找 success_pattern 匹配的教训
    - outcome_score < 0.5 → 找 failure_pattern 匹配的教训
    - 教训写入 lessons 表（含 chain_id 用于溯源）
    - 返回写入的 lesson_ids
    """
    if outcome_score is None:
        return []
    if verdict is None:
        verdict = ""
    text = task_text + " " + verdict

    saved_ids = []
    is_success = outcome_score >= 0.5

    for (trigger_kws, success_flag, ltype, domain, pattern, correction
         ) in _AUTO_EXTRACT_RULES:
        if success_flag != is_success:
            continue
        if not any(kw.lower() in text.lower() for kw in trigger_kws):
            continue

        # 去重检查（signature 已在 save_lesson 里处理）
        pos = [chain_id] if chain_id else None
        try:
            lid = save_lesson(
                ltype=ltype,
                domain=domain,
                pattern=pattern,
                correction=correction,
                pos=pos,
                neg=None,
                source="experience",
                tags=[domain, ltype],
                uid=user_id,
                db=db,
            )
            saved_ids.append(lid)
        except Exception:
            # UNIQUE constraint → 已存在，跳过
            pass

    return saved_ids
