"""
user_model.py — UserModel 汇聚层

三路信息 -> UserModel -> router

架构：
  biography.py (L1) ---+
  experiences.py (L2) --+---> UserModel.get_context() ---> router.py
  causal_memory (L3) --+

主要能力：
- 矛盾检测：L1 声称 vs L2 行为模式
- 时间衰减：近期 > 远期，fact 半衰期 365天，pattern 半衰期 180天
- 按任务相关性过滤：三路信息加权合并
"""
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path
import sqlite3
import json
import math
import datetime

# 数据结构

@dataclass
class Fact:
    category: str
    fact: str
    confidence: float
    importance: int
    created_at: str
    last_seen: str
    mentions: int
    tags: List[str]
    time_weight: float = 1.0
    contradiction_flag: bool = False
    half_life_days: int = 365  # P1: 分级半衰期，0=永不过期


@dataclass
class Pattern:
    situation_type: str
    task_text: str
    conclusion: str
    outcome_score: Optional[float]
    outcome: Optional[str]
    keywords: List[str]
    created_at: str
    recency_score: float = 1.0


@dataclass
class Intent:
    topic: str
    summary: str
    source: str
    relevance: float = 0.5
    recency: str = ""

@dataclass
class BehaviorEntry:
    behavior_id: str
    channel: str
    conclusion: str
    tool_calls: List[str]
    outcome_score: Optional[float]
    created_at: str



@dataclass
class ProfileEntry:
    """
    统一条目：三条通路的数据统一成同一个结构。
    
    source:   "fact" / "pattern" / "signal"
    priority: 1 (L1 主动确认) / 2 (L2 行为推断) / 3 (L3 被动信号)
    dimension: 关联的判断维度
    """
    source: str          # "fact" | "pattern" | "signal"
    priority: int         # 1 > 2 > 3
    dimension: str       # 判断维度 id
    claim: str            # 主张内容
    evidence: str         # 原始证据（来源文本）
    confidence: float     # 原始置信度
    recency_score: float  # 时间衰减后的权重
    contradiction_flag: bool = False
    profile_id: str = ""  # 关联的 DB row id ("fact:{id}" / "pattern:{id}")


@dataclass
class Contradiction:
    dimension: str
    l1_claim: str
    l2_behavior: str
    severity: str   # "high" / "medium" / "low"
    l1_weight_penalty: float


@dataclass
class UnifiedContext:
    facts: List[Fact] = field(default_factory=list)
    patterns: List[Pattern] = field(default_factory=list)
    intents: List[Intent] = field(default_factory=list)
    contradictions: List[Contradiction] = field(default_factory=list)
    oldest_fact_days: int = 0
    newest_fact_days: int = 0
    oldest_pattern_days: int = 0
    newest_pattern_days: int = 0


# 语义维度配置
_SEMANTIC_DIMENSIONS = {
    "risk_tolerance": {
        "l1_claims": ["保守", "稳健", "风险厌恶", "不冒险", "怕亏", "谨慎投资", "稳健型", "低风险"],
        "l2_patterns": ["all in", "全仓", "高杠杆", "炒股", "投机", "赌博", "激进", "加杠杆", "追涨"],
        "severity": "high",
        "penalty": 0.4,
    },
    "career_ambition": {
        "l1_claims": ["稳定就好", "不卷", "躺平", "安稳", "保守", "不想冒险"],
        "l2_patterns": ["创业", "跳槽", "辞职", "all in", "转型", "裸辞", "拼命工作", "高强度"],
        "severity": "high",
        "penalty": 0.4,
    },
    "financial_habit": {
        "l1_claims": ["量入为出", "存钱", "节俭", "不乱花钱", "储蓄", "理性消费"],
        "l2_patterns": ["高消费", "贷款消费", "超前消费", "奢侈品", "冲动购物"],
        "severity": "medium",
        "penalty": 0.3,
    },
    "relationship_style": {
        "l1_claims": ["独立", "不依赖", "理性", "不感情用事"],
        "l2_patterns": ["闪婚", "闪离", "异地恋", "网恋", "情感用事", "为爱放弃"],
        "severity": "low",
        "penalty": 0.2,
    },
}


