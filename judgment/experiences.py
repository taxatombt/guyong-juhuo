# experiences.py — 经历层：每个使用者独立的历史记忆
"""
多用户设计：
- user_id: 使用者唯一标识（CoPaw session_id / channel+user_id / "default"）
- task_hash: (user_id, task_text) 组合哈希，同一用户同问题去重
- find_similar: 只匹配同一用户的经历
- CLI/benchmark: user_id="default"（单用户模式）
"""
import json as _json
import re
import sqlite3
import hashlib
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict


from judgment._schema import _get_db_conn
SITUATION_TYPES = {
    "career":       ["辞职", "跳槽", "创业", "工作", "offer", "裁员", "加薪"],
    "investment":   ["买房", "投资", "理财", "炒股", "基金", "存款", "保险", "股市", "全仓"],
    "relationship": ["分手", "复合", "追求", "约会", "恋爱", "暧昧", "前任"],
    "family":       ["结婚", "离婚", "孩子", "父母", "亲戚", "彩礼", "房产证"],
    "migration":    ["移民", "留学", "搬家", "换城市", "回老家", "出国"],
    "health":       ["健康", "体检", "手术", "抑郁", "焦虑", "减肥", "戒烟"],
    "education":    ["读研", "读博", "考证", "考公", "留学", "培训", "MBA"],
    "finance":      ["借钱", "贷款", "负债", "债务", "信用", "房贷"],
    "other":        [],
}

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


def _classify(task_text: str) -> str:
    # 移除停用词短语（与 _extract_keywords 保持一致）
    for ph in ["要不要", "该不该"]:
        task_text = task_text.replace(ph, "")
    text = task_text.lower()
    for stype, keywords in SITUATION_TYPES.items():
        if stype == "other":
            continue
        for kw in keywords:
            if kw in text:
                return stype
    return "other"


def _extract_keywords(task_text: str, max_kw: int = 8) -> str:
    # 移除停用词短语
    for ph in ["要不要", "该不该"]:
        task_text = task_text.replace(ph, "")
    candidates = set()
    # 英文单词
    for w in re.findall(r'[a-zA-Z0-9]{2,6}', task_text):
        if not w.isdigit():
            candidates.add(w.lower())
    # 中文字符 bigram/trigram（在连续中文字符串上滑动）
    chinese_chars = [c for c in task_text if '一' <= c <= '鿿']
    for i in range(len(chinese_chars)):
        for length in [2, 3]:  # 2字词和3字词
            if i + length <= len(chinese_chars):
                kw = ''.join(chinese_chars[i:i + length])
                candidates.add(kw)
    # 频率统计（这里简化为直接用集合去重）
    top = sorted(candidates, key=lambda x: -len(x))[:max_kw]
    return "|".join(top)


def _task_hash(user_id: str, task_text: str) -> str:
    return hashlib.md5(f"{user_id}::{task_text}".encode()).hexdigest()[:24]


def _get_conn():
    return _get_db_conn()


