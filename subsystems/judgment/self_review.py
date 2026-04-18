#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
self_review.py — 聚活自我复盘系统

对齐终极目标：让数字分身记住你的错误，不重复踩坑。

## 两大核心功能

### 1. 教训记录（Lesson Record）
每次判断后，如果收到反馈，自动提取教训：
- 判断对了：强化对应的维度置信度
- 判断错了：记录教训，更新 self_model 的 bias

### 2. 漏用检测（Missed Dimension Detection）
启发式检测：给定任务关键词，推断"这次本该重点看哪些维度但没看"。

判断关键词 → 对应维度建议：
| 任务关键词 | 建议维度 |
|-----------|---------|
| 验证/测试/commit | metacognitive, cognitive |
| exec/bash/命令 | cognitive, moral（安全底线）|
| 待办/任务/计划 | temporal, cognitive |
| 复盘/总结/反思 | metacognitive, moral |
| 风险/危险/不确定 | game_theory, emotional |
| 赚钱/成本/投入 | economic, temporal |
| 人际/关系/合作 | social, game_theory |
| 创作/设计/直觉 | intuitive, emotional |
| 学习/研究/调研 | cognitive, curiosity |

### 3. 3次触发确认升级机制
- 同类错误 1-2次 → 普通追踪
- 同类错误 3次 → [PATTERN×3] 标记，询问用户是否升级为永久规则
- 用户确认 → 写入教训记录，永久生效

## 数据文件
- `judgment_data/self_review_records.jsonl` — 每次复盘记录
- `judgment_data/lessons.json` — 提取的教训（最新50条）
- `judgment_data/pattern_alerts.jsonl` — 触发确认升级的记录

## 使用方式
```python
from judgment.self_review import SelfReviewSystem

sr = SelfReviewSystem()

# 判断后自动复盘
sr.review_after_judgment(
    judgment_id="xxx",
    task_text="要不要辞职创业",
    judgment_result={...},  # check10d 的输出
    feedback_text="我最终选了B，你分析得对",  # 可选
    feedback_correct=True   # 可选
)

# 获取相关教训（下次判断前调用）
lessons = sr.get_relevant_lessons(task_text)
# -> [{"dimension": "cognitive", "lesson": "...", "confidence": 0.8}, ...]

# 检查是否需要升级为永久规则
alerts = sr.check_pattern_alerts()
# -> [{"pattern": "创业决策", "count": 3, "suggestion": "..."}]
```
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from collections import defaultdict

# ============ 路径配置 ============
JUDGMENT_DATA = Path(__file__).parent.parent / "data" / "judgment_data"
RECORDS_FILE = JUDGMENT_DATA / "self_review_records.jsonl"
LESSONS_FILE = JUDGMENT_DATA / "lessons.json"
PATTERNS_FILE = JUDGMENT_DATA / "pattern_alerts.jsonl"

# 确保目录存在
JUDGMENT_DATA.mkdir(parents=True, exist_ok=True)


# ============ 教训类型定义 ============

@dataclass
class LessonRecord:
    """单条教训"""
    lesson_id: str
    judgment_id: str          # 来自哪个判断
    task_text: str             # 任务文本（脱敏）
    dimension: str             # 涉及的维度
    lesson_type: str           # "correct" | "wrong" | "missed"
    lesson_text: str            # 教训内容
    confidence: float          # 教训置信度 0-1
    times_applied: int = 0     # 被应用次数
    last_applied: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return LessonRecord(**d)


@dataclass
class PatternAlert:
    """PATTERN×N 升级警告"""
    pattern_key: str           # 模式标识（如"创业决策_经济维度"）
    pattern_summary: str        # 人类可读描述
    dimension: str
    count: int                 # 同类错误次数
    threshold: int = 3         # 触发阈值
    status: str = "pending"     # "pending" | "confirmed" | "dismissed"
    related_lessons: List[str] = field(default_factory=list)
    confirmed_rule: Optional[str] = None  # 确认后写入的规则
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return PatternAlert(**d)


# ============ 漏用维度检测 ============

