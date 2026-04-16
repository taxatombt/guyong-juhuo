#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
curiosity_engine.py — 聚活好奇心引擎
**独特核心技术（聚活独有）：锁定兴趣域的双随机游走**

普通AI好奇心会瞎探索什么都感兴趣，聚活不是：
1. **锁定兴趣域**：只探索符合你锁定兴趣方向的话题，不跑题
   - 你的兴趣列表永久锁定（核心身份锁），可以手动修改但不能自动修改
   - 不符合锁定域的话题直接过滤，不消耗认知资源

2. **双随机游走**：
   - **目标导向游走**：80%概率走"对齐长期目标→服务当前任务→知识缺口→延伸"路径
     → 跟着目标走，大部分探索对当前系统有用
   - **自由随机游走**：20%概率走随机步，在锁定域内随便跳
     → 保留意外发现惊喜（serendipity），不完全功利，保持创造力

3. **三触发机制（聚活适配）：**
   ① 知识缺口触发 → 判断置信度低，现有知识不足以判断
   ② 未知异常触发 → 因果不匹配，预期和实际不符
   ③ 价值相关性触发 → 新话题和长期目标/锁定兴趣沾边

优先级排序（聚活规则）：
  1. 对齐长期目标 → 最高优先级
  2. 服务当前任务 → 第二优先级
  3. 锁定兴趣域自由游走 → 低优先级但每日必占一位
  4. 完全无关 → 过滤掉

