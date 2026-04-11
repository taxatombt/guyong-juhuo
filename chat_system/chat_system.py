#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chat_system — 聚活个人对话聊天系统

独特设计：
- 固定单用户使用（只为一个人生成数字分身）
- 完整对话历史持久化存储为文件
- 自动分析对话，触发相应功能模块：
  收到问题 → 自动触发十维判断
  发现知识缺口 → 自动触发好奇心引擎记录
  对话结束 → 自动生成行动规划 → 输出行动信号
- 定时自动进化 → 每日基于对话分析，建议进化
- 所有对话都保存为文件，保留完整思考轨迹
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from dataclasses import dataclass, field

# 导入聚活各个模块
import sys
import os
# 确保能找到上级目录的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router import check10d, format_report
from router import check10d as full_check10d
from action_system.action_system import generate_action_plan, format_action_plan
from action_signal import generate_action_signals, format_for_robot, save_to_file
from curiosity.curiosity_engine import CuriosityEngine, trigger_from_low_confidence
from goal_system.goal_system import get_goal_system
from causal_memory.causal_memory import log_causal_event, recall_causal_history
from feedback_system.feedback_system import add_feedback
from openspace import suggest_evolution, get_stats
from llm_adapter import get_adapter


# ── 类型定义 ───────────────────────────────────────────────────────────

