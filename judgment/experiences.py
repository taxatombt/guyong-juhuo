# experiences.py — 经历层：让每次判断成为可复用的记忆
"""
核心思想：
- 每次判断存为一个"经历"：情况类型 + 结论 + 上下文
- 新判断来 → 匹配最像的历史经历 → 给出判断时优先参考
- 结论 = 真实选择，不是分析

数据模型：
experiences 表：
  id, situation_type, context, conclusion, confidence,
  matched_keywords, outcome, outcome_notes, created_at

situation_type: 情况分类（从task_text提取）
  - career: 职业/辞职/跳槽
  - investment: 投资/买房/理财
  - relationship: 人际关系/感情
  - family: 家庭/婚姻/孩子
  - migration: 移民/留学/搬家
  - health: 健康/医疗
  - education: 教育/考证/读研
  - other: 其他

matched_keywords: 从task_text提取的关键词（用于快速匹配）
"""
import sqlite3
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple

_ROOT = Path(__file__).parent.parent  # E:/juhuo
_DB = _ROOT / "data" / "judgment_data" / "juhuo_judgment.db"

# ── 情况分类 ──────────────────────────────────────────────────

SITUATION_TYPES = {
    "career":       ["辞职", "跳槽", "创业", "工作", "offer", "裁员", "加薪"],
    "investment":   ["买房", "投资", "理财", "炒股", "基金", "存款", "保险"],
    "relationship": ["分手", "复合", "追求", "约会", "恋爱", "暧昧", "前任"],
    "family":       ["结婚", "离婚", "孩子", "父母", "亲戚", "彩礼", "房产证"],
    "migration":    ["移民", "留学", "搬家", "换城市", "回老家", "出国"],
    "health":       ["健康", "体检", "手术", "抑郁", "焦虑", "减肥", "戒烟"],
    "education":    ["读研", "读博", "考证", "考公", "留学", "培训", "MBA"],
    "finance":      ["借钱", "贷款", "负债", "债务", "信用", "房贷"],
    "other":        [],
}


def _classify(task_text: str) -> str:
    """从 task_text 推断情况类型"""
    text = task_text.lower()
    for stype, keywords in SITUATION_TYPES.items():
        if stype == "other":
            continue
        for kw in keywords:
            if kw in text:
                return stype
    return "other"


def _extract_keywords(task_text: str, max_kw: int = 8) -> str:
    """从 task_text 提取关键词（用于匹配）"""
    # 去停用词
    stop = {"我", "你", "他", "她", "它", "的", "了", "是", "在", "和",
            "要", "吗", "呢", "该", "怎么", "如何", "要不要", "要不要"}
    words = re.findall(r'[\w]{2,}', task_text)
    words = [w for w in words if w not in stop and not w.isdigit()]
    # 取高频词
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:max_kw]
    return "|".join(w for w, _ in top)


