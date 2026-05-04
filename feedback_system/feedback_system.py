#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feedback_system.py — 聚活反馈记录系统
**独特核心技术（聚活独有）：双层反馈锚定**

普通反馈系统就是记个log，统计对不对就完了。聚活不是：

1. **判断层锚定** → 这次判断对不对？（对错反馈）
   - 绑定到对应因果事件
   - 更新偏差/优势统计
   - 直接更新自我模型

2. **进化层锚定** → 这次进化方向对不对？（进化反馈）
   - OpenSpace三级进化后，你觉得改得对不对？
   - 错了就回滚到父版本，保留历史快照
   - 对了就固化下来，提升置信度

**双重锚定**保证：只有你真正认可的进化才会固化，不会越进化越歪，永远对齐你的真实想法。

核心闭环：
反馈接收 → 判断层锚定 → 进化层锚定（如果是进化）→ 更新因果记忆 → 更新自我模型 → 更新情感系统 → 完成闭环
"""

# 核心区别：不只记录判断对错，还要记录进化方向对不对 → 双重锚定，永远对齐你的真实想法

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

# 文件路径
FEEDBACK_LOG_FILE = Path(__file__).parent.parent / "feedback_log.jsonl"


@dataclass
class Feedback:
    """一条反馈
    聚活独特：双层反馈锚定 → 判断层+进化层
    """
    feedback_id: int
    related_judgment_id: str      # 关联哪个判断
    related_event_id: Optional[int] # 关联哪个因果事件
    related_skill_id: Optional[str] # 关联哪个OpenSpace进化技能（进化层锚定）
    feedback_text: str             # 反馈内容
    is_correct: Optional[bool]    # 之前判断正确吗？（判断层）
    is_evolution_correct: Optional[bool] # 这次进化方向正确吗？（进化层）
    created_at: str

    def to_dict(self):
        return {
            "feedback_id": self.feedback_id,
            "related_judgment_id": self.related_judgment_id,
            "related_event_id": self.related_event_id,
            "related_skill_id": self.related_skill_id,
            "feedback_text": self.feedback_text,
            "is_correct": self.is_correct,
            "is_evolution_correct": self.is_evolution_correct,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        # 兼容旧格式
        return cls(
            feedback_id=data["feedback_id"],
            related_judgment_id=data["related_judgment_id"],
            related_event_id=data.get("related_event_id"),
            related_skill_id=data.get("related_skill_id"),
            feedback_text=data["feedback_text"],
            is_correct=data.get("is_correct"),
            is_evolution_correct=data.get("is_evolution_correct"),
            created_at=data["created_at"],
        )


def _next_feedback_id() -> int:
    """生成下一个反馈ID"""
    all_feedback = load_all_feedback()
    if not all_feedback:
        return 1
    max_id = max(f["feedback_id"] for f in all_feedback)
    return max_id + 1


def load_all_feedback() -> List[Dict]:
    """加载所有反馈"""
    if not FEEDBACK_LOG_FILE.exists():
        return []
    
    feedback = []
    with open(FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                feedback.append(json.loads(line))
            except:
                continue
    return feedback


def save_feedback(feedback: Feedback):
    """保存反馈到日志"""
    with open(FEEDBACK_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(feedback.to_dict(), ensure_ascii=False) + "\n")


def add_feedback(
    judgment_id: str,
    event_id: Optional[int],
    feedback_text: str,
    is_correct: Optional[bool] = None,
    related_skill_id: Optional[str] = None,
    is_evolution_correct: Optional[bool] = None,
) -> Feedback:
    """
    聚活独特技术：双层反馈锚定 → 判断层+进化层
    添加一条反馈 → 自动更新所有相关系统：
    - **判断层锚定**：保存反馈日志 → 更新因果记忆 → 更新自我模型 → 更新情感系统
    - **进化层锚定**：如果是OpenSpace进化反馈 → 处理回滚/固化：
      - 如果进化错了 → 回滚到父版本，保留历史快照
      - 如果进化对了 → 固化下来，提升置信度
    """
    # 创建反馈对象
    fb = Feedback(
        feedback_id=_next_feedback_id(),
        related_judgment_id=judgment_id,
        related_event_id=event_id,
        related_skill_id=related_skill_id,
        feedback_text=feedback_text,
        is_correct=is_correct,
        is_evolution_correct=is_evolution_correct,
        created_at=datetime.now().isoformat(),
    )
    save_feedback(fb)

    # ========== 第一层：判断层锚定 ==========
    # 更新因果记忆：把反馈写回对应事件
    if event_id is not None:
        update_causal_event_feedback(event_id, feedback_text)

    # 更新自我模型：根据反馈总结偏差
    update_self_model_from_feedback(fb)

    # 如果反馈涉及情绪信号判断，更新情感系统
    update_emotion_pattern_from_feedback(fb)

    # ========== 第二层：进化层锚定（聚活独特） ==========
    if related_skill_id is not None and is_evolution_correct is not None:
        process_evolution_feedback(related_skill_id, is_evolution_correct)

    return fb


def process_evolution_feedback(skill_id: str, is_correct: bool) -> bool:
    """
    聚活独特技术：进化层锚定处理
    - 正确 → 固化，提升置信度
    - 错误 → 回滚到父版本，保留历史快照
    """
    from openspace.openspace_evolution import get_skill_by_id, rollback_to_parent, confirm_evolution
    
    skill = get_skill_by_id(skill_id)
    if not skill:
        return False
    
    if is_correct:
        # 进化正确 → 固化，提升置信度
        confirm_evolution(skill_id)
        return True
    else:
        # 进化错误 → 回滚到父版本
        rollback_to_parent(skill_id)
        return True


def update_causal_event_feedback(event_id: int, feedback: str):
    """更新因果事件里的反馈字段"""
    from correlation_memoryNone import load_all_events
    from pathlib import Path
    
    CAUSAL_EVENTS_FILE = Path(__file__).parent.parent / "correlation_memory" / "causal_events.jsonl"
    
    events = load_all_events()
    updated = False
    
    # 重写整个文件（简单可靠，数据量不大）
    with open(CAUSAL_EVENTS_FILE, "w", encoding="utf-8") as f:
        for event in events:
            if event.get("event_id") == event_id:
                event["feedback"] = feedback
                updated = True
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    return updated


def update_self_model_from_feedback(feedback: Feedback):
    """更新自我模型：从反馈中学习偏差"""
    from self_model.self_model import update_from_feedback
    return update_from_feedback(feedback.to_dict())


def update_emotion_pattern_from_feedback(feedback: Feedback):
    """更新情感系统：情绪信号是不是真的"""
    # 如果反馈里提到了情绪，更新模式概率
    text = feedback.feedback_text.lower()
    is_signal = None
    emotion_label = None

    # 检测常见情绪词
    emotion_keywords = {
        "焦虑": "anxiety",
        "担心": "anxiety", 
        "兴奋": "excitement",
        "愤怒": "anger",
        "纠结": "uncertainty",
        "后悔": "regret",
    }

    for kw, label in emotion_keywords.items():
        if kw in text:
            emotion_label = label
            break

    if emotion_label is None:
        return False

    # 判断反馈说"是信号"还是"不是信号"
    if "是信号" in text or "确实" in text or "对的" in text:
        is_signal = True
    elif "不是" in text or "不对" in text or "错了" in text:
        is_signal = False

    if is_signal is not None:
        from emotion_system.emotion_system import EmotionSystem
        es = EmotionSystem()
        es.update_pattern(emotion_label, is_signal)
        return True

    return False


def format_recent_feedback(days: int = 7) -> str:
    """格式化最近N天的反馈，人类可读"""
    all_fb = load_all_feedback()
    cutoff = datetime.now().timestamp() - days * 24 * 3600

    recent = []
    for fb in all_fb:
        ts = datetime.fromisoformat(fb["created_at"]).timestamp()
        if ts >= cutoff:
            recent.append(fb)

    if not recent:
        return f"最近 {days} 天没有反馈记录。"

    lines = [f"=== 最近 {days} 天反馈 ===\n"]
    for idx, fb in enumerate(recent[-10:], 1):
        correct = ""
        if fb["is_correct"] is True:
            correct = " [判断正确]"
        elif fb["is_correct"] is False:
            correct = " [判断错误]"
        
        lines.append(f"{idx}. {fb['feedback_text'][:60]}{correct}")
        lines.append(f"   关联判断：{fb['related_judgment_id']}")
    
    return "\n".join(lines)


def get_statistics() -> Dict:
    """反馈统计"""
    all_fb = load_all_feedback()
    total = len(all_fb)
    correct = sum(1 for f in all_fb if f["is_correct"] is True)
    wrong = sum(1 for f in all_fb if f["is_correct"] is False)
    
    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "accuracy": correct / (correct + wrong) if (correct + wrong) > 0 else None,
    }


def format_statistics() -> str:
    """格式化统计信息"""
    stat = get_statistics()
    lines = ["=== 反馈统计 ===\n"]
    lines.append(f"总反馈：{stat['total']}")
    if stat['accuracy'] is not None:
        lines.append(f"判断正确率：{int(stat['accuracy'] * 100)}% ({stat['correct']}/{stat['correct'] + stat['wrong']})")
    else:
        lines.append("暂无对错标记")
    return "\n".join(lines)


# 测试
if __name__ == "__main__":
    print("反馈系统测试")
    print(format_statistics())
    print("\n最近7天反馈：")
    print(format_recent_feedback(7))
