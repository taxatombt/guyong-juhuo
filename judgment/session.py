#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session.py — Juhuo Session 持久化

借鉴 Codex Session 格式：完整的对话历史持久化

Session 结构：
- session.json: 元数据
- session.jsonl: 消息历史
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from uuid import uuid4

from judgment.logging_config import get_logger
log = get_logger("juhuo.session")


# 配置
SESSION_DIR = Path(__file__).parent.parent / "data" / "sessions"
CURRENT_SESSION_FILE = SESSION_DIR / "current.json"


@dataclass
class SessionMetadata:
    """Session 元数据"""
    id: str
    created_at: str
    updated_at: str
    title: str = ""
    message_count: int = 0
    total_tokens: int = 0
    tags: List[str] = field(default_factory=list)
    archived: bool = False


@dataclass
class Message:
    """消息"""
    id: str
    role: str  # user / assistant / system
    content: str
    timestamp: str
    metadata: Dict = field(default_factory=dict)


class Session:
    """
    Juhuo Session
    
    管理单个会话的生命周期
    """
    
    def __init__(self, session_id: str = None):
        self.id = session_id or str(uuid4())
        self.metadata = SessionMetadata(
            id=self.id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self.messages: List[Message] = []
        
        # 加载已有 session
        if CURRENT_SESSION_FILE.exists():
            self._load()
    
    def add_message(self, role: str, content: str, metadata: Dict = None) -> Message:
        """添加消息"""
        msg = Message(
            id=str(uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        self.messages.append(msg)
        self.metadata.message_count = len(self.messages)
        self.metadata.updated_at = datetime.now().isoformat()
        
        # 自动保存
        self.save()
        
        return msg
    
    def add_user_message(self, content: str) -> Message:
        """添加用户消息"""
        return self.add_message("user", content)
    
    def add_assistant_message(self, content: str, metadata: Dict = None) -> Message:
        """添加助手消息"""
        return self.add_message("assistant", content, metadata)
    
    def get_messages(self, limit: int = None) -> List[Dict]:
        """获取消息列表"""
        msgs = self.messages[-limit:] if limit else self.messages
        return [asdict(m) for m in msgs]
    
    def save(self) -> None:
        """保存 Session"""
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        
        # 保存元数据
        meta_file = SESSION_DIR / f"{self.id}.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": asdict(self.metadata),
                "messages": [asdict(m) for m in self.messages]
            }, f, ensure_ascii=False, indent=2)
        
        # 更新当前 session 指针
        with open(CURRENT_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"current_session_id": self.id}, f)
        
        log.debug(f"Saved session {self.id}")
    
    def _load(self) -> None:
        """加载 Session"""
        try:
            meta_file = SESSION_DIR / f"{self.id}.json"
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.metadata = SessionMetadata(**data["metadata"])
                    self.messages = [Message(**m) for m in data["messages"]]
        except Exception as e:
            log.error(f"Failed to load session: {e}")
    
    def archive(self) -> None:
        """归档 Session"""
        self.metadata.archived = True
        self.save()
    
    def export_jsonl(self) -> str:
        """导出为 JSONL 格式"""
        lines = []
        for msg in self.messages:
            lines.append(json.dumps(asdict(msg), ensure_ascii=False))
        return "\n".join(lines)
    
    def get_summary(self) -> str:
        """获取 Session 摘要"""
        first_msg = self.messages[0].content if self.messages else ""
        return first_msg[:50] + "..." if len(first_msg) > 50 else first_msg


class SessionManager:
    """
    Session 管理器
    
    管理所有 Session
    """
    
    def __init__(self):
        self.current_session: Optional[Session] = None
        self._load_current()
    
    def _load_current(self) -> None:
        """加载当前 Session"""
        if CURRENT_SESSION_FILE.exists():
            with open(CURRENT_SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                session_id = data.get("current_session_id")
                if session_id:
                    self.current_session = Session(session_id)
        
        if self.current_session is None:
            self.current_session = Session()
    
    def get_current(self) -> Session:
        """获取当前 Session"""
        if self.current_session is None:
            self.current_session = Session()
        return self.current_session
    
    def new_session(self) -> Session:
        """创建新 Session"""
        # 归档当前
        if self.current_session and self.current_session.messages:
            self.current_session.archive()
        
        # 创建新的
        self.current_session = Session()
        return self.current_session
    
    def list_sessions(self, limit: int = 10) -> List[SessionMetadata]:
        """列出最近的 Sessions"""
        sessions = []
        if not SESSION_DIR.exists():
            return sessions
        
        for f in sorted(SESSION_DIR.glob("*.json"), reverse=True)[:limit]:
            if f.name == "current.json":
                continue
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    sessions.append(SessionMetadata(**data["metadata"]))
            except:
                continue
        
        return sessions
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取指定 Session"""
        session = Session(session_id)
        return session if session.messages else None


# 全局管理器
_manager: Optional[SessionManager] = None


def get_manager() -> SessionManager:
    """获取全局 Session 管理器"""
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager


def get_current_session() -> Session:
    """获取当前 Session"""
    return get_manager().get_current()


if __name__ == "__main__":
    # 测试
    mgr = get_manager()
    session = mgr.get_current()
    
    session.add_user_message("测试问题")
    session.add_assistant_message("这是回答")
    
    print(f"Session: {session.id}")
    print(f"Messages: {len(session.messages)}")
    print(f"Summary: {session.get_summary()}")
