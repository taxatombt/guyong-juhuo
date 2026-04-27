# -*- coding: utf-8 -*-
"""
judgment/honcho_soft_profile.py — Honcho 软画像推断

从 experiences 表推断用户的软画像（行为模式）：
  - debug导向 / 重视原理 / 实战派 / 学术型 / 谨慎型 / 冒险型
  - 决策风格（快速决断/深思熟虑）

Hermes Orange-Book 启发：
  L1 (Hard Profile): biographical_facts — 年龄/职业/地域/学历
  L2 (Soft Profile): soft_profile — 行为模式/决策风格
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
        "keywords": ["怎么用","代码","实现","demo","示例","跑通",
                     "快速","上手","实践","落地","直接","最快"],
        "weight": 1.0,
    },
    "学术型": {
        "keywords": ["paper","论文","research","研究","survey","综述",
                     "benchmark","state of art","SOTA","数据集","metric"],
        "weight": 1.0,
    },
    "谨慎型": {
        "keywords": ["风险","万一","最坏情况","容错","备份","安全",
                     "稳妥","保守","确认","验证","测试","边界条件"],
        "weight": 1.0,
    },
    "冒险型": {
        "keywords": ["all in","梭哈","干","冲","先做","边做边改",
                     "试错","快速迭代","MVP","先上线再说"],
        "weight": 1.0,
    },
    "追求效率": {
        "keywords": ["最快","最优","性能","并发","异步","缓存",
                     "优化","加速","省时间","自动","批量"],
        "weight": 1.0,
    },
    "追求质量": {
        "keywords": ["优雅","clean code","重构","可维护","可扩展",
                     "健壮","测试覆盖","code review","规范"],
        "weight": 1.0,
    },
}

DECISION_PATTERNS = {
    "快速决断": {
        "keywords": ["先做","先跑","先试","先用","直接","立刻",
                     "马上","立即","不等"],
        "weight": 1.0,
    },
    "深思熟虑": {
        "keywords": ["再想想","考虑","权衡","对比","综合","评估",
                     "分析","调研","先查","信息不足","不确定"],
        "weight": 1.0,
    },
}


def _score_trait(text: str, patterns: dict) -> float:
    text_lower = text.lower()
    total = 0.0
    for info in patterns.values():
        for kw in info["keywords"]:
            if kw.lower() in text_lower:
                total += info["weight"]
    return total


def infer_soft_profile(user_id: str = "default", limit: int = 50) -> dict:
    """从 experiences 表推断用户软画像"""
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
        texts = [r[0] or "" for r in rows]
        texts += [r[1] or "" for r in rows]
        based_on = len([t for t in texts if t.strip()])
    except Exception:
        pass

    # 推断 traits
    trait_scores: Dict[str, float] = {}
    for trait, patterns in TRAIT_PATTERNS.items():
        score = sum(_score_trait(t, {trait: patterns}) for t in texts)
        if score > 0:
            trait_scores[trait] = score

    sorted_traits = sorted(trait_scores.items(), key=lambda x: x[1], reverse=True)
    top_traits = [
        {"name": name, "score": round(score, 2)}
        for name, score in sorted_traits[:5]
    ]

    # 推断决策风格
    dec_scores = {k: sum(_score_trait(t, {k: v}) for t in texts)
                  for k, v in DECISION_PATTERNS.items()}
    decision_style = max(dec_scores, key=dec_scores.get) if dec_scores else "未知"
    if dec_scores.get(decision_style, 0) == 0:
        decision_style = "未知"

    confidence = min(1.0, based_on / 20.0) if based_on > 0 else 0.0

    return {
        "traits": top_traits,
        "decision_style": decision_style,
        "confidence": round(confidence, 2),
        "based_on": based_on,
        "last_updated": "",
    }


def soft_profile_to_prompt(user_id: str = "default") -> str:
    """生成软画像提示文本，注入判断 prompt"""
    profile = infer_soft_profile(user_id)
    if profile["confidence"] < 0.1:
        return ""

    lines = ["【用户软画像（行为模式推断）】"]
    if profile["traits"]:
        traits_str = " / ".join(f"{t['name']}({t['score']})" for t in profile["traits"])
        lines.append(f"行为倾向: {traits_str}")
    if profile["decision_style"] != "未知":
        lines.append(f"决策风格: {profile['decision_style']}")
    lines.append(f"（基于{profile['based_on']}条历史推断）")
    return "\n".join(lines)
