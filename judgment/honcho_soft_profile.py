# -*- coding: utf-8 -*-
"""
judgment/honcho_soft_profile.py — Honcho 软画像推断

从 experiences 表推断用户的软画像（行为模式）：
  - debug导向 / 重视原理 / 实战派 / 学术型 / 谨慎型 / 冒险型
  - 决策风格（快速决断 / 深思熟虑 / 分析型）
"""

from typing import List, Dict

TRAIT_PATTERNS = {
    "debug导向": {
        "keywords": ["bug","error","debug","调试","修复","崩溃","闪退",
                     "crash","exception","stack","traceback","性能问题",
                     "内存泄漏","race condition","并发","死锁"],
        "weight": 1.5,
    },
    "重视原理": {
        "keywords": ["原理","机制","为什么","怎么实现","架构","设计模式",
                     "algorithm","理论","本质","底层","内核","source code",
                     "源码","理解","分解","推演"],
        "weight": 1.2,
    },
    "实战派": {
        "keywords": ["实战","落地","实践","执行","做出来","先试","快速迭代",
                     "MVP","最小可行","先跑","干了再说"],
        "weight": 1.0,
    },
    "学术型": {
        "keywords": ["论文","研究","学术","发表","理论","文献","引用",
                     "benchmark","数据集","评测","survey","综述"],
        "weight": 1.0,
    },
    "谨慎型": {
        "keywords": ["风险","慎重","谨慎","再想想","不急","等等看",
                     "冷静","保守","稳住","先评估","备份"],
        "weight": 1.0,
    },
    "冒险型": {
        "keywords": ["all in","梭哈","冲","干就完了","不怕","赌",
                     "博一把","冲一把","先干了","激进","果断"],
        "weight": 1.0,
    },
}

DECISION_PATTERNS = {
    "快速决断": {
        "keywords": ["先干","先做","先试","赶紧","立即","马上",
                     "不等了","先冲","先跑起来","立刻"],
        "weight": 1.0,
    },
    "深思熟虑": {
        "keywords": ["再想想","仔细","评估","分析","权衡","谨慎",
                     "慎重","充分","全面","深入","仔细考虑"],
        "weight": 1.0,
    },
    "分析型": {
        "keywords": ["数据","指标","分析","逻辑","推理","因果",
                     "量化","对比","拆解","验证"],
        "weight": 1.0,
    },
}


def _score_trait(texts: List[str], trait: str) -> float:
    if trait not in TRAIT_PATTERNS:
        return 0.0
    info = TRAIT_PATTERNS[trait]
    total = 0.0
    for text in texts:
        if not text:
            continue
        text_lower = text.lower()
        for kw in info["keywords"]:
            if kw.lower() in text_lower:
                total += info["weight"]
    return total


def infer_soft_profile(user_id: str = "default", limit: int = 50) -> dict:
    texts = []
    based_on = 0
    try:
        from judgment._schema import _get_db_conn
        conn = _get_db_conn()
        rows = conn.execute(
            "SELECT task_text, conclusion, outcome FROM experiences "
            "WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        conn.close()
        for r in rows:
            if r[0]:
                texts.append(r[0])
            if r[1]:
                texts.append(r[1])
            if r[2]:
                texts.append(str(r[2]))
        based_on = len([t for t in texts if t.strip()])
    except Exception:
        pass

    if not based_on:
        return {
            "traits": [],
            "decision_style": "未知",
            "confidence": 0.0,
            "based_on": 0,
            "last_updated": "",
        }

    trait_scores = {}
    for trait in TRAIT_PATTERNS:
        score = _score_trait(texts, trait)
        if score > 0:
            trait_scores[trait] = score

    sorted_traits = sorted(trait_scores.items(), key=lambda x: x[1], reverse=True)
    top_traits = [
        {"name": name, "score": round(score, 2)}
        for name, score in sorted_traits[:5]
    ]

    dec_scores = {}
    for style, info in DECISION_PATTERNS.items():
        score = sum(
            1 for text in texts
            if text and any(kw.lower() in text.lower() for kw in info["keywords"])
        )
        if score > 0:
            dec_scores[style] = score

    decision_style = "未知"
    if dec_scores:
        decision_style = max(dec_scores, key=dec_scores.get)

    confidence = min(1.0, based_on / 20.0) if based_on > 0 else 0.0
    return {
        "traits": top_traits,
        "decision_style": decision_style,
        "confidence": round(confidence, 2),
        "based_on": based_on,
        "last_updated": "",
    }


def soft_profile_to_prompt(user_id: str = "default") -> str:
    """生成软画像提示文本，confidence < 0.1 时返回空字符串。"""
    profile = infer_soft_profile(user_id)
    _conf = float(profile.get("confidence", 0.0))
    if _conf < 0.1:
        return ""
    lines = []
    lines.append("【用户软画像（行为模式推断）】")
    traits = profile.get("traits", [])
    if traits:
        traits_str = " / ".join(f"{t['name']}({t['score']:.0f})" for t in traits)
        lines.append(f"行为倾向: {traits_str}")
    decision_style = profile.get("decision_style", "未知")
    if decision_style != "未知":
        lines.append(f"决策风格: {decision_style}")
    return "\n".join(lines)