def init():
    """
    初始化 experiences 表（P1-4：统一使用 _schema_tables.py 中的完整 schema）。

    流程：
    1. 用 _schema_tables._TABLE_DEFS 中的 unified schema 创建 experiences 表
       （行为列：action_channel / tool_calls / execution_result / perception_summary / behavior_id
        由 _schema_tables 统一管理，不再由 behavior_logger._migrate() 兜底）
    2. 如旧表缺少行为列，走 _rebuild_table 迁移（保留现有数据）

    注意：不使用 _schema._get_db_conn()（它会被同一线程的后续操作复用），
    而是创建独立连接，完成后关闭（init 只在启动时运行一次）。
    """
    from ._schema_tables import _TABLE_DEFS, _rebuild_table
    from pathlib import Path as _Path

    # 使用独立连接（init 只在 _ensure_started 时调用一次）
    db_path = _Path(__file__).parent.parent / "data" / "juhuo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        exp_def = dict(_TABLE_DEFS)["experiences"]
        # 尝试用 CREATE TABLE IF NOT EXISTS 建表
        conn.execute(f"CREATE TABLE IF NOT EXISTS experiences ({exp_def})")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_user ON experiences(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_type ON experiences(user_id, situation_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_kw ON experiences(user_id, matched_keywords)")
        conn.commit()

        # 如果旧表缺少列，走 _rebuild_table 迁移（保留现有数据）
        existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(experiences)").fetchall()]
        behavior_cols = ["action_channel", "tool_calls", "execution_result",
                         "perception_summary", "behavior_id", "source", "task_embedding"]
        missing = [c for c in behavior_cols if c not in existing_cols]
        if missing:
            print(f"[experiences.init] 迁移 experiences 表，补充列: {missing}")
            _rebuild_table(conn, "experiences", exp_def)
    finally:
        conn.close()


def _get_embedding(text: str) -> str:
    """生成文本 embedding，失败返回空字符串。"""
    try:
        from adapters.llm.minimax import get_adapter
        adapter = get_adapter()
        vec = adapter.embed(text)
        if vec:
            import json as _json
            return _json.dumps(vec)
    except Exception:
        pass
    return ""


def save_experience(task_text: str, conclusion: str, confidence: float,
                   context: str = "", user_id: str = "default",
                   perception_summary: str = "",
                   chain_id: str = "") -> int:
    """Save or update a user experience record.
    
    Args:
        chain_id: judgment snapshot chain_id, used for linking to closed_loop.receive_verdict
    """
    th = _task_hash(user_id, task_text)
    stype = _classify(task_text)
    keywords = _extract_keywords(task_text)
    embedding = _get_embedding(task_text)
    conn = _get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO experiences
            (user_id, situation_type, task_hash, task_text, context, conclusion,
             confidence, matched_keywords, created_at, task_embedding,
             perception_summary, chain_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (user_id, stype, th, task_text, context, conclusion,
              confidence, keywords, datetime.now().isoformat(), embedding,
              perception_summary, chain_id or None))
        eid = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.execute("""
            UPDATE experiences
            SET conclusion=?, confidence=?, context=?, task_embedding=COALESCE(task_embedding, ?),
                perception_summary=COALESCE(?, perception_summary),
                chain_id=COALESCE(?, chain_id)
            WHERE user_id=? AND task_hash=?
        """, (conclusion, confidence, context, embedding, perception_summary,
              chain_id or None, user_id, th))
        eid = -1
    finally:
        pass  # P0-1: 不关闭 per-thread 连接

    # L3: 感知结果同步写入 perception_intents 表
    if perception_summary:
        try:
            from judgment.user_model import save_perception_result
            save_perception_result(
                source="manual",
                topic=stype or "perception",
                content=perception_summary,
                url="",
                priority=3,
            )
        except Exception:
            pass

    return eid


def record_outcome(task_text: str, outcome: str, outcome_score: float = 1.0,
                   notes: str = "", user_id: str = "default",
                   chain_id: str = "") -> bool:
    """Record the outcome of a judgment experience.
    
    Args:
        chain_id: if provided, UPDATE by chain_id first (avoids task_hash mismatch
                  between experiences[SHA256[:16]] and judgment_snapshots[MD5[:24]])
    """
    conn = _get_conn()
    
    if chain_id:
        n = conn.execute(
            'UPDATE experiences SET outcome=?, outcome_score=?, outcome_notes=? '
            'WHERE chain_id=?',
            (outcome, outcome_score, notes, chain_id)).rowcount
    else:
        th = _task_hash(user_id, task_text)
        n = conn.execute(
            'UPDATE experiences SET outcome=?, outcome_score=?, outcome_notes=? '
            'WHERE user_id=? AND task_hash=?',
            (outcome, outcome_score, notes, user_id, th)).rowcount
    
    conn.commit()
    return n > 0  # P0-1: 不关闭 per-thread 连接

def _keyword_overlap(kw1: str, kw2: str) -> float:
    set1 = set(kw1.split("|")) if kw1 else set()
    set2 = set(kw2.split("|")) if kw2 else set()
    if not set1 or not set2: return 0.0
    inter = len(set1 & set2)
    # 子串匹配加分："股市" 覆盖 "进股市"，"all" 覆盖 "allin"
    for s in list(set1):
        for t in list(set2):
            if s in t or t in s:
                inter += 0.5
    inter = min(inter, len(set1) + len(set2))
    union = len(set1 | set2)
    return inter / union if union > 0 else 0.0

def _cosine_sim(a: List[float], b: List[float]) -> float:
    """纯 Python cosine similarity（无 numpy 依赖）。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_similar(task_text: str, limit: int = 3, min_score: float = 0.05, user_id: str = "default") -> list:
    stype = _classify(task_text)
    keywords = _extract_keywords(task_text)
    # P3-11: 生成 query embedding（所有行共用同一个 query embedding）
    query_emb = _get_embedding(task_text)
    query_vec = _json.loads(query_emb) if query_emb else []

    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, situation_type, task_text, conclusion, confidence, "
        "matched_keywords, outcome, outcome_score, task_embedding "
        "FROM experiences WHERE user_id = ? "
        "ORDER BY CASE WHEN situation_type = ? THEN 1 ELSE 0 END DESC, "
        "outcome_score DESC, created_at DESC LIMIT 100",
        (user_id, stype)).fetchall()
    # P0-1: 不关闭 per-thread 连接

    scored = []
    for r in rows:
        eid, rtype, rtext, rconclusion, rconf, rkw, routcome, rscore, r_emb = r
        kw_sim = _keyword_overlap(keywords, rkw or "")
        type_bonus = 0.15 if rtype == stype else 0.0

        # P3-11: cosine similarity（仅当双方都有 embedding 时）
        emb_sim = 0.0
        if query_vec and r_emb:
            try:
                stored_vec = _json.loads(r_emb)
                emb_sim = _cosine_sim(query_vec, stored_vec)
            except Exception:
                emb_sim = 0.0

        # 混合评分：embedding 0.5 + keyword 0.3 + type 0.15
        if emb_sim > 0:
            score = emb_sim * 0.5 + kw_sim * 0.3 + type_bonus
        else:
            # 无 embedding 时回退到纯 keyword + type
            score = kw_sim * 0.7 + type_bonus

        if score >= min_score:
            scored.append({
                "experience_id": eid, "situation_type": rtype,
                "task_text": rtext, "conclusion": rconclusion,
                "confidence": rconf, "matched_keywords": rkw,
                "similarity": round(score, 3),
                "emb_similarity": round(emb_sim, 3) if emb_sim > 0 else None,
                "outcome": routcome, "outcome_score": rscore,
            })
    scored.sort(key=lambda x: -x["similarity"])
    return scored[:limit]


def find_similar_structured(task_text: str, user_id: str = "default", limit: int = 10) -> list:
    """
    P0 融合: similarity(0.6) + keyword_overlap(0.4)
    返回比 find_similar 更完整的结构，含 keywords + created_at
    """
    results = find_similar(task_text, limit=limit, user_id=user_id)
    for r in results:
        # 解析 matched_keywords
        kw_str = r.get("matched_keywords", "")
        if kw_str:
            try:
                r["keywords"] = _json.loads(kw_str) if kw_str.startswith("[") else [kw_str]
            except Exception:
                r["keywords"] = [kw_str] if kw_str else []
        else:
            r["keywords"] = []
        # 补充 created_at
        eid = r.get("experience_id")
        if eid:
            row = _get_conn().execute(
                "SELECT created_at FROM experiences WHERE id = ?", (eid,)
            ).fetchone()
            r["created_at"] = row["created_at"] if row else ""
    return results


def get_context_for_judgment(task_text: str, user_id: str = "default") -> str:
    similar = find_similar(task_text, limit=3, user_id=user_id)
    if not similar: return ""
    lines = ["\n【历史参考】这个用户（你）遇到过类似情况："]
    for i, s in enumerate(similar, 1):
        lines.append(str(i) + ". 情况：" + (s["task_text"] or s.get("conclusion") or "类似经历")[:40] + "...")
        lines.append("   判断：" + s["conclusion"])
        if s.get("outcome"):
            ok = "对" if s.get("outcome_score", 0) >= 0.6 else "待验证"
            lines.append("   结果：" + s["outcome"] + "（" + ok + "）")
        lines.append("   相似度：" + str(round(s["similarity"] * 100)) + "%")
    return "\n".join(lines)

def seed_initial_experiences(user_id: str = "default") -> int:
    init()
    added = 0
    for case in EXPERIENCE_SEEDS:
        eid = save_experience(case["task"], case["verdict"], case["confidence"], user_id=user_id)
        if eid != -1: added += 1
    return added