class UserModel:
    """
    三路信息汇聚层。
    用法：
        um = UserModel()
        ctx = um.get_context_for_task("要不要辞职创业？", user_id="default")
        prompt_context = um.synthesize(ctx, task_text)
    """

    FACT_HALF_LIFE = 365
    PATTERN_HALF_LIFE = 180
    MAX_FACTS = 15
    MAX_PATTERNS = 10

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._bio_db = Path(__file__).parent.parent / "data" / "causal_memory" / "events.db"
        self._juhuo_db = Path(__file__).parent.parent / "data" / "juhuo.db"
        self._pi_db = self._juhuo_db
        self._profile_entries: List[ProfileEntry] = []

    def get_context_for_task(self, task_text: str, user_id: Optional[str] = None) -> UnifiedContext:
        uid = user_id or self.user_id
        facts = self._get_l1_facts(uid)
        patterns = self._get_l2_patterns(task_text, uid)
        behaviors = self._get_l3_behaviors(uid)
        intents = self._get_l3_intents(task_text, uid)
        for b in behaviors:
            intents.append(Intent(
                topic="[agent:{}] {}".format(b.channel, b.conclusion[:40]),
                summary=b.conclusion[:100],
                source="behavior:{}".format(b.channel),
                relevance=b.outcome_score or 0.5,
                recency=b.created_at,
            ))
        facts = self._apply_time_decay(facts, self.FACT_HALF_LIFE)
        patterns = self._apply_time_decay(patterns, self.PATTERN_HALF_LIFE)
        contradictions = self._detect_contradictions(facts, patterns)
        for fact in facts:
            for c in contradictions:
                if any(kw in fact.fact for kw in _SEMANTIC_DIMENSIONS[c.dimension]["l1_claims"]):
                    fact.contradiction_flag = True
                    fact.time_weight *= (1.0 - c.l1_weight_penalty)
        facts = self._filter_by_task_relevance(facts, task_text)[:self.MAX_FACTS]
        patterns = self._filter_by_task_relevance(patterns, task_text)[:self.MAX_PATTERNS]
        time_summary = self._time_summary(facts, patterns)
        ctx = UnifiedContext(facts=facts, patterns=patterns, intents=intents,
                             contradictions=contradictions, **time_summary)
        self._profile_entries = UnifiedProfile().generate(ctx, task_text)
        for c_ in contradictions:
            update_profile_on_contradiction(c_, ctx)
        return ctx

    def generate_profile(self, ctx: UnifiedContext, task_text: str) -> List[ProfileEntry]:
        self._profile_entries = UnifiedProfile().generate(ctx, task_text)
        return self._profile_entries

    def get_profile(self) -> List[ProfileEntry]:
        return self._profile_entries

    def synthesize(self, ctx: UnifiedContext, task_text: str) -> str:
        parts = []
        if ctx.contradictions:
            high = [c for c in ctx.contradictions if c.severity == "high"]
            if high:
                parts.append("[Contradiction Warning]")
                for c in high[:2]:
                    parts.append("  WARNING {}: claims {} but historically {}".format(
                        c.dimension, c.l1_claim, c.l2_behavior))
        if ctx.facts:
            parts.append("[Known Facts]")
            for f in ctx.facts[:8]:
                flag = " [contradict]" if f.contradiction_flag else ""
                parts.append("  - {}{}".format(f.fact, flag))
        if ctx.patterns:
            parts.append("[Behavior Patterns]")
            for p in ctx.patterns[:5]:
                outcome_str = " -> {}".format(p.outcome) if p.outcome else ""
                parts.append("  - {}{} ({})".format(p.conclusion, outcome_str, p.situation_type))
        if ctx.intents:
            parts.append("[Perception Intents]")
            for i in ctx.intents[:5]:
                parts.append("  - [{}.{}] {}: {}...".format(
                    i.source, i.topic[:15], i.relevance, i.summary[:60]))
        return "\n".join(parts) if parts else ""
    # L1: Biography facts
    def _get_l1_facts(self, user_id: str) -> List[Fact]:
        db = self._bio_db
        if not db.exists():
            return []
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT category, fact, confidence, importance, created_at, last_seen, mentions, tags, half_life_days "
                "FROM biographical_facts ORDER BY importance DESC, mentions DESC LIMIT 50").fetchall()
        finally:
            conn.close()
        facts = []
        for r in rows:
            tags = []
            if r["tags"]:
                try: tags = json.loads(r["tags"])
                except: pass
            facts.append(Fact(
                category=r["category"] or "unknown",
                fact=r["fact"],
                confidence=float(r["confidence"] or 1.0),
                importance=int(r["importance"] or 1),
                created_at=r["created_at"] or "",
                last_seen=r["last_seen"] or r["created_at"] or "",
                mentions=int(r["mentions"] or 1),
                tags=tags,
                half_life_days=r["half_life_days"] if r["half_life_days"] is not None else 365,
            ))
        return facts

    # L2: Experience patterns - find_similar_structured
    # 铁律: experiences > biography > behavior
    def _get_l2_patterns(self, task_text: str, user_id: str = "default") -> List[Pattern]:
        try:
            from judgment.experiences import find_similar_structured
            rows = find_similar_structured(task_text, user_id=user_id, limit=10)
        except Exception:
            return []
        patterns = []
        for r in rows:
            p = Pattern(
                situation_type=r.get("situation_type","other"),
                task_text=r.get("task_text",""),
                conclusion=r.get("conclusion",""),
                outcome_score=r.get("outcome_score"),
                outcome=r.get("outcome"),
                keywords=r.get("keywords",[]),
                created_at=r.get("created_at",""),
            )
            p.recency_score = r.get("similarity",0.5)
            patterns.append(p)
        return patterns

    # L3: Perception intents — 从三个来源汇聚
    def _get_l3_behaviors(self, user_id: str = "default", limit: int = 10) -> List[BehaviorEntry]:
        try:
            from judgment.behavior_logger import get_recent_behaviors
            rows = get_recent_behaviors(user_id=user_id, limit=limit)
        except Exception:
            return []
        entries = []
        for r in rows:
            tc = []
            if r.get("tool_calls"):
                try:
                    tc = json.loads(r["tool_calls"]) if isinstance(r["tool_calls"], str) else list(r["tool_calls"])
                except: pass
            entries.append(BehaviorEntry(
                behavior_id=str(r.get("behavior_id","")),
                channel=r.get("action_channel","JUDGMENT"),
                conclusion=r.get("conclusion",""),
                tool_calls=tc,
                outcome_score=r.get("outcome_score"),
                created_at=r.get("created_at",""),
            ))
        return entries


    def _get_l3_intents(self, task_text: str, user_id: str = "default") -> List[Intent]:
        intents = []
        seen_topics = set()

        def _add(topic, summary, source, relevance, recency):
            key = (topic, source)
            if key not in seen_topics:
                seen_topics.add(key)
                intents.append(Intent(
                    topic=topic,
                    summary=summary[:200] if summary else "",
                    source=source,
                    relevance=relevance,
                    recency=recency,
                ))

        # 来源1：perception_intents 表（最近感知结果，TTL 7天）
        pi_db = self._pi_db
        if pi_db.exists():
            conn = sqlite3.connect(str(pi_db))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT source, topic, content, url, priority, created_at "
                    "FROM perception_intents "
                    "WHERE created_at >= datetime('now', '-7 days') "
                    "ORDER BY created_at DESC LIMIT 20").fetchall()
                for r in rows:
                    _add(
                        topic=r["topic"] or r["source"] or "perception",
                        summary=r["content"] or "",
                        source="perception:" + (r["source"] or "unknown"),
                        relevance=min((r["priority"] or 0) / 5.0, 1.0),
                        recency=r["created_at"] or "",
                    )
            except Exception:
                pass
            finally:
                conn.close()

        # 来源2：experiences 表的 perception_summary 字段
        jh_db = self._juhuo_db
        if jh_db.exists():
            conn = sqlite3.connect(str(jh_db))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT perception_summary, situation_type, created_at "
                    "FROM experiences WHERE perception_summary IS NOT NULL "
                    "AND perception_summary != '' "
                    "ORDER BY created_at DESC LIMIT 5").fetchall()
                for r in rows:
                    if r["perception_summary"]:
                        # 从 summary 文本中提取第一行作为 topic
                        first_line = r["perception_summary"].split("\n")[0][:50]
                        _add(
                            topic=r["situation_type"] or first_line or "perception",
                            summary=r["perception_summary"],
                            source="experiences",
                            relevance=0.6,
                            recency=r["created_at"] or "",
                        )
            except Exception:
                pass
            finally:
                conn.close()

        # 来源3：causal_memory（兜底）
        try:
            from causal_memory import recall_causal_history
            result = recall_causal_history(task_text)
            for chain in (result.get("causal_chains") or [])[:3]:
                _add(
                    topic=chain.get("situation_type", "unknown"),
                    summary=chain.get("conclusion", ""),
                    source="causal_memory",
                    relevance=0.5,
                    recency=chain.get("created_at", ""),
                )
        except Exception:
            pass

        # 按 relevance 排序，返回最多10条
        intents.sort(key=lambda x: x.relevance, reverse=True)
        return intents[:10]

    # 矛盾检测
    def _detect_contradictions(self, facts: List[Fact], patterns: List[Pattern]) -> List[Contradiction]:
        contradictions = []
        l1_claims = {dim: False for dim in _SEMANTIC_DIMENSIONS}
        for fact in facts:
            for dim, cfg in _SEMANTIC_DIMENSIONS.items():
                if any(kw in fact.fact for kw in cfg["l1_claims"]):
                    l1_claims[dim] = True
        l2_behaviors = {dim: [] for dim in _SEMANTIC_DIMENSIONS}
        for pat in patterns:
            text = (pat.conclusion or "") + " " + (pat.task_text or "")
            for dim, cfg in _SEMANTIC_DIMENSIONS.items():
                for kw in cfg["l2_patterns"]:
                    if kw in text:
                        l2_behaviors[dim].append(pat.conclusion or pat.task_text or "")
        for dim, cfg in _SEMANTIC_DIMENSIONS.items():
            if l1_claims[dim] and l2_behaviors[dim]:
                contradictions.append(Contradiction(
                    dimension=dim,
                    l1_claim=",".join([f.fact for f in facts if any(
                        kw in f.fact for kw in cfg["l1_claims"])][:1]) or "(claims)",
                    l2_behavior=l2_behaviors[dim][0][:30] + "..." if l2_behaviors[dim] else "(historical behavior)",
                    severity=cfg["severity"],
                    l1_weight_penalty=cfg["penalty"],
                ))
        return contradictions

    # 时间衰减
    @staticmethod
    def _apply_time_decay(items, half_life: float) -> List:
        now = datetime.datetime.now()
        result = []
        for item in items:
            ts_str = getattr(item, "last_seen", None) or getattr(item, "created_at", None) or ""
            if not ts_str:
                weight = 0.5
            else:
                try:
                    if "T" in ts_str:
                        dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    else:
                        dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    weight = 0.5
                else:
                    days = max(0, (now - dt).total_seconds() / 86400)
                    item_hl = getattr(item, "half_life_days", None)
                    if item_hl is None or item_hl == 0:
                        weight = 1.0  # 永不过期
                    else:
                        weight = math.pow(0.5, days / item_hl)
            item.recency_score = weight
            if hasattr(item, "time_weight"):
                item.time_weight = weight
            result.append(item)
        return result

    # 任务相关性过滤
    def _filter_by_task_relevance(self, items, task_text: str) -> List:
        if not items or not task_text:
            return items
        task_lower = task_text.lower()
        scored = []
        for item in items:
            item_text = (
                (getattr(item, "fact", "") or "") + " " +
                (getattr(item, "conclusion", "") or "") + " " +
                " ".join(getattr(item, "keywords", []) or []) +
                " ".join(getattr(item, "tags", []) or [])
            ).lower()
            overlap = sum(
                1 for kw in [w[:4] for w in task_lower.split() if len(w) > 2]
                if kw in item_text
            ) / max(len(task_lower.split()), 1)
            score = overlap + (getattr(item, "recency_score", 1.0) or 1.0) * 0.3
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]

    # 时间摘要
    def _time_summary(self, facts, patterns):
        now = datetime.datetime.now()
        def parse_days(ts_str):
            if not ts_str:
                return None
            try:
                if "T" in ts_str:
                    dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                return (now - dt).days
            except Exception:
                return None
        fd = [parse_days(f.last_seen or f.created_at) for f in facts]
        pd = [parse_days(p.created_at) for p in patterns]
        fd = [d for d in fd if d is not None]
        pd = [d for d in pd if d is not None]
        return {
            "oldest_fact_days": max(fd) if fd else 0,
            "newest_fact_days": min(fd) if fd else 0,
            "oldest_pattern_days": max(pd) if pd else 0,
            "newest_pattern_days": min(pd) if pd else 0,
        }