# 启发式：任务关键词 → 建议维度
DIMENSION_HINTS = {
    "cognitive": [
        "分析", "思考", "认知", "假设", "事实", "证据",
        "验证", "测试", "判断", "推理", "逻辑",
    ],
    "game_theory": [
        "玩家", "对手", "合作", "竞争", "策略", "均衡",
        "博弈", "激励", "诉求", "利益",
    ],
    "economic": [
        "成本", "收益", "代价", "投入", "回报", "划算",
        "赚钱", "机会成本", "边际", "利润", "亏损",
        "创业", "辞职",
    ],
    "dialectical": [
        "矛盾", "对立", "变化", "主要", "次要", "实际",
        "现实", "矛盾", "转化",
    ],
    "emotional": [
        "焦虑", "恐惧", "开心", "愤怒", "情绪", "感受",
        "直觉", "害怕", "兴奋", "担心",
    ],
    "intuitive": [
        "直觉", "第一反应", "感觉", "经验", "模式", "身体",
    ],
    "moral": [
        "应该", "原则", "底线", "公正", "道德", "伦理",
        "对错", "责任",
    ],
    "social": [
        "群体", "他人", "社会", "关系", "人际", "认同",
        "压力", "独立",
    ],
    "temporal": [
        "长期", "短期", "五年", "未来", "复利", "后悔",
        "坚持", "放弃", "辞职",
    ],
    "metacognitive": [
        "反思", "复盘", "总结", "校准", "思考", "元认知",
        "自己", "我的判断", "辞职",
    ],
}


def detect_task_dimensions(task_text: str) -> List[Tuple[str, float]]:
    """从任务文本推断应该关注哪些维度

    返回: [(dimension_id, confidence), ...]，按 confidence 排序
    """
    text_lower = task_text.lower()
    scores = {}

    for dim_id, keywords in DIMENSION_HINTS.items():
        score = 0.0
        for kw in keywords:
            if kw in text_lower:
                score += 1.0
        if score > 0:
            # 归一化：关键词命中越多，confidence 越高
            confidence = min(1.0, score / max(len(keywords) * 0.3, 1))
            scores[dim_id] = confidence

    # 按 confidence 排序
    sorted_dims = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_dims


# ============ 自我复盘系统 ============