输出：每日结束输出「今日好奇清单」，前三高优先级，一定留一个自由随机位
"""

# 锁定兴趣域是聚活好奇心和通用AI好奇心最大区别
# 你永远只探索你真正感兴趣的方向，不会被热点带偏，不会浪费时间

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import time  # 用于时间戳生成
import json
from pathlib import Path

# 文件路径
CURIOSITY_FILE = Path(__file__).parent.parent / "curiosity.json"
GOALS_FILE = Path(__file__).parent.parent / "goal_system" / "goals.json"
LOCKED_INTERESTS_FILE = Path(__file__).parent / "locked_interests.json"

# 双随机游走概率
WALK_TARGET_GUIDED_RATE = 0.8  # 80%目标导向，20%自由随机
SIMILARITY_THRESHOLD = 0.3  # 低于这个相似度进锁定域

# 使用目标系统计算对齐得分
import random
import difflib
from typing import List

# 锁定兴趣域是聚活独特：只读，不能自动修改（身份锁）
from goal_system.goal_system import get_goal_system

def _load_locked_interests() -> List[str]:
    """
    聚活独特技术：锁定兴趣域，加载锁定兴趣列表
    锁定兴趣域不会自动进化，必须手动修改 → 你的兴趣永远是你的兴趣
    """
    if not LOCKED_INTERESTS_FILE.exists():
        # 初始化默认锁定兴趣（根据聚活项目本身设置）
        default_interests = [
            "AI Agent", "self-evolution", "personal digital clone", "digital immortality",
            "认知科学", "心理学", "决策科学", "哲学", "科幻小说写作", "诗歌",
            "FPS游戏", "狼人杀", "编程", "设计方法论", "CoPaw开发"
        ]
        with open(LOCKED_INTERESTS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_interests, f, ensure_ascii=False, indent=2)
        return default_interests
    
    with open(LOCKED_INTERESTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def is_in_locked_domain(topic: str) -> bool:
    """
    聚活独特技术：判断话题是否在锁定兴趣域
    只要匹配到任何一个锁定兴趣相似度够高，就算在域内
    """
    locked = _load_locked_interests()
    for interest in locked:
        sim = difflib.SequenceMatcher(None, topic.lower(), interest.lower()).ratio()
        if sim >= SIMILARITY_THRESHOLD:
            return True
    return False


def max_locked_similarity(topic: str) -> float:
    """返回话题和锁定兴趣域的最大相似度"""
    locked = _load_locked_interests()
    return max(
        difflib.SequenceMatcher(None, topic.lower(), interest.lower()).ratio()
        for interest in locked
    )


def sample_random_interest_in_domain() -> str:
    """
    聚活独特技术：双随机游走 → 自由随机游走从锁定域采样一个随机兴趣
    """
    locked = _load_locked_interests()
    return random.choice(locked)


def pick_next_exploration_topic(current_topic: str) -> Tuple[str, str]:
    """
    聚活独特技术：双随机游走 → 选择下一个探索主题
    Returns:
        (topic, walk_type) where walk_type = "target_guided" or "free_random"
    """
    if random.random() < WALK_TARGET_GUIDED_RATE:
        # 目标导向游走 → 找和当前话题最接近的锁定兴趣
        locked = _load_locked_interests()
        best = max(locked, key=lambda x: difflib.SequenceMatcher(None, current_topic.lower(), x.lower()).ratio())
        return (best, "target_guided")
    else:
        # 自由随机游走 → 在锁定域内随机选一个
        return (sample_random_interest_in_domain(), "free_random")


def calculate_alignment_score(topic: str) -> float:
    """计算话题和长期目标的对齐得分（0-1）"""
    # 先检查锁定域内话题本身就是对齐长期目标（因为锁定就是你选的）
    in_domain = is_in_locked_domain(topic)
    if not in_domain:
        return 0.0  # 域外话题直接零分，不探索
    
    # 再计算和当前目标对齐
    gs = get_goal_system()
    base_score = gs.calculate_alignment_score(topic)
    # 锁定域加成
    return min(base_score + 0.2, 1.0)  # 锁定域话题本身加分


# 优先级等级
PRIORITY_HIGH = 3
PRIORITY_MEDIUM = 2
PRIORITY_LOW = 1


@dataclass
class TriggerInfo:
    """触发信息"""
    trigger_type: str  # "gap" / "anomaly" / "relevance"
    description: str


@dataclass
class CuriosityItem:
    """一条好奇心条目"""
    id: int
    question: str             # 探索问题
    topic: str               # 所属主题
    trigger: TriggerInfo     # 怎么触发的
    priority_level: int      # 3高/2中/1低（按三条规则）
    aligned_to_long_term: bool  # 是否对齐长期目标
    serves_current_task: str or None  # 服务哪个当前任务
    created_at: str
    status: str              # open / exploring / resolved / deferred
    resolved_answer: Optional[str] = None

    def to_dict(self):
        return {
            "id": self.id,
            "question": self.question,
            "topic": self.topic,
            "trigger": {
                "trigger_type": self.trigger.trigger_type,
                "description": self.trigger.description,
            },
            "priority_level": self.priority_level,
            "aligned_to_long_term": self.aligned_to_long_term,
            "serves_current_task": self.serves_current_task,
            "created_at": self.created_at,
            "status": self.status,
            "resolved_answer": self.resolved_answer,
        }

    @classmethod
    def from_dict(cls, data):
        trigger = TriggerInfo(**data["trigger"])
        return cls(
            id=data["id"],
            question=data["question"],
            topic=data["topic"],
            trigger=trigger,
            priority_level=data["priority_level"],
            aligned_to_long_term=data["aligned_to_long_term"],
            serves_current_task=data.get("serves_current_task"),
            created_at=data["created_at"],
            status=data.get("status", "open"),
            resolved_answer=data.get("resolved_answer"),
        )


def load_long_term_goals() -> List[str]:
    """加载长期目标列表，用于相关性检测"""
    if not GOALS_FILE.exists():
        # 默认长期目标（guyong-juhuo 主项目）
        default_goals = [
            "guyong-juhuo 完整模拟个体Agent系统",
            "数字永生",
            "持续学习成长",
            "超越人类思想",
            "因果记忆",
            "十维判断",
            "自我模型",
            "好奇心引擎",
        ]
        with open(GOALS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_goals, f, ensure_ascii=False, indent=2)
        return default_goals
    
    with open(GOALS_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
        # 兼容旧格式，如果是列表提取关键词
        if isinstance(data, list):
            return data
        # 新格式，从五级结构提取关键词
        keywords = []
        if "five_year" in data and "keywords" in data["five_year"]:
            keywords.extend(data["five_year"]["keywords"])
        if "annual" in data and "keywords" in data["annual"]:
            keywords.extend(data["annual"]["keywords"])
        return keywords


class CuriosityEngine:
    """好奇心引擎 最小可用"""

    def __init__(self):
        self.items: List[CuriosityItem] = []
        self.long_term_goals: List[str] = load_long_term_goals()
        self._load()

    def _deduplicate(self, items: List[CuriosityItem]) -> List[CuriosityItem]:
        """去重：question + topic 相同视为重复"""
        seen = set()
        unique = []
        for item in items:
            key = hash((item.question, item.topic))
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    def _load(self):
        if not CURIOSITY_FILE.exists():
            self._save()
            return
        
        with open(CURIOSITY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        items = [CuriosityItem.from_dict(item) for item in data]
        self.items = self._deduplicate(items)

    def _save(self):
        with open(CURIOSITY_FILE, "w", encoding="utf-8") as f:
            json.dump([item.to_dict() for item in self.items], f, ensure_ascii=False, indent=2)

    def _next_id(self) -> int:
        if not self.items:
            return 1
        return max(item.id for item in self.items) + 1

    def _calculate_priority(self, topic: str, aligned_to_long_term: bool, serves_current_task: Optional[str]) -> int:
        """
        聚活独特优先级计算（锁定兴趣域）：
        1. **域外话题直接拒绝探索** → 优先级0（不收录）
        2. 锁定域内：对齐长期目标 → HIGH
        3. 锁定域内：服务当前任务 → MEDIUM
        4. 锁定域内：自由随机 → LOW（每天必留一个位置）
        """
        # 聚活独特：域外话题直接零分，不探索，不浪费认知资源
        if not is_in_locked_domain(topic):
            return 0  # 0 → 不收录
        
        # 用目标系统再算一遍对齐得分，再确认
        score = calculate_alignment_score(topic)
        if score >= 0.5:
            return PRIORITY_HIGH
        if aligned_to_long_term:
            return PRIORITY_HIGH
        if serves_current_task is not None:
            return PRIORITY_MEDIUM
        return PRIORITY_LOW

    def _check_relevance(self, topic: str) -> bool:
        """检查话题是否和长期目标相关"""
        topic_lower = topic.lower()
        for goal in self.long_term_goals:
            if goal.lower() in topic_lower or topic_lower in goal.lower():
                return True
        return False

    # 触发点①：知识缺口
    def add_gap_trigger(self, question: str, topic: str, gap_description: str,
                       current_task: Optional[str] = None) -> CuriosityItem:
        """知识缺口触发：知道相关，但不知道具体影响→好奇"""
        aligned = self._check_relevance(topic)
        priority = self._calculate_priority(topic, aligned, current_task)
        
        # 去重：相同 question + topic 不重复添加
        existing = [i for i in self.items if i.question == question and i.topic == topic]
        if existing:
            return existing[0]
        
        item = CuriosityItem(
            id=self._next_id(),
            question=question,
            topic=topic,
            trigger=TriggerInfo(
                trigger_type="gap",
                description=gap_description,
            ),
            priority_level=priority,
            aligned_to_long_term=aligned,
            serves_current_task=current_task,
            created_at=datetime.now().isoformat(),
            status="open",
        )

        self.items.append(item)
        self._sort()
        self._save()
        return item

    # 触发点②：未知异常（因果不匹配）
    def add_anomaly_trigger(self, expected: str, actual: str, context: str,
                           current_task: Optional[str] = None) -> CuriosityItem:
        """未知异常触发：预期≠实际，好奇为什么"""
        question = f"为什么在{context}下，预期{expected}但是实际{actual}？"
        topic = context
        aligned = self._check_relevance(topic)
        priority = self._calculate_priority(topic, aligned, current_task)
        
        # 去重：相同 question + topic 不重复添加
        existing = [i for i in self.items if i.question == question and i.topic == topic]
        if existing:
            return existing[0]
        
        item = CuriosityItem(
            id=self._next_id(),
            question=question,
            topic=topic,
            trigger=TriggerInfo(
                trigger_type="anomaly",
                description=f"预期结果与实际不符: 预期 {expected}, 实际 {actual}",
            ),
            priority_level=priority,
            aligned_to_long_term=aligned,
            serves_current_task=current_task,
            created_at=datetime.now().isoformat(),
            status="open",
        )

        self.items.append(item)
        self._sort()
        self._save()
        return item

    # 触发点③：价值相关性
    def add_relevance_trigger(self, question: str, topic: str, description: str,
                             current_task: Optional[str] = None) -> CuriosityItem:
        """价值相关性触发：新话题和长期/当前目标相关→好奇"""
        aligned = self._check_relevance(topic)
        priority = self._calculate_priority(topic, aligned, current_task)
        
        # 去重：相同 question + topic 不重复添加
        existing = [i for i in self.items if i.question == question and i.topic == topic]
        if existing:
            return existing[0]
        
        item = CuriosityItem(
            id=self._next_id(),
            question=question,
            topic=topic,
            trigger=TriggerInfo(
                trigger_type="relevance",
                description=description,
            ),
            priority_level=priority,
            aligned_to_long_term=aligned,
            serves_current_task=current_task,
            created_at=datetime.now().isoformat(),
            status="open",
        )

        self.items.append(item)
        self._sort()
        self._save()
        return item

    def _sort(self):
        """按优先级降序 + 创建时间降序（同优先级新的在前）"""
        self.items.sort(key=lambda x: (-x.priority_level, x.created_at), reverse=False)

    def get_top_open(self, limit: int = 3) -> List[CuriosityItem]:
        """获取优先级最高的前N个待探索条目（默认前三，每日输出用）"""
        open_items = [item for item in self.items if item.status == "open"]
        self._sort()
        return open_items[:limit]

    def set_status(self, item_id: int, status: str, answer: Optional[str] = None) -> bool:
        """更新状态，resolved 需要答案"""
        for item in self.items:
            if item.id == item_id:
                item.status = status
                if status == "resolved" and answer:
                    item.resolved_answer = answer
                self._sort()
                self._save()
                return True
        return False

    def resolve(self, item_id: int, answer: str) -> bool:
        """解决好奇，记录答案 → 回流因果记忆，闭环完成！"""
        success = self.set_status(item_id, "resolved", answer)
        if not success:
            return False
        
        # 回流因果记忆：把探索结果作为一个事件节点写入
        from ..causal_memory.causal_memory import log_causal_event
        item = self._get_item(item_id)
        if item is not None:
            # 创建因果事件：探索了这个好奇，得到答案
            log_causal_event(
                task=item.question,
                result=f"探索完成，答案: {answer[:200]}",
                confidence=0.9,
                feedback=None,
            )
        
        return True

    def _get_item(self, item_id: int) -> Optional[CuriosityItem]:
        """获取条目"""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_daily_list(self) -> str:
        """生成「今日好奇清单」输出，每日结束用
        规则：前三高优先级 + 一定保留一个低优先级随机位置给serendipity
        """
        today = datetime.now().date()
        today_items = [
            item for item in self.items
            if datetime.fromisoformat(item.created_at).date() == today
            and item.status == "open"
        ]
        
        # 分堆：高优先级 + 低优先级
        high_items = [item for item in today_items if item.priority_level >= 2]
        low_items = [item for item in today_items if item.priority_level < 2]
        
        lines = [f"今日好奇清单 — {today.isoformat()}\n"]
        
        if not today_items:
            lines.append("（今日没有新好奇心）")
            return "\n".join(lines)
        
        # 取高优先级前两个，如果还有低优先级，留第三个位置给随机低优先级（serendipity）
        result_items = high_items[:2]
        if len(result_items) < 3 and low_items:
            # 随机选一个低优先级作为今日惊喜
            import random
            random_item = random.choice(low_items)
            result_items.append(random_item)
        elif len(high_items) >= 3:
            result_items = high_items[:3]
        
        for idx, item in enumerate(result_items, 1):
            level_name = {3: "[高]", 2: "[中]", 1: "[低] (随机好奇位)"}[item.priority_level]
            trigger_type = {
                "gap": "知识缺口",
                "anomaly": "未知异常",
                "relevance": "价值相关",
            }[item.trigger.trigger_type]
            
            lines.append(f"{idx}. {level_name} {item.question}")
            lines.append(f"   - 触发：{trigger_type} — {item.trigger.description}")
            if item.aligned_to_long_term:
                lines.append(f"   - 对齐长期目标guyong-juhuo")
            if item.serves_current_task:
                lines.append(f"   - 服务当前任务：{item.serves_current_task}")
            lines.append("")
        
        remaining = len(today_items) - len(result_items)
        if remaining > 0:
            lines.append(f"...还有 {remaining} 条待探索")
        
        stats = self.stats()
        lines.append(f"统计：累计 {stats['total']} 条，{stats['open']} 条待探索，{stats['resolved']} 条已解决")
        return "\n".join(lines)

    def stats(self) -> Dict:
        return {
            "total": len(self.items),
            "open": sum(1 for i in self.items if i.status == "open"),
            "exploring": sum(1 for i in self.items if i.status == "exploring"),
            "resolved": sum(1 for i in self.items if i.status == "resolved"),
            "deferred": sum(1 for i in self.items if i.status == "deferred"),
            "by_trigger": {
                "gap": sum(1 for i in self.items if i.trigger.trigger_type == "gap"),
                "anomaly": sum(1 for i in self.items if i.trigger.trigger_type == "anomaly"),
                "relevance": sum(1 for i in self.items if i.trigger.trigger_type == "relevance"),
            }
        }

    def full_report(self) -> str:
        """完整报告"""
        open_items = [item for item in self.items if item.status == "open"]
        stats = self.stats()
        
        lines = [f"好奇心引擎完整报告\n累计 {stats['total']} 条，{stats['open']} 条待探索\n"]
        
        if not open_items:
            lines.append("（没有待探索条目）")
            return "\n".join(lines)
        
        lines.append("### 待探索（按优先级排序）")
        for item in open_items:
            level_name = {3: "[H]", 2: "[M]", 1: "[L]"}[item.priority_level]
            lines.append(f"{level_name} [{item.trigger.trigger_type}] {item.question}")
        
        return "\n".join(lines)


# 接入判断系统：低置信度自动触发缺口
def trigger_from_verdict(chain_id: str, task_text: str, correct: bool,
                          pad_state: Optional[Dict[str, float]] = None,
                          changes: Optional[Dict] = None) -> Optional[CuriosityItem]:
    """
    事后验证触发 → 情绪驱动好奇心探索频率增加。

    PAD 高激活（A > 0.7）时，增加自由随机游走概率：
      - 判断错了 + 高激活 → "为什么我想错了？"（系统反思）
      - 判断对了 + 高激活 → "下次如何更好？"（优化探索）
      - 低激活 → 不额外触发

    由 closed_loop.receive_verdict() 在信念更新后调用。
    """
    arousal = (pad_state or {}).get("A", 0.5)

    if arousal <= 0.55:
        return None  # 激活度不够，不触发

    # 根据正确性和激活度构建探索问题
    if not correct and arousal > 0.7:
        # 错了 + 高激活：深度反思为什么错
        topic = _extract_topic_from_task(task_text)
        question = (
            f"Verdict wrong (chain={chain_id}). "
            f"Why did I misjudge this? What pattern do these mistakes share?"
        )
        trigger_type = "emotion_anomaly"
        priority = round(0.5 + arousal * 0.4, 3)
    elif correct and arousal > 0.75:
        # 正确但很激动：探索如何进一步优化
        topic = _extract_topic_from_task(task_text)
        question = (
            f"Verdict correct (chain={chain_id}). "
            f"How could this judgment be even better next time?"
        )
        trigger_type = "emotion_optimize"
        priority = round(0.3 + arousal * 0.3, 3)
    else:
        return None

    # 临时提升自由探索概率（全局状态）
    global _pad_arousal_boost
    _pad_arousal_boost = arousal

    item = _build_verdict_curiosity_item(
        question=question,
        topic=topic or "judgment_self_reflection",
        trigger_type=trigger_type,
        priority=priority,
        chain_id=chain_id,
    )
    return item


def _extract_topic_from_task(task_text: str) -> Optional[str]:
    """从任务文本中提取探索主题关键词"""
    if not task_text:
        return None
    interest_keywords = [
        "工作", "职业", "创业", "辞职", "跳槽", "offer",
        "人际关系", "亲密关系", "家庭", "朋友",
        "投资", "理财", "赚钱", "财务",
        "学习", "成长", "目标", "规划",
        "AI", "agent", "技术", "产品",
    ]
    for kw in interest_keywords:
        if kw in task_text:
            return kw
    return task_text[:10].strip()


def _build_verdict_curiosity_item(question: str, topic: str,
                                   trigger_type: str, priority: float,
                                   chain_id: str) -> CuriosityItem:
    """构建一条 verdict 触发的 curiosity 条目"""
    trigger = TriggerInfo(
        trigger_type=trigger_type,
        description=f"verdict_emotional A>0.7 chain={chain_id}",
    )
    return CuriosityItem(
        id=int(time.time() * 1000) % 1000000,
        question=question,
        topic=topic,
        trigger=trigger,
        priority_level=2,  # medium-high for emotional triggers
        aligned_to_long_term=False,
        serves_current_task=None,
        created_at=datetime.now().isoformat(),
        status="open",
    )


# ── PAD arousal 全局增强状态（下次 get_daily_list 时读取）───────────────
_pad_arousal_boost: float = 0.0


def get_pad_arousal_boost() -> float:
    """返回当前 PAD 激活度增强值（消费后重置）"""
    global _pad_arousal_boost
    val = _pad_arousal_boost
    _pad_arousal_boost = 0.0
    return val


def trigger_from_low_confidence(judgment_result, current_task=None) -> Optional[CuriosityItem]:
    """
    判断结果置信度低 → 自动触发好奇心缺口
    调用位置：judgment.router 最后
    """
    avg_conf = judgment_result.get("average_confidence", 0.5)
    if avg_conf >= 0.5:
        return None
    
    engine = CuriosityEngine()
    low_dims = [d for d, c in judgment_result.get("dim_confidence", {}).items() if c < 0.5]
    if not low_dims:
        return None
    
    question = f"补充哪些{', '.join(low_dims)}维度信息可以提高判断置信度？"
    topic = judgment_result.get("original_task", "")[:60]
    description = f"判断置信度平均 {avg_conf:.2f}，{len(low_dims)} 个维度信息不足"
    
    return engine.add_gap_trigger(
        question=question,
        topic=topic,
        gap_description=description,
        current_task=current_task,
    )


# P1改进：判断塑造好奇心
def evolve_from_judgment(judgment_result) -> None:
    """
    P1改进：判断结果反哺好奇心引擎
    
    判断完成后，根据判断结果调整好奇心优先级：
    - 高权重维度的缺口 → 提高探索优先级
    - 低置信度维度 → 触发新的好奇项
    """
    engine = CuriosityEngine()
    
    weights = judgment_result.get("weights", {})
    dim_confidence = judgment_result.get("dim_confidence", {})
    task = judgment_result.get("original_task", "")[:60]
    
    # 高权重但低置信度的维度 → 提高探索优先级
    for dim_id, weight in weights.items():
        conf = dim_confidence.get(dim_id, 0.5)
        if weight > 0.3 and conf < 0.5:
            # 这个维度权重高但置信度低，应该多探索
            question = f"深入了解{dim_id}维度，提高{conf:.0%}→70%+置信度"
            engine.add_gap_trigger(
                question=question,
                topic=task,
                gap_description=f"权重{weight:.2f}但置信度仅{conf:.2f}",
                priority="high" if weight > 0.5 else "normal"
            )


# P1改进：好奇心驱动判断
def get_context_for_judgment(task_text: str) -> str:
    """
    P1改进：为判断提供好奇上下文
    
    在判断前，查询好奇心引擎中与当前任务相关的高优先级议题
    作为额外上下文注入判断
    """
    engine = CuriosityEngine()
    
    # 获取与当前任务相关的开放好奇项
    related_items = []
    for item in engine.get_top_open(limit=3):
        # 简单相关性：任务文本包含好奇项的关键词
        if any(kw in task_text.lower() for kw in item.topic.lower().split()):
            related_items.append(item)
    
    if not related_items:
        return ""
    
    # 构造好奇上下文
    context_parts = ["[好奇驱动] 相关开放议题："]
    for item in related_items[:2]:
        context_parts.append(f"- {item.topic}: {item.question}")
    
    return "\n".join(context_parts)


# 接入因果记忆：因果不匹配自动触发异常
def trigger_from_causal_mismatch(context: str, expected: str, actual: str, current_task=None) -> CuriosityItem:
    """预期因果结果不符 → 自动触发异常好奇"""
    engine = CuriosityEngine()
    return engine.add_anomaly_trigger(
        expected=expected,
        actual=actual,
        context=context,
        current_task=current_task,
    )


def get_top_open(engine: CuriosityEngine, limit: int = 10):
    """顶层接口：获取优先级最高的前 N 个待探索议题"""
    return engine.get_top_open(limit)


def resolve(engine: CuriosityEngine, item_id: int, conclusion: str):
    """顶层接口：标记议题已解决"""
    return engine.resolve(item_id, conclusion)


def get_daily_list(engine: CuriosityEngine):
    """顶层接口：获取今日新增议题"""
    return engine.get_daily_list()


def full_report(engine: CuriosityEngine):
    """顶层接口：生成完整报告"""
    return engine.full_report()


# 测试
if __name__ == "__main__":
    engine = CuriosityEngine()
    print(engine.get_daily_list())
    print("\n=== 测试添加 ===")
    
    # 测试缺口触发（对齐长期目标）
    engine.add_gap_trigger(
        question="MAGMA的图遍历具体怎么实现高效相似搜索？",
        topic="guyong-juhuo 因果记忆",
        gap_description="知道需要相似搜索，但不知道MAGMA具体实现细节",
        current_task="实现因果记忆快慢双流",
    )
    
    # 测试异常触发（服务当前任务）
    engine.add_anomaly_trigger(
        expected="GitHub推送成功",
        actual="连接重置超时",
        context="推送 guyong-juhuo 代码",
        current_task="完善好奇心引擎",
    )
    
    print(engine.get_daily_list())