# ════════════════════════════════════════════════════════════════════════════
# L3 感知存储 — 模块级函数，供 router / experiences / perception adapters 调用
# ════════════════════════════════════════════════════════════════════════════

def _pi_conn():
    """获取 perception_intents 表连接（与 juhuo.db 同库）"""
    import sqlite3
    from pathlib import Path
    db = Path(__file__).parent.parent / "data" / "juhuo.db"
    return sqlite3.connect(str(db), timeout=10)


def save_perception_result(
    source: str,
    topic: str,
    content: str,
    url: str = "",
    priority: int = 0,
    ttl_days: int = 7,
) -> int:
    """
    存储一次感知结果到 perception_intents 表（L3 数据源）。

    调用场景：
        from judgment.user_model import save_perception_result
        save_perception_result(source="web", topic="量子计算最新进展",
                               content="...提取内容...", url="https://...")

    来源优先级：
        source=web   → 网页提取
        source=pdf   → PDF 提取
        source=rss   → RSS 订阅
        source=email → 邮件
        source=manual → 用户手动提供

    TTL：默认7天，过期后 _get_l3_intents() 自动不读。
    """
    try:
        from datetime import datetime, timedelta
        conn = _pi_conn()
        expires = (datetime.now() + timedelta(days=ttl_days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute(
            "INSERT INTO perception_intents (source, topic, content, url, priority, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source, topic, content[:2000], url, priority,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"), expires)
        )
        intent_id = cursor.lastrowid
        conn.commit()
        conn.close()
        # 自动清理过期记录（每次写入时顺带清理，随机触发1/20概率）
        import random
        if random.random() < 0.05:
            _cleanup_expired()
        return intent_id or 0
    except Exception:
        return 0


