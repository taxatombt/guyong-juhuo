#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rss_adapter.py — RSS Feed 适配器，对接 perception 注意力过滤

功能:
  1. 抓取 RSS/Atom feed 并解析条目
  2. 分块分配优先级
  3. 输出给 AttentionFilter → 过滤后进入判断 pipeline

依赖:
  pip install feedparser

使用:
    from perception.rss_adapter import RSSExtractorAdapter, extract_rss_to_judgment_input

    adapter = RSSExtractorAdapter()
    items = adapter.fetch_feed("https://example.com/feed.xml")
    filtered = adapter.fetch_and_filter("https://example.com/feed.xml", attention_filter)
"""

from __future__ import annotations
import sys
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# 可选依赖
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False


from perception.attention_filter import (
    AttentionFilter,
    IncomingMessage,
    FilterResult,
)


# ─── 数据类 ─────────────────────────────────────────────────────────────────

@dataclass
class RSSItem:
    """RSS/Atom 条目"""
    title: str
    content: str          # 摘要或正文
    url: str
    published: str         # 发布时间的原始字符串
    source: str            # feed 源名称
    feed_url: str          # feed URL（来源追踪）
    author: str = ""
    categories: List[str] = field(default_factory=list)


@dataclass
class ExtractedRSS:
    """提取完成的完整 RSS feed"""
    feed_url: str
    feed_title: str
    items: List[RSSItem]
    metadata: Dict = field(default_factory=dict)


# ─── 便捷函数 ───────────────────────────────────────────────────────────────

def extract_rss_to_judgment_input(
    feed_url: str,
    attention_filter: AttentionFilter,
    max_items: int = 10,
) -> str:
    """
    一行 API：RSS → 过滤后 markdown（供判断系统使用）
    """
    adapter = RSSExtractorAdapter()
    return adapter.fetch_and_filter(feed_url, attention_filter, max_items=max_items)


# ─── 适配器 ─────────────────────────────────────────────────────────────────

class RSSExtractorAdapter:
    """
    RSS Feed 提取适配器

    使用:
        adapter = RSSExtractorAdapter()
        # 方式1: 直接获取条目
        items = adapter.fetch_feed("https://example.com/feed.xml")
        # 方式2: 获取 + 过滤
        md = adapter.fetch_and_filter("https://example.com/feed.xml", attention_filter)
    """

    def __init__(self):
        if not FEEDPARSER_AVAILABLE:
            raise ImportError(
                "feedparser 未安装。请运行: pip install feedparser"
            )
        self.base_priority = {
            "title":       4,  # 条目标题
            "content":     2,  # 正文内容
            "author":      1,  # 作者
            "category":    2,  # 分类标签
        }

    # ── 核心方法 ──────────────────────────────────────────────────────────

    def fetch_feed(self, feed_url: str, max_items: int = 50) -> ExtractedRSS:
        """
        抓取并解析 RSS/Atom feed。

        Args:
            feed_url: RSS 或 Atom feed URL
            max_items: 最大条目数（避免内容爆炸）

        Returns:
            ExtractedRSS 对象

        Raises:
            RuntimeError: feed 无法解析或网络错误
        """
        parsed = feedparser.parse(feed_url)

        if parsed.bozo and not parsed.entries:
            raise RuntimeError(f"RSS feed 解析失败: {feed_url}")

        feed_title = parsed.feed.get("title", feed_url)
        items: List[RSSItem] = []

        for entry in parsed.entries[:max_items]:
            # 提取内容（优先 summary，fallback title）
            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "content") and entry.content:
                content = entry.content[0].value
            elif hasattr(entry, "title"):
                content = entry.title

            # 发布时间
            published = ""
            if hasattr(entry, "published"):
                published = entry.published
            elif hasattr(entry, "updated"):
                published = entry.updated

            # URL
            url = ""
            if hasattr(entry, "link"):
                url = entry.link
            elif hasattr(entry, "id"):
                url = entry.id

            # 分类
            categories = []
            if hasattr(entry, "tags"):
                categories = [t.term for t in entry.tags]

            # 作者
            author = ""
            if hasattr(entry, "author"):
                author = entry.author
            elif hasattr(entry, "author_detail") and entry.author_detail:
                author = entry.author_detail.get("name", "")

            items.append(RSSItem(
                title=str(entry.get("title", "")),
                content=content,
                url=url,
                published=published,
                source=feed_title,
                feed_url=feed_url,
                author=author,
                categories=categories,
            ))

        return ExtractedRSS(
            feed_url=feed_url,
            feed_title=feed_title,
            items=items,
            metadata={
                "bozo": parsed.bozo,
                "version": parsed.version,
            },
        )

    def assign_priority(
        self,
        item: RSSItem,
        attention_filter: AttentionFilter,
    ) -> int:
        """
        用 AttentionFilter 计算单条 RSS 的优先级。

        匹配范围：title + content + author + categories
        """
        text = " ".join([
            item.title,
            item.content,
            item.author,
            *item.categories,
        ])
        msg = IncomingMessage(
            content=text,
            source="rss",
            sender=item.source,
        )
        result = attention_filter.filter(msg)
        return result.priority

    def filter_items(
        self,
        extracted: ExtractedRSS,
        attention_filter: AttentionFilter,
        min_priority: int = 1,
    ) -> List[RSSItem]:
        """用 AttentionFilter 过滤 RSS 条目。"""
        passed = []
        for item in extracted.items:
            priority = self.assign_priority(item, attention_filter)
            if priority >= min_priority:
                passed.append(item)
        return passed

    def to_markdown(self, item: RSSItem) -> str:
        """单条 RSS 条目 → markdown 格式。"""
        lines = [
            f"## {item.title}",
            f"",
            f"来源: [{item.source}]({item.feed_url})",
        ]
        if item.url:
            lines.append(f"链接: [{item.url}]({item.url})")
        if item.author:
            lines.append(f"作者: {item.author}")
        if item.published:
            lines.append(f"时间: {item.published}")
        if item.categories:
            lines.append(f"标签: {' / '.join(item.categories)}")
        lines.append("")
        lines.append(item.content)
        return "\n".join(lines)

    def filter_to_markdown(
        self,
        extracted: ExtractedRSS,
        attention_filter: AttentionFilter,
        min_priority: int = 1,
    ) -> str:
        """
        过滤并输出 markdown 格式（供判断 pipeline 使用）。
        """
        passed = self.filter_items(extracted, attention_filter, min_priority)

        if not passed:
            return ""

        lines = [
            f"# {extracted.feed_title}",
            f"共 {len(extracted.items)} 条，命中 {len(passed)} 条",
            "",
        ]
        for item in passed:
            lines.append(self.to_markdown(item))
            lines.append("\n---\n")

        return "\n".join(lines)

    def fetch_and_filter(
        self,
        feed_url: str,
        attention_filter: AttentionFilter,
        max_items: int = 20,
        min_priority: int = 1,
    ) -> str:
        """
        完整流程：fetch → parse → filter → markdown

        Returns:
            markdown 字符串（空字符串表示没有通过过滤的内容）
        """
        try:
            extracted = self.fetch_feed(feed_url, max_items=max_items)
        except RuntimeError as e:
            return f"[RSS Error] {e}"

        return self.filter_to_markdown(extracted, attention_filter, min_priority)       