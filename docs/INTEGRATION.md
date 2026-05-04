# INTEGRATION — 子系统接口与数据流

本文档描述各子系统之间的调用关系、数据格式、更新流向。

---

## 完整数据流（从输入到闭环）

```
perception/attention_filter.filter(message)
    ↓
    IncomingMessage → FilterResult {passed, priority}
    ↓
router/check10d(task_text)
    ↓
    JudgmentResult {
        task, complexity, must_check, important, skipped,
        questions, answers, conclusion,
        meta: {checked, total_dims},
        correlation_memory: {events},
    }
    ↓
correlation_memory/log_causal_event(task, result, decision)
    ↓
    Event {event_id, task, timestamp, ...} → 写入 causal_events.jsonl (快路径)
    ↓
self_model/get_self_warnings(judgment_result)
    ↓
    (warnings: List[str], strengths: List[str])
    ↓  → 注入到 judgment_result
curiosity_engine/check_triggers / add_*_trigger
    ↓
    CuriosityItem → 写入 curiosity.json
    ↓  → 优先级由 goal_system 计算对齐得分
emotion_system/detect_emotion(task_text, judgment_result)
    ↓
    EmotionSignal {is_signal, description, label}
    ↓  → 注入到 judgment_result
output_system/format_output(judgment_result, format_request)
    ↓
    str (formatted output) → 返回给用户
    ↓
action_system/generate_action_plan(judgment_result)
    ↓
    ActionPlan {actions: [NextAction]} → 写入 action_log.jsonl
    ↓  → 用户执行行动 → 标记完成
action_system/mark_action_completed(action_id, result)
    ↓
    更新行动状态 → result 写入日志
    ↓
feedback_system/add_feedback(judgment_id, event_id, text, is_correct)
    ↓
    Feedback → 写入 feedback_log.jsonl
    ↓
    1. 更新 causal_events.jsonl 对应事件加上 feedback 字段
    2. 调用 self_model/update_from_feedback → 更新已知偏差统计
    3. 如果涉及情绪信号，调用 emotion_system/update_pattern → 更新信号概率
    ↓
    闭环完成 → 下次判断因果记忆会自动召回这次结果
```

---

## 核心接口定义

### action_system → feedback_system

**行动完成反馈格式：**
```python
# 用户执行完成后调用
mark_action_completed(
    action_id: int,      # 行动ID
    result: str,         # 执行结果描述：成功/失败/学到了什么
) → bool
```

**行动数据格式（action_log.jsonl）：**
```json
{
  "action_id": 1,
  "action_text": "思考并回答：涉及哪些玩家？每个玩家的核心诉求是什么？",
  "priority": "now",        // now/tomorrow/delegate/wait
  "judgment_id": "...",     // 关联哪个判断
  "created_at": "ISO",
  "completed": false,
  "result": null or string, // 完成后写入结果
}
```

---

### feedback_system → correlation_memory / self_model / emotion_system

**更新路径：**

1. **到 correlation_memory：**
```python
# feedback_system/update_causal_event_feedback
# 直接重写 causal_events.jsonl，给对应 event 加上 feedback 字段
event["feedback"] = feedback_text
```

2. **到 self_model：**
```python
# feedback = {feedback_text, is_correct, related_event}
self_model/update_from_feedback(event)
→ 如果反馈说判断错了 → 对应维度偏差计数+1，置信度提高
→ 如果对了 → 对应维度优势计数+1
→ 保存到 self_model.json
```

3. **到 emotion_system：**
```python
# 如果反馈文字提到情绪词 + 说"这是信号"/"这不是信号"
emotion_system/update_pattern(label, is_signal)
→ pattern.total_count += 1
→ if is_signal: pattern.signal_count += 1
→ 更新 signal_probability = signal_count / total_count
→ 保存到 emotions.json
```

---

### emotion_system 数据结构 (emotions.json)

```json
{
  "patterns": {
    "anxiety": {
      "label": "anxiety",
      "trigger_context": "多个维度置信度不足",
      "total_count": 2,
      "signal_count": 1,
      "signal_probability": 0.5
    },
    "excitement": { ... },
    ...
  },
  "signals": [
    {
      "id": 1,
      "task_id": "...",
      "emotion_label": "anxiety",
      "intensity": 0.6,
      "is_signal": true,
      "description": "...",
      "created_at": "..."
    }
  ],
  "updated_at": "..."
}
```

- `patterns`: 每种情绪的**信号概率统计**——这个情绪标签出现时，**真的需要重视的概率**，反馈学习后更新
- `signals`: 历史信号记录

---

### 关键设计原则

1. **松耦合**：每个子系统只依赖接口，不侵入内部实现
2. **单向依赖**：下层不依赖上层，上层依赖下层，符合开发顺序
3. **数据持久化**：所有状态都存在 `.jsonl` 或 `.json` 文件，纯文本，易于版本控制
4. **完整闭环**：行动结果 → 反馈 → 更新底层记忆 → 下次判断自动使用，真正成长

---

## 端到端调用示例（代码）

```python
import sys
sys.path.insert(0, '.')

from perception.attention_filter import AttentionFilter, IncomingMessage
from router import check10d
from correlation_memory import log_causal_event
from self_model import get_self_warnings
from curiosity.curiosity_engine import CuriosityEngine
from goal_system.goal_system import get_goal_system
from emotion_system.emotion_system import EmotionSystem
from output_system.output_system import format_output
from action_system.action_system import generate_action_plan, mark_action_completed
from feedback_system.feedback_system import add_feedback

# 1. 信息接收过滤
af = AttentionFilter()
msg = IncomingMessage(content="...", source="github", sender="user")
filter_result = af.filter(msg)

# 2. 十维判断
result = check10d("用户问题")

# 3. 记录因果
event = log_causal_event("用户问题", result, "结论")

# 4. 自我提醒
warnings, strengths = get_self_warnings(result)

# 5. 好奇心触发
ce = CuriosityEngine()
item = ce.add_relevance_trigger(...)

# 6. 目标对齐得分
score = get_goal_system().calculate_alignment_score("topic")

# 7. 情绪检测
signal = EmotionSystem().detect_emotion("用户问题", result)

# 8. 输出给用户
output = format_output(result, "full")
print(output)

# 9. 生成行动计划
plan = generate_action_plan(result)
print(plan)

# 10. 用户完成行动，标记结果
mark_action_completed(action_id, "行动结果描述")

# 11. 用户给判断反馈
add_feedback(
    judgment_id=result["id"],
    event_id=event["event_id"],
    feedback_text="这次判断不对，因为...",
    is_correct=False,
)
# → 自动更新 correlation_memory / self_model / emotion_system
# → 闭环完成
```

---

## 更新频率

- **快路径**：每次判断/行动/反馈立即写入（不阻塞）
- **慢路径**：每日闲时批量推断（因果链接/自我模型重建），不影响实时判断

---

## 版本历史

- **2026-04-11**：统一目录结构后首次整理