def _cleanup_expired():
    """删除已过期的 perception_intents 记录"""
    try:
        conn = _pi_conn()
        conn.execute("DELETE FROM perception_intents WHERE expires_at IS NOT NULL "
                     "AND expires_at < datetime('now')")
        conn.commit()
        conn.close()
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════════════
# UnifiedProfile — 三路 Profile 统一结构 + Self-Evolver 进化反馈
# ════════════════════════════════════════════════════════════════════════════

class UnifiedProfile:
    """三路 Profile 统一结构。priority: 1(L1主动确认)>2(L2行为推断)>3(L3被动信号)"""
    DIMENSION_KEYWORDS = {
        "cognitive":     ["思考","分析","信息","认知","判断","学习"],
        "game_theory":   ["博弈","对方","竞争","合作","谈判"],
        "economic":      ["成本","收益","金钱","财务","经济","收入","划算"],
        "dialectical":   ["矛盾","对立","两面","辩证","利弊","权衡"],
        "emotional":     ["情绪","感受","心情","焦虑","兴奋","恐惧","喜悦"],
        "intuitive":     ["直觉","第六感","感觉","本能"],
        "moral":         ["道德","责任","义务","对错","伦理"],
        "social":        ["人际","关系","社交","朋友","家人","同事"],
        "temporal":      ["时间","时机","长期","短期","未来","过去"],
        "metacognitive": ["反思","自我","元认知"],
    }

    def generate(self, ctx, task_text: str = "") -> List[ProfileEntry]:
        entries = []
        task_lower = task_text.lower()
        for f in (ctx.facts or []):
            dim = self._match_dimension(f.fact + f.category, task_lower)
            entries.append(ProfileEntry(
                source="fact", priority=1, dimension=dim, claim=f.fact,
                evidence="bio:{} conf={} imp={}".format(f.category, f.confidence, f.importance),
                confidence=f.confidence, recency_score=getattr(f, "time_weight", 1.0),
                contradiction_flag=getattr(f, "contradiction_flag", False),
                profile_id="fact:{}:{}".format(f.category, hash(f.fact) % 999999)))
        for p in (ctx.patterns or []):
            text = (p.conclusion or "") + " " + (p.task_text or "")
            dim = self._match_dimension(text, task_lower)
            out_str = " -> {}".format(p.outcome) if p.outcome else ""
            entries.append(ProfileEntry(
                source="pattern", priority=2, dimension=dim,
                claim="{}{}".format(p.conclusion, out_str),
                evidence="exp:{} kw={}".format(p.situation_type, ",".join(p.keywords[:5])),
                confidence=p.outcome_score or 0.6,
                recency_score=getattr(p, "recency_score", 1.0),
                contradiction_flag=False,
                profile_id="pattern:{}:{}".format(p.situation_type, hash(p.conclusion or '') % 999999)))
        for i in (ctx.intents or []):
            dim = self._match_dimension(i.summary + i.topic, task_lower)
            entries.append(ProfileEntry(
                source="signal", priority=3, dimension=dim,
                claim="{}: {}".format(i.topic, i.summary[:60]),
                evidence="perc:{} rel={}".format(i.source, i.relevance),
                confidence=i.relevance, recency_score=1.0,
                contradiction_flag=False,
                profile_id="signal:{}:{}".format(i.topic[:20], hash(i.summary) % 999999)))
        # 矛盾双向处理：
        #   - L1 claim vs L2 behavior → L1降priority, L2升priority
        for c_ in (ctx.contradictions or []):
            matched_fact = None
            matched_pattern = None
            for e in entries:
                if e.source == "fact" and c_.l1_claim[:20] in e.claim:
                    matched_fact = e
                # L2 behavior匹配：pattern的conclusion含L2关键词
                if e.source == "pattern":
                    for kw in _SEMANTIC_DIMENSIONS.get(c_.dimension, {}).get("l2_patterns", []):
                        if kw in e.claim:
                            matched_pattern = e
                            break
            if matched_fact:
                matched_fact.priority = 3
                matched_fact.contradiction_flag = True
            if matched_pattern:
                matched_pattern.priority = 1          # 升：行为>声称
                matched_pattern.contradiction_flag = True
        entries.sort(key=lambda x: (x.priority if not x.contradiction_flag else 99, -x.recency_score))
        return entries

    def get_for_task(self, entries: List[ProfileEntry], dimension: str = "") -> List[ProfileEntry]:
        filtered = [e for e in entries if e.dimension == dimension] if dimension else list(entries)
        filtered.sort(key=lambda x: (x.priority if not x.contradiction_flag else 99, -x.recency_score))
        return filtered

    def _match_dimension(self, text: str, task_lower: str = "") -> str:
        text_lower = text.lower()
        best, score = "cognitive", 0
        for dim, kws in self.DIMENSION_KEYWORDS.items():
            s = sum(1 for kw in kws if kw in text_lower)
            if s > score:
                score = s
                best = dim
        return best

    def to_prompt(self, entries: List[ProfileEntry], dimension: str = "") -> str:
        """
        ProfileEntry -> 结构化 prompt 文本。

        格式：[PROFILE: priority=X, source=Y, recency=Z, claim="...", flag=Z]
        - priority: 1(主动确认)>2(行为推断)>3(被动信号)
        - source: fact/pattern/signal
        - recency: 时间衰减后权重 0.0~1.0
        - flag: contra(矛盾)|ok(正常)
        """
        dim_entries = self.get_for_task(entries, dimension=dimension)
        if not dim_entries:
            return ""
        parts = []
        for e in dim_entries:
            flag_str = "contra" if e.contradiction_flag else "ok"
            parts.append(
                '[PROFILE: priority={}, source={}, recency={:.2f}, claim="{}", flag={}]'.format(
                    e.priority, e.source, e.recency_score, e.claim[:60], flag_str
                )
            )
        return "\\n".join(parts)

    def to_summary(self, entries: List[ProfileEntry]) -> str:
        if not entries:
            return "No profile data yet."
        core = [e for e in entries if e.priority == 1 and not e.contradiction_flag]
        patterns = [e for e in entries if e.source == "pattern"]
        contradictions = [e for e in entries if e.contradiction_flag]
        lines = []
        if core:
            lines.append("[User Profile]")
            for e in core[:5]:
                lines.append("  - {}".format(e.claim))
        if patterns:
            lines.append("[Behavior Patterns]")
            for e in patterns[:3]:
                lines.append("  - {}".format(e.claim))
        if contradictions:
            lines.append("[Behavioral Drift]")
            for e in contradictions[:3]:
                lines.append("  WARNING: {} (claimed vs acted)".format(e.claim))
        return "\\n".join(lines) if lines else "No profile data yet."


def update_profile_on_contradiction(contradiction: Contradiction, ctx: UnifiedContext) -> bool:
    """L1 claim 和 L2 behavior 矛盾时 -> 降低 biography fact 的 importance"""
    severity_map = {"high": 3, "medium": 2, "low": 1}
    penalty = severity_map.get(contradiction.severity, 0)
    if not penalty:
        return False
    bio_db = Path(__file__).parent.parent / "data" / "causal_memory" / "events.db"
    if not bio_db.exists():
        return False
    conn = None
    try:
        conn = sqlite3.connect(str(bio_db), timeout=10)
        conn.row_factory = sqlite3.Row
        for fact in (ctx.facts or []):
            if contradiction.l1_claim[:20] in fact.fact:
                new_imp = max(1, (fact.importance or 1) - penalty)
                tags = json.dumps(["contradiction_flagged",
                                   "contradicted_by:" + contradiction.dimension], ensure_ascii=False)
                conn.execute("UPDATE biographical_facts SET importance=?, tags=? WHERE fact=?",
                           (new_imp, tags, fact.fact))
                conn.commit()
                return True
    except Exception:
        pass
    finally:
        if conn:
            conn.close()
    return False