class SelfReviewSystem:
    """
    教训记录 + 漏用检测 + PATTERN×N 升级机制
    """

    def __init__(self):
        self._ensure_files()
        self._pattern_counts = self._load_pattern_counts()

    def _ensure_files(self):
        """确保数据文件存在"""
        JUDGMENT_DATA.mkdir(parents=True, exist_ok=True)
        if not RECORDS_FILE.exists():
            RECORDS_FILE.write_text("", encoding="utf-8")
        if not LESSONS_FILE.exists():
            self._save_lessons({})
        if not PATTERNS_FILE.exists():
            PATTERNS_FILE.write_text("", encoding="utf-8")

    def _save_lessons(self, lessons: Dict[str, List]):
        """保存教训到文件（保留最新50条）"""
        # 只保留最近50条
        all_lessons = []
        for dim_lessons in lessons.values():
            all_lessons.extend(dim_lessons)
        all_lessons.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        trimmed = all_lessons[:50]
        LESSONS_FILE.write_text(
            json.dumps(trimmed, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _load_lessons(self) -> Dict[str, List]:
        """加载教训（按维度索引）"""
        if not LESSONS_FILE.exists():
            return {}
        try:
            data = json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
            by_dim = defaultdict(list)
            for lesson in data:
                by_dim[lesson.get("dimension", "unknown")].append(lesson)
            return by_dim
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _load_pattern_counts(self) -> Dict[str, int]:
        """加载模式计数"""
        if not PATTERNS_FILE.exists():
            return {}
        try:
            lines = PATTERNS_FILE.read_text(encoding="utf-8").strip().splitlines()
            counts = {}
            for line in lines:
                try:
                    alert = json.loads(line)
                    counts[alert["pattern_key"]] = alert["count"]
                except json.JSONDecodeError:
                    continue
            return counts
        except FileNotFoundError:
            return {}

    def _record_to_file(self, record: dict):
        """追加记录到文件"""
        with open(RECORDS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _save_alert(self, alert: PatternAlert):
        """保存/更新 PATTERN 警告"""
        lines = []
        found = False
        if PATTERNS_FILE.exists():
            for line in PATTERNS_FILE.read_text(encoding="utf-8").strip().splitlines():
                if not line.strip():
                    continue
                try:
                    a = json.loads(line)
                    if a["pattern_key"] == alert.pattern_key:
                        lines.append(json.dumps(alert.to_dict(), ensure_ascii=False))
                        found = True
                    else:
                        lines.append(line)
                except json.JSONDecodeError:
                    continue
        if not found:
            lines.append(json.dumps(alert.to_dict(), ensure_ascii=False))
        PATTERNS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- 公开接口 ----

    def review_after_judgment(
        self,
        judgment_id: str,
        task_text: str,
        judgment_result: dict,
        feedback_text: Optional[str] = None,
        feedback_correct: Optional[bool] = None,
    ) -> dict:
        """
        判断后自动复盘。

        Args:
            judgment_id: 判断ID
            task_text: 原始任务文本
            judgment_result: check10d 的完整输出
            feedback_text: 用户反馈文本（可选）
            feedback_correct: 反馈是否正确（可选）

        Returns:
            {
                "recorded": True,
                "lessons_extracted": [...],
                "missed_dimensions": [...],
                "pattern_alert": None | PatternAlert,
            }
        """
        # 1. 提取这次判断激活了哪些维度
        activated_dims = set()
        if "dimension_results" in judgment_result:
            for dr in judgment_result["dimension_results"]:
                if dr.get("answered", False):
                    activated_dims.add(dr.get("dimension", "unknown"))

        # 2. 检测漏用维度
        suggested = detect_task_dimensions(task_text)
        missed = []
        for dim_id, conf in suggested:
            if conf >= 0.3 and dim_id not in activated_dims:
                missed.append({"dimension": dim_id, "confidence": conf})

        # 3. 处理反馈
        lessons_extracted = []
        if feedback_correct is not None or feedback_text:
            lesson_type = "correct" if feedback_correct else "wrong"
            lesson_text = self._extract_lesson_text(
                task_text, feedback_text, feedback_correct, judgment_result
            )

            # 提取主要涉及的维度
            primary_dim = "cognitive"
            if "dimension_results" in judgment_result:
                for dr in judgment_result["dimension_results"]:
                    if dr.get("answered", False):
                        primary_dim = dr.get("dimension", primary_dim)
                        break

            lesson_id = hashlib.md5(
                f"{judgment_id}{primary_dim}{datetime.now().isoformat()}".encode()
            ).hexdigest()[:12]

            lesson = LessonRecord(
                lesson_id=lesson_id,
                judgment_id=judgment_id,
                task_text=task_text[:100],
                dimension=primary_dim,
                lesson_type=lesson_type,
                lesson_text=lesson_text,
                confidence=0.8 if feedback_correct else 0.9,
            )

            # 保存教训
            all_lessons = self._load_lessons()
            all_lessons[primary_dim].append(lesson.to_dict())
            self._save_lessons(all_lessons)
            lessons_extracted.append(lesson.to_dict())

            # 4. PATTERN×N 检测（非正确反馈才计数）
            if not feedback_correct:
                pattern_key = self._make_pattern_key(task_text, primary_dim)
                self._pattern_counts[pattern_key] = self._pattern_counts.get(pattern_key, 0) + 1

                if self._pattern_counts[pattern_key] >= 3:
                    alert = PatternAlert(
                        pattern_key=pattern_key,
                        pattern_summary=self._summarize_pattern(task_text),
                        dimension=primary_dim,
                        count=self._pattern_counts[pattern_key],
                        status="pending",
                    )
                    self._save_alert(alert)
                else:
                    alert = None
            else:
                alert = None

        else:
            alert = None

        # 5. 记录复盘本身
        record = {
            "judgment_id": judgment_id,
            "task_text": task_text[:100],
            "activated_dims": list(activated_dims),
            "missed_dims": missed,
            "feedback": feedback_text,
            "feedback_correct": feedback_correct,
            "lessons_extracted": lessons_extracted,
            "reviewed_at": datetime.now().isoformat(),
        }
        self._record_to_file(record)

        return {
            "recorded": True,
            "lessons_extracted": lessons_extracted,
            "missed_dimensions": missed,
            "pattern_alert": alert.to_dict() if alert else None,
        }

    def _extract_lesson_text(
        self,
        task_text: str,
        feedback_text: Optional[str],
        feedback_correct: Optional[bool],
        judgment_result: dict,
    ) -> str:
        """从反馈中提取教训文本"""
        if feedback_text:
            if feedback_correct:
                return f"判断正确。反馈：{feedback_text[:80]}"
            else:
                return f"判断有误。反馈：{feedback_text[:80]}"
        return "从判断结果中提取"

    def _make_pattern_key(self, task_text: str, dimension: str) -> str:
        """生成模式标识"""
        # 简化版：取任务文本前20字 + 维度
        key_text = task_text[:20].strip()
        return f"{key_text}_{dimension}"

    def _summarize_pattern(self, task_text: str) -> str:
        """生成人类可读的模式描述"""
        return f"同类决策重复出现：{task_text[:30]}..."

    def get_relevant_lessons(
        self,
        task_text: str,
        top_k: int = 5,
    ) -> List[dict]:
        """
        根据当前任务获取相关教训。

        Returns:
            [{"dimension": "cognitive", "lesson": "...", "confidence": 0.8, "times_applied": 2}, ...]
        """
        suggested = detect_task_dimensions(task_text)
        all_lessons = self._load_lessons()

        results = []
        for dim_id, conf in suggested:
            if dim_id in all_lessons:
                for lesson in all_lessons[dim_id][-3:]:  # 每个维度最多取3条
                    results.append({
                        "dimension": dim_id,
                        "lesson": lesson.get("lesson_text", ""),
                        "confidence": lesson.get("confidence", 0.5) * conf,
                        "times_applied": lesson.get("times_applied", 0),
                        "lesson_type": lesson.get("lesson_type", "unknown"),
                    })

        # 按 confidence 排序
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:top_k]

    def check_pattern_alerts(self, status: str = "pending") -> List[dict]:
        """
        检查需要升级确认的 PATTERN 警告。

        Returns:
            [{"pattern_key": "...", "count": 3, "suggestion": "...", "dimension": "..."}]
        """
        if not PATTERNS_FILE.exists():
            return []
        try:
            lines = PATTERNS_FILE.read_text(encoding="utf-8").strip().splitlines()
            alerts = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    a = json.loads(line)
                    if a.get("status", "") == status:
                        alerts.append(a)
                except json.JSONDecodeError:
                    continue
            return alerts
        except FileNotFoundError:
            return []

    def confirm_pattern(self, pattern_key: str, confirmed_rule: str) -> bool:
        """
        用户确认 PATTERN 升级。

        将指定 pattern 标记为 confirmed，并写入 confirmed_rule。
        """
        if not PATTERNS_FILE.exists():
            return False
        try:
            lines = PATTERNS_FILE.read_text(encoding="utf-8").strip().splitlines()
            updated = []
            found = False
            for line in lines:
                if not line.strip():
                    continue
                try:
                    a = json.loads(line)
                    if a["pattern_key"] == pattern_key:
                        a["status"] = "confirmed"
                        a["confirmed_rule"] = confirmed_rule
                        a["updated_at"] = datetime.now().isoformat()
                        found = True
                    updated.append(json.dumps(a, ensure_ascii=False))
                except json.JSONDecodeError:
                    continue
            if found:
                PATTERNS_FILE.write_text("\n".join(updated) + "\n", encoding="utf-8")
            return found
        except FileNotFoundError:
            return False

    def dismiss_pattern(self, pattern_key: str) -> bool:
        """用户拒绝 PATTERN 升级"""
        if not PATTERNS_FILE.exists():
            return False
        try:
            lines = PATTERNS_FILE.read_text(encoding="utf-8").strip().splitlines()
            updated = []
            found = False
            for line in lines:
                if not line.strip():
                    continue
                try:
                    a = json.loads(line)
                    if a["pattern_key"] == pattern_key:
                        a["status"] = "dismissed"
                        a["updated_at"] = datetime.now().isoformat()
                        found = True
                    updated.append(json.dumps(a, ensure_ascii=False))
                except json.JSONDecodeError:
                    continue
            if found:
                PATTERNS_FILE.write_text("\n".join(updated) + "\n", encoding="utf-8")
            return found
        except FileNotFoundError:
            return False

    def get_missed_dimension_warning(
        self,
        task_text: str,
        activated_dims: List[str],
    ) -> Optional[str]:
        """
        生成漏用维度警告（用于判断前提示）。

        Returns:
            警告文本，或 None（无警告）
        """
        suggested = detect_task_dimensions(task_text)
        high_conf_missed = [
            dim for dim, conf in suggested
            if conf >= 0.5 and dim not in activated_dims
        ]
        if not high_conf_missed:
            return None

        dim_names = {
            "cognitive": "认知分析",
            "game_theory": "博弈策略",
            "economic": "经济成本",
            "dialectical": "辩证思维",
            "emotional": "情绪信号",
            "intuitive": "直觉判断",
            "moral": "道德底线",
            "social": "社会影响",
            "temporal": "时间维度",
            "metacognitive": "元认知",
        }
        names = [dim_names.get(d, d) for d in high_conf_missed]
        return f"⚠️ 漏用提醒：任务关键词建议关注 [{'/'.join(names)}]，但本次判断未激活"



