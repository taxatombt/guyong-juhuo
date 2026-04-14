#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
email_adapter.py — Email 适配器，对接 perception 注意力过滤

功能:
  1. 连接 IMAP 邮箱，抓取最近邮件
  2. 分块分配优先级
  3. 输出给 AttentionFilter → 过滤后进入判断 pipeline

依赖:
  pip install imap-tools

支持:
  - Gmail / QQ邮箱 / 企业邮箱（IMAP）
  - SSL/TLS 连接
  - 发件人/主题/正文三路匹配

使用:
    from perception.email_adapter import EmailExtractorAdapter, fetch_inbox_to_judgment_input

    adapter = EmailExtractorAdapter()
    # 配置邮箱
    adapter.configure(imap_server="imap.qq.com", username="...", password="...")
    # 获取并过滤
    md = adapter.fetch_and_filter(attention_filter, folder="INBOX", limit=20)
"""

from __future__ import annotations
import imaplib
import ssl
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

# 可选依赖
try:
    import imap_tools
    from imap_tools import MailBox, AND, OR
    IMAP_TOOLS_AVAILABLE = True
except ImportError:
    IMAP_TOOLS_AVAILABLE = False


from perception.attention_filter import (
    AttentionFilter,
    IncomingMessage,
    FilterResult,
)


# ─── 数据类 ─────────────────────────────────────────────────────────────────

@dataclass
class EmailMessage:
    """一封邮件"""
    subject: str
    sender: str            # 发件人
    sender_email: str       # 发件人邮箱
    body: str               # 正文（纯文本，HTML 已转）
    date: str               # 日期字符串
    uid: str
    flags: List[str] = field(default_factory=list)
    has_attachments: bool = False
    to: str = ""            # 收件人


@dataclass
class ExtractedEmail:
    """提取完成的邮件集合"""
    folder: str
    messages: List[EmailMessage]
    metadata: Dict = field(default_factory=dict)


# ─── 便捷函数 ───────────────────────────────────────────────────────────────

def fetch_inbox_to_judgment_input(
    attention_filter: AttentionFilter,
    imap_server: str,
    username: str,
    password: str,
    folder: str = "INBOX",
    limit: int = 20,
    min_priority: int = 1,
    use_ssl: bool = True,
) -> str:
    """
    一行 API：邮箱 → 过滤后 markdown（供判断系统使用）

    Args:
        attention_filter: 注意力过滤器
        imap_server: IMAP 服务器地址
        username: 邮箱用户名
        password: 密码或授权码
        folder: 文件夹（默认 INBOX）
        limit: 最多获取邮件数
        min_priority: 最低优先级阈值
        use_ssl: 是否使用 SSL
    """
    adapter = EmailExtractorAdapter()
    adapter.configure(imap_server, username, password, use_ssl=use_ssl)
    return adapter.fetch_and_filter(
        attention_filter,
        folder=folder,
        limit=limit,
        min_priority=min_priority,
    )


# ─── 适配器 ─────────────────────────────────────────────────────────────────

class EmailExtractorAdapter:
    """
    Email 提取适配器

    使用:
        adapter = EmailExtractorAdapter()
        adapter.configure(imap_server="imap.qq.com", username="...", password="...")
        md = adapter.fetch_and_filter(attention_filter)
    """

    def __init__(self):
        if not IMAP_TOOLS_AVAILABLE:
            raise ImportError(
                "imap-tools 未安装。请运行: pip install imap-tools"
            )
        self._server: str = ""
        self._username: str = ""
        self._password: str = ""
        self._use_ssl: bool = True
        self.base_priority = {
            "subject":  4,  # 主题
            "sender":   3,  # 发件人
            "body":     2,  # 正文
        }

    def configure(
        self,
        imap_server: str,
        username: str,
        password: str,
        use_ssl: bool = True,
    ) -> None:
        """配置邮箱连接参数。"""
        self._server = imap_server
        self._username = username
        self._password = password
        self._use_ssl = use_ssl

    # ── 核心方法 ──────────────────────────────────────────────────────────

    def fetch_emails(
        self,
        folder: str = "INBOX",
        limit: int = 50,
        unread_only: bool = False,
    ) -> ExtractedEmail:
        """
        从 IMAP 服务器拉取邮件。

        Args:
            folder: 文件夹（INBOX / Sent / Drafts 等）
            limit: 最大邮件数
            unread_only: 是否只抓未读邮件

        Returns:
            ExtractedEmail 对象

        Raises:
            RuntimeError: 连接或认证失败
        """
        try:
            if self._use_ssl:
                with MailBox(self._server).login(
                    self._username, self._password
                ) as mailbox:
                    # 切换文件夹
                    folder_info = mailbox.folder.get()
                    if folder_info.name != folder:
                        mailbox.folder.set(folder)

                    # 构建查询条件
                    criteria = AND(seen=not unread_only) if unread_only else None

                    messages: List[EmailMessage] = []
                    for msg in mailbox.fetch(criteria, limit=limit, reverse=True):
                        # HTML 转纯文本
                        body = ""
                        if msg.html:
                            try:
                                import html2text
                                h = html2text.HTML2Text()
                                body = h.handle(msg.html)
                            except ImportError:
                                # fallback: 简单去除 HTML 标签
                                import re
                                body = re.sub(r'<[^>]+>', '', msg.html)
                        else:
                            body = msg.text or ""

                        # 发件人信息
                        sender_name = ""
                        sender_email = ""
                        if msg.from_:
                            sender_email = msg.from_.email
                            sender_name = msg.from_.name or sender_email

                        messages.append(EmailMessage(
                            subject=msg.subject or "(无主题)",
                            sender=sender_name,
                            sender_email=sender_email,
                            body=body.strip(),
                            date=msg.date_str or "",
                            uid=str(msg.uid),
                            flags=list(msg.flags) if msg.flags else [],
                            has_attachments=len(msg.attachments) > 0,
                            to=msg.to or "",
                        ))

                    return ExtractedEmail(
                        folder=folder,
                        messages=messages,
                        metadata={
                            "imap_server": self._server,
                            "username": self._username,
                            "unread_only": unread_only,
                        },
                    )
        except Exception as e:
            raise RuntimeError(f"Email fetch 失败: {e}")

    def assign_priority(
        self,
        email: EmailMessage,
        attention_filter: AttentionFilter,
    ) -> int:
        """
        用 AttentionFilter 计算单封邮件的优先级。

        匹配范围：subject + sender + body
        """
        text = " ".join([email.subject, email.sender, email.sender_email, email.body[:500]])
        msg = IncomingMessage(
            content=text,
            source="email",
            sender=email.sender_email,
        )
        result = attention_filter.filter(msg)
        return result.priority

    def filter_messages(
        self,
        extracted: ExtractedEmail,
        attention_filter: AttentionFilter,
        min_priority: int = 1,
    ) -> List[EmailMessage]:
        """用 AttentionFilter 过滤邮件。"""
        passed = []
        for email in extracted.messages:
            priority = self.assign_priority(email, attention_filter)
            if priority >= min_priority:
                passed.append(email)
        return passed

    def to_markdown(self, email: EmailMessage) -> str:
        """单封邮件 → markdown 格式。"""
        lines = [
            f"## {email.subject}",
            "",
            f"发件人: {email.sender} <{email.sender_email}>",
            f"时间: {email.date}",
            f"收件人: {email.to}",
        ]
        if email.has_attachments:
            lines.append(f"附件: 有")
        lines.append("")
        lines.append(email.body)
        return "\n".join(lines)

    def filter_to_markdown(
        self,
        extracted: ExtractedEmail,
        attention_filter: AttentionFilter,
        min_priority: int = 1,
    ) -> str:
        """
        过滤并输出 markdown 格式（供判断 pipeline 使用）。
        """
        passed = self.filter_messages(extracted, attention_filter, min_priority)

        if not passed:
            return ""

        lines = [
            f"# Email: {extracted.folder}",
            f"共 {len(extracted.messages)} 封，命中 {len(passed)} 封",
            "",
        ]
        for email in passed:
            lines.append(self.to_markdown(email))
            lines.append("\n---\n")

        return "\n".join(lines)

    def fetch_and_filter(
        self,
        attention_filter: AttentionFilter,
        folder: str = "INBOX",
        limit: int = 20,
        min_priority: int = 1,
        unread_only: bool = False,
    ) -> str:
        """
        完整流程：fetch → filter → markdown

        Returns:
            markdown 字符串（空字符串表示没有通过过滤的内容）
        """
        if not self._server:
            return "[Email Error] 请先调用 configure() 配置邮箱"

        try:
            extracted = self.fetch_emails(
                folder=folder,
                limit=limit,
                unread_only=unread_only,
            )
        except RuntimeError as e:
            return f"[Email Error] {e}"

        return self.filter_to_markdown(extracted, attention_filter, min_priority)       