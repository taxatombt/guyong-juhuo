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