# ── 存储 ──────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init():
    """建表"""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            situation_type TEXT,
            task_hash TEXT UNIQUE,
            task_text TEXT,
            context TEXT,
            conclusion TEXT NOT NULL,
            confidence REAL,
            matched_keywords TEXT,
            outcome TEXT,
            outcome_notes TEXT,
            outcome_score REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 索引：加速关键词匹配
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_type ON experiences(situation_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_keywords ON experiences(matched_keywords)")
    conn.commit()
    conn.close()


def save_experience(
    task_text: str,
    conclusion: str,
    confidence: float,
    context: str = "",
) -> int:
    """
    存一次判断经历。
    返回 experience id。
    """
    task_hash = hashlib.md5(task_text.encode()).hexdigest()[:16]
    stype = _classify(task_text)
    keywords = _extract_keywords(task_text)

    conn = _get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO experiences
            (situation_type, task_hash, task_text, context, conclusion,
             confidence, matched_keywords, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (stype, task_hash, task_text, context, conclusion,
              confidence, keywords, datetime.now().isoformat()))
        eid = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        # 已存在，更新
        conn.execute("""
            UPDATE experiences
            SET conclusion=?, confidence=?, context=?
            WHERE task_hash=?
        """, (conclusion, confidence, context, task_hash))
        eid = -1  # 表示更新而非新增
    finally:
        conn.close()
    return eid


def record_outcome(
    task_text: str,
    outcome: str,
    outcome_score: float = 1.0,
    notes: str = "",
) -> bool:
    """事后记录结果"""
    task_hash = hashlib.md5(task_text.encode()).hexdigest()[:16]
    conn = _get_conn()
    n = conn.execute("""
        UPDATE experiences
        SET outcome=?, outcome_score=?, outcome_notes=?
        WHERE task_hash=?
    """, (outcome, outcome_score, notes, task_hash)).rowcount
    conn.commit()
    conn.close()
    return n > 0


# ── 相似匹配 ──────────────────────────────────────────────────

def _keyword_overlap(kw1: str, kw2: str) -> float:
    """计算两个关键词集合的重叠度"""
    set1 = set(kw1.split("|")) if kw1 else set()
    set2 = set(kw2.split("|")) if kw2 else set()
    if not set1 or not set2:
        return 0.0
    inter = len(set1 & set2)
    union = len(set1 | set2)
    return inter / union if union > 0 else 0.0


def find_similar(
    task_text: str,
    limit: int = 3,
    min_score: float = 0.15,
) -> List[Dict]:
    """
    找最像的历史经历。
    返回: [{"experience_id", "situation_type", "conclusion",
            "confidence", "matched_keywords", "similarity", "outcome"}, ...]
    """
    stype = _classify(task_text)
    keywords = _extract_keywords(task_text)

    conn = _get_conn()
    rows = conn.execute("""
        SELECT id, situation_type, task_text, conclusion, confidence,
               matched_keywords, outcome, outcome_score
        FROM experiences
        ORDER BY
          CASE WHEN situation_type = ? THEN 1 ELSE 0 END DESC,
          outcome_score DESC NULLS LAST,
          created_at DESC
        LIMIT 100
    """, (stype,)).fetchall()
    conn.close()

    scored = []
    for r in rows:
        eid, rtype, rtext, rconclusion, rconf, rkw, routcome, rscore = r
        kw_sim = _keyword_overlap(keywords, rkw or "")
        type_bonus = 0.15 if rtype == stype else 0.0
        score = kw_sim * 0.7 + type_bonus

        if score >= min_score:
            scored.append({
                "experience_id": eid,
                "situation_type": rtype,
                "task_text": rtext,
                "conclusion": rconclusion,
                "confidence": rconf,
                "matched_keywords": rkw,
                "similarity": round(score, 3),
                "outcome": routcome,
                "outcome_score": rscore,
            })

    scored.sort(key=lambda x: -x["similarity"])
    return scored[:limit]


# ── 冷启动种子 ────────────────────────────────────────────────

EXPERIENCE_SEEDS = [
    {"task": "有一笔50万存款，3%年利率，另一投资机会50%概率翻倍，50%概率亏损30%，怎么选？", "verdict": "选分散配置，不要全押高风险", "confidence": 0.80},
    {"task": "高薪大公司996 vs 低薪小公司朝九晚五，怎么选？", "verdict": "看成长空间和个人阶段，不一概而论", "confidence": 0.75},
    {"task": "朋友借钱不还，还要不要借第二次？", "verdict": "看关系深浅和金额大小，救急不救穷", "confidence": 0.78},
    {"task": "要不要从大公司跳槽到创业公司？", "verdict": "看赛道和团队，靠谱的可以博一把", "confidence": 0.77},
    {"task": "要不要裸辞休息一段时间？", "verdict": "有积蓄有方向就休息，没有就别裸辞", "confidence": 0.76},
    {"task": "要不要报一个5万块的MBA课程？", "verdict": "看目的和ROI，不是为了学历镀金", "confidence": 0.75},
    {"task": "要不要all in炒股？", "verdict": "普通人all in炒股风险极高，不要", "confidence": 0.85},
    {"task": "要不要移民？", "verdict": "想清楚代价和目的，想好了就去", "confidence": 0.73},
    {"task": "要不要和对象分手？", "verdict": "触及底线就分，不是底线就磨合", "confidence": 0.80},
    {"task": "要不要买房？", "verdict": "看城市看时机，不要跟风", "confidence": 0.78},
    {"task": "要不要创业？", "verdict": "先做调研，见过足够多创业案例再决定", "confidence": 0.80},
    {"task": "要不要借钱给亲戚？", "verdict": "做好不还的准备再借，借了就别惦记", "confidence": 0.82},
    {"task": "要不要读研究生？", "verdict": "看专业和职业规划，不是为了逃避就业", "confidence": 0.76},
    {"task": "要不要考证？", "verdict": "考证是手段不是目的，看有没有实际用处", "confidence": 0.75},
    {"task": "要不要换城市工作？", "verdict": "权衡机会成本和生活成本，不为逃避而换", "confidence": 0.77},
    {"task": "要不要投资数字货币？", "verdict": "高风险，做好归零准备再用闲钱", "confidence": 0.72},
    {"task": "要不要接受父母安排的相亲？", "verdict": "去见见无妨，不合适就直说", "confidence": 0.74},
    {"task": "要不要让孩子学奥数？", "verdict": "看孩子兴趣，不要强推", "confidence": 0.76},
    {"task": "要不要帮朋友做担保？", "verdict": "不要，担保风险极高", "confidence": 0.85},
    {"task": "要不要接受一份低于市场价的offer？", "verdict": "看成长性和领导，长期有回报就考虑", "confidence": 0.74},
]


def seed_initial_experiences():
    """用初始种子数据填充 experiences 表（冷启动，只运行一次）"""
    init()
    added = 0
    for case in EXPERIENCE_SEEDS:
        eid = save_experience(case["task"], case["verdict"], case["confidence"])
        if eid != -1:
            added += 1
    return added


def get_context_for_judgment(task_text: str) -> str:
    """
    为判断生成历史参考上下文。
    拼成一段 prompt-friendly 的文字。
    """
    similar = find_similar(task_text, limit=3)
    if not similar:
        return ""

    lines = ["\n【历史参考】顾庸x 遇到过类似情况："]
    for i, s in enumerate(similar, 1):
        lines.append(f"{i}. 情况：{s['task_text'][:40]}...")
        lines.append(f"   判断：{s['conclusion']}")
        if s.get("outcome"):
            lines.append(f"   结果：{s['outcome']}（{'对' if s.get('outcome_score',0)>=0.6 else '待验证'}）")
        lines.append(f"   相似度：{s['similarity']:.0%}")
    return "\n".join(lines)


#