class MessageRole(str):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    """单条聊天消息"""
    message_id: str
    role: str  # user/assistant/system
    content: str
    timestamp: str
    metadata: Dict = field(default_factory=dict)
    """
    metadata 可包含：
    - judgment_result: 十维判断结果
    - action_plan: 行动规划结果
    - action_signal: 行动信号JSON
    - triggered_functions: 触发了哪些功能
    """
    
    def to_dict(self):
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class ChatSession:
    """一个聊天会话"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[ChatMessage] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def add_message(self, message: ChatMessage):
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data):
        session = cls(
            session_id=data["session_id"],
            title=data["title"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            metadata=data.get("metadata", {}),
        )
        session.messages = [ChatMessage.from_dict(m) for m in data["messages"]]
        return session


# ── 主聊天系统 ───────────────────────────────────────────────────────────

CHAT_DIR = Path("chat_history")
CURRENT_SESSION_FILE = Path("current_session.json")


class ChatSystem:
    """聚活个人对话聊天系统
    
    只为固定单用户设计，所有对话持久化存储
    """
    
    def __init__(self, username: str = "default"):
        self.username = username
        self.current_session: Optional[ChatSession] = None
        self.curiosity_engine = CuriosityEngine()
        self.goal_system = get_goal_system()
        self.llm_adapter = get_adapter()  # 可选，用于自动进化
        
        # 确保目录存在
        CHAT_DIR.mkdir(exist_ok=True, parents=True)
    
    def create_session(self, title: str) -> ChatSession:
        """创建新会话"""
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        session = ChatSession(
            session_id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        self.current_session = session
        self._save_current_session()
        self._save_session_to_file(session)
        return session
    
    def add_user_message(self, content: str) -> ChatMessage:
        """添加用户消息"""
        if self.current_session is None:
            # 创建默认会话
            title = content[:30] + ("..." if len(content) > 30 else "")
            self.create_session(title)
        
        msg = ChatMessage(
            message_id=str(uuid.uuid4())[:8],
            role=MessageRole.USER,
            content=content,
            timestamp=datetime.now().isoformat(),
        )
        self.current_session.add_message(msg)
        self._save_current_session()
        self._save_session_to_file(self.current_session)
        return msg
    
    def add_assistant_message(
        self,
        content: str,
        judgment_result = None,
        action_plan = None,
        action_signal = None,
        triggered: List[str] = None,
    ) -> ChatMessage:
        """添加助手消息"""
        metadata = {}
        if judgment_result is not None:
            metadata["judgment_result"] = judgment_result
        if action_plan is not None:
            metadata["action_plan"] = [a.to_dict() for a in action_plan.items]
        if action_signal is not None:
            metadata["action_signal"] = action_signal
        if triggered is not None:
            metadata["triggered_functions"] = triggered
        
        msg = ChatMessage(
            message_id=str(uuid.uuid4())[:8],
            role=MessageRole.ASSISTANT,
            content=content,
            timestamp=datetime.now().isoformat(),
            metadata=metadata,
        )
        self.current_session.add_message(msg)
        self._save_current_session()
        self._save_session_to_file(self.current_session)
        return msg
    
    def process_user_message(
        self,
        content: str,
        auto_trigger: bool = True,
    ) -> Tuple[str, Dict]:
        """
        处理用户消息，自动触发各个功能：
        1. 添加用户消息
        2. 十维判断
        3. 生成行动规划
        4. 生成行动信号
        5. 自动检测低置信度 → 触发好奇心
        6. 记录因果事件
        7. 返回完整回答
        """
        # 1. 添加用户消息
        self.add_user_message(content)
        
        triggered = []
        result = {}
        
        # 2. 十维判断
        judgment = full_check10d(content)
        report = format_report(judgment)
        triggered.append("judgment")
        result["judgment"] = judgment
        result["report"] = report
        
        # 3. 生成行动规划
        action_plan = generate_action_plan(content, judgment)
        action_report = format_action_plan(action_plan)
        triggered.append("action_plan")
        result["action_plan"] = action_plan
        result["action_report"] = action_report
        
        # 4. 生成行动信号（给机器人）
        from action_signal import generate_action_signals
        signals = generate_action_signals(action_plan, self.current_session.session_id)
        robot_json = format_for_robot(signals)
        triggered.append("action_signal")
        result["action_signals"] = signals
        result["robot_json"] = robot_json
        
        # 5. 自动检测低置信度 → 触发好奇心
        if auto_trigger and self.llm_adapter:
            from curiosity.curiosity_engine import trigger_from_low_confidence
            low_confidence_dims = [
                d for d in judgment["dimensions"]
                if d.get("confidence", 1.0) < 0.5
            ]
            for dim in low_confidence_dims:
                trigger_from_low_confidence(
                    self.curiosity_engine,
                    content,
                    dim["name"],
                    dim["confidence"],
                )
            if low_confidence_dims:
                triggered.append("curiosity")
                result["triggered_curiosity"] = len(low_confidence_dims)
        
        # 6. 记录因果事件
        # 用户输入就是一个事件，记录下来供后续因果推断
        from causal_memory.causal_memory import log_causal_event
        log_causal_event(
            content=content,
            source="chat",
            context={"session_id": self.current_session.session_id},
        )
        triggered.append("causal_memory")
        
        # 7. 组装完整回答
        full_response = report + "\n\n" + "=== 行动规划 ===\n" + action_report
        
        if action_plan.items:
            full_response += f"\n\n=== 机器人行动信号（{len(signals)}个）===\n"
            full_response += robot_json[:500]
            if len(robot_json) > 500:
                full_response += "\n...(truncated)"
        
        # 8. 保存到助手消息
        self.add_assistant_message(
            content=full_response,
            judgment_result=judgment,
            action_plan=action_plan,
            action_signal=robot_json,
            triggered=triggered,
        )
        
        result["full_response"] = full_response
        result["triggered"] = triggered
        
        return full_response, result
    
    def auto_daily_evolution(self) -> str:
        """
        每日自动进化：
        - 扫描今日对话
        - 提取知识单元
        - 建议进化
        - 写入进化建议文件
        """
        if not self.llm_adapter:
            return "大模型适配器未配置，无法自动进化"
        
        # 获取今日所有会话
        today_sessions = self._list_today_sessions()
        if not today_sessions:
            return "今日没有对话，不需要进化"
        
        # 收集所有内容
        all_content = ""
        for session in today_sessions:
            all_content += f"\n\n=== 会话: {session.title} ===\n"
            for msg in session.messages:
                all_content += f"\n[{msg.role}]: {msg.content}\n"
        
        # 提取知识单元
        knowledge = self.llm_adapter.extract_knowledge(
            all_content,
            source=f"daily-chat-{datetime.now().strftime('%Y%m%d')}",
        )
        
        # 生成进化建议
        suggestions = suggest_evolution()
        # 保存到文件
        evolution_dir = Path("evolution_suggestions")
        evolution_dir.mkdir(exist_ok=True)
        filename = evolution_dir / f"suggestion-{datetime.now().strftime('%Y%m%d')}.json"
        
        output = {
            "date": datetime.now().isoformat(),
            "knowledge_extracted": [k.__dict__ for k in knowledge],
            "evolution_suggestions": suggestions,
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        report = f"""每日自动进化完成：
- 今日会话数: {len(today_sessions)}
- 提取知识单元: {len(knowledge)}
- 建议文件: {filename}
"""
        return report
    
    def _save_current_session(self):
        """保存当前会话"""
        if self.current_session is None:
            return
        data = self.current_session.to_dict()
        with open(CURRENT_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _save_session_to_file(self, session: ChatSession):
        """保存会话到独立文件"""
        filepath = CHAT_DIR / f"{session.session_id}.json"
        data = session.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_current_session(self) -> Optional[ChatSession]:
        """加载当前会话"""
        if not CURRENT_SESSION_FILE.exists():
            return None
        with open(CURRENT_SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.current_session = ChatSession.from_dict(data)
        return self.current_session
    
    def _list_today_sessions(self) -> List[ChatSession]:
        """列出今日所有会话"""
        today = datetime.now().strftime("%Y-%m-%d")
        sessions = []
        for f in CHAT_DIR.glob("*.json"):
            with open(f, "r", encoding="utf-8") as fobj:
                data = json.load(fobj)
            if today in data.get("created_at", ""):
                sessions.append(ChatSession.from_dict(data))
        return sessions


# ── 顶层接口 ───────────────────────────────────────────────────────────

def load_chat_system(username: str = "default") -> ChatSystem:
    """加载聊天系统"""
    cs = ChatSystem(username)
    cs.load_current_session()
    return cs


def get_current_session(cs: ChatSystem) -> Optional[ChatSession]:
    """获取当前会话"""
    return cs.current_session


def list_sessions() -> List[Dict]:
    """列出所有会话"""
    sessions = []
    for f in CHAT_DIR.glob("*.json"):
        with open(f, "r", encoding="utf-8") as fobj:
            data = json.load(fobj)
            sessions.append({
                "session_id": data["session_id"],
                "title": data["title"],
                "created_at": data["created_at"],
                "message_count": len(data["messages"]),
            })
    # 按创建时间倒序
    sessions.sort(key=lambda x: x["created_at"], reverse=True)
    return sessions


def should_keep_full(msg: ChatMessage) -> bool:
    """
    【对齐数字分身目标】科学筛选：判断这条消息是否需要完整保留
    核心原则：**记住个人思考，过滤无效闲聊，保留进化轨迹**
    
    优先级：
    1. 对自我模型/身份/判断规则的修改 → 最高重要性，必须完整
    2. 对因果记忆/决策的反馈 → 高重要性，必须完整
    3. 完整的问题/观点表达 → 保留
    4. 简短确认/闲聊/无意义回应 → 只计数不保存
    """
    if msg.role == "system":
        return True  # 系统记录必须完整
    
    content = msg.content.strip()
    
    # 1. 触发了核心分身功能 → 必须完整保留（这些是进化轨迹）
    if "triggered_functions" in msg.metadata:
        critical_funcs = {
            "feedback_record",        # 对之前决策的反馈 → 修正自我模型
            "evolution_accept",       # 接受进化建议 → 记录进化点
            "causal_record",          # 新增因果记忆 → 个人经验
            "identity_update",        # 更新核心身份 → 不能丢
            "judgment_10d",           # 完整十维判断 → 思考轨迹
            "action_plan",            # 行动规划 → 决策轨迹
        }
        triggered = msg.metadata["triggered_functions"]
        if any(f in critical_funcs for f in triggered):
            return True
    
    # 2. 包含关键个人内容关键词 → 必须完整（这些定义了"你是谁"）
    key_phrases = [
        "我认为", "我觉得", "我偏好", "我习惯", "我决定",
        "我会选择", "对我来说", "我不同意", "我同意",
        "教训", "经验", "总结", "反思", "下次",
        "核心", "原则", "价值观", "目标", "我喜欢", "我讨厌",
    ]
    for phrase in key_phrases:
        if phrase in content:
            return True
    
    # 3. 长度过滤：非常短（< 8字）通常是简单回应 → 摘要即可
    if len(content) < 8:
        return False
    
    # 4. 默认：中等长度以上是完整表达 → 保留
    return len(content) >= 20


def get_importance_level(msg: ChatMessage) -> int:
    """
    【对齐数字分身目标】获取消息重要性层级：
    0 = 低（仅摘要）→ 简短闲聊/确认
    1 = 中（完整保留）→ 普通对话/问题
    2 = 高（必须完整，核心记忆）→ 思考轨迹/反馈/进化/身份
    
    核心原则：**记住个人思考，过滤无效闲聊，保留进化轨迹**
    """
    if msg.role == "system":
        return 2  # 系统进化记录必须完整
    
    # 1. 触发核心分身功能 → 最高优先级，必须完整（这些是进化轨迹）
    if "triggered_functions" in msg.metadata:
        critical_funcs = {
            "feedback_record",        # 对之前决策的反馈 → 修正自我模型
            "evolution_accept",       # 接受进化建议 → 记录进化点
            "causal_record",          # 新增因果记忆 → 个人独有经验
            "identity_update",        # 更新核心身份 → 绝对不能丢
            "judgment_10d",           # 完整十维判断 → 思考轨迹
            "action_plan",            # 行动规划 → 决策轨迹
        }
        triggered = msg.metadata["triggered_functions"]
        if any(f in critical_funcs for f in triggered):
            return 2
    
    # 2. 内容包含个人观点/偏好 → 高重要性，必须完整（这些塑造了"你是谁"）
    content = msg.content.strip()
    key_phrases = [
        "我认为", "我觉得", "我偏好", "我习惯", "我决定",
        "我会选择", "对我来说", "我不同意", "我同意",
        "教训", "经验", "总结", "反思", "下次改进",
        "核心", "原则", "价值观", "目标", "我喜欢", "我讨厌",
    ]
    for phrase in key_phrases:
        if phrase in content:
            return 2
    
    # 3. 长度分级
    if len(content) < 8:
        return 0  # 太短，闲聊/确认，仅摘要
    if len(content) < 20:
        return 1  # 中等长度，普通问题
    return 2  # 长内容，完整表达 → 保留


def save_dialogue_to_file(session: ChatSession, filepath: str, level: int = 1):
    """
    将对话保存为可读性好的markdown文件，带科学筛选：
    - level=0: 只保留高重要性（重要决策/反馈）
    - level=1: 保留中+高重要性（默认，去冗余）
    - level=2: 保留全部（完整存档）
    """
    # 统计各层级
    stats = {0: 0, 1: 0, 2: 0}
    for msg in session.messages:
        stats[get_importance_level(msg)] += 1
    
    lines = [
        f"# 对话会话: {session.title}",
        "",
        f"- **会话ID**: {session.session_id}",
        f"- **创建时间**: {session.created_at}",
        f"- **更新时间**: {session.updated_at}",
        f"- **总消息数**: {len(session.messages)}",
        f"- **筛选层级**: level={level} (0=仅高重要性 1=中+高 2=全部)",
        f"- **统计**: 高重要性={stats[2]} | 中重要性={stats[1]} | 低重要性={stats[0]}",
        "",
        "## 筛选规则（数字分身目标：记住个人思考，过滤无效闲聊，保留进化轨迹）",
        "",
        "| 重要性 | 规则 | 是否保存 |",
        "|--------|------|----------|",
        "| 🔴 **高** | 触发十维判断/反馈/因果记录/进化/身份更新 · 包含\"我认为/我偏好/教训/原则\"等个人观点 · 系统记录 | ✅ **必须完整保存**（这就是你）|",
        "| 🟡 **中** | 长度 8-20 字 · 普通问题/回答 | ✅ 完整保存 |",
        "| 🟢 **低** | < 8 字 闲聊/简单确认 | ❌ 仅计数，不保存详情 |",
        "",
        "---",
        "",
    ]
    
    # 分块：高重要性在前，然后中，低在最后摘要
    high_importance = []
    medium_importance = []
    low_importance = []
    
    for msg in session.messages:
        imp = get_importance_level(msg)
        if imp >= level:
            role = "用户" if msg.role == "user" else ("聚活" if msg.role == "assistant" else "系统")
            entry = {
                "role": role,
                "content": msg.content,
                "triggered": msg.metadata.get("triggered_functions", [])
            }
            if imp == 2:
                high_importance.append(entry)
            else:
                medium_importance.append(entry)
        else:
            low_importance.append(msg)
    
    # 输出高重要性
    if high_importance:
        lines.append("## 🔴 高重要性内容（完整保存）")
        lines.append("")
        for entry in high_importance:
            lines.append(f"### {entry['role']}")
            lines.append("")
            lines.append(entry['content'])
            if entry['triggered']:
                lines.append("")
                lines.append(f"*触发功能: {', '.join(entry['triggered'])}*")
            lines.append("")
            lines.append("---")
            lines.append("")
    
    # 输出中等重要性
    if medium_importance:
        lines.append("## 🟡 中等重要性内容（完整保存）")
        lines.append("")
        for entry in medium_importance:
            lines.append(f"### {entry['role']}")
            lines.append("")
            lines.append(entry['content'])
            if entry['triggered']:
                lines.append("")
                lines.append(f"*触发功能: {', '.join(entry['triggered'])}*")
            lines.append("")
            lines.append("---")
            lines.append("")
    
    # 低重要性摘要
    if low_importance:
        lines.append("## 🟢 低重要性内容（摘要）")
        lines.append("")
        lines.append(f"共 {len(low_importance)} 条短消息/闲聊，这里只计数不保存详情：")
        user_short = sum(1 for m in low_importance if m.role == "user")
        assistant_short = len(low_importance) - user_short
        lines.append(f"- 用户: {user_short} 条")
        lines.append(f"- 聚活: {assistant_short} 条")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # 如果有触发记录，加上统计
    has_triggered = any("triggered_functions" in msg.metadata for msg in session.messages)
    if has_triggered:
        lines.append("## 📊 触发功能统计");
        lines.append("");
        all_triggered = [];
        for msg in session.messages:
            if "triggered_functions" in msg.metadata:
                all_triggered.extend(msg.metadata["triggered_functions"]);
        if all_triggered:
            from collections import Counter
            counter = Counter(all_triggered);
            for func, count in counter.most_common():
                lines.append(f"- {func}: {count} 次");
        lines.append("");
        lines.append("---");
        lines.append("");
    
    # 加上进化快照信息
    if hasattr(session, 'evolution_snapshot') and session.evolution_snapshot:
        lines.append("## 🧬 进化记录")
        lines.append("")
        for evo in session.evolution_snapshot:
            lines.append(f"- {evo.get('type', 'evolution')}: {evo.get('message', '')}")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def auto_trigger_functions(cs: ChatSystem, content: str):
    """自动触发各个功能，模拟人类思考过程"""
    return cs.process_user_message(content)
