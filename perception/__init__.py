"""
perception — 信息接收层

负责:
- 注意力过滤：决定哪些内容要进入认知系统
- PDF 结构化提取适配
- 网页提取适配
- RSS Feed 适配
- Email 适配
"""

from .attention_filter import (
    AttentionFilter,
    AttentionItem,
    IncomingMessage,
    FilterResult,
)

from .pdf_adapter import (
    PDFExtractorAdapter,
    PDFBlock,
    ExtractedPDF,
    extract_pdf_to_judgment_input,
)

from .web_adapter import (
    WebExtractorAdapter,
    WebBlock,
    ExtractedWeb,
    extract_web_to_judgment_input,
)

from .rss_adapter import (
    RSSExtractorAdapter,
    RSSItem,
    ExtractedRSS,
    extract_rss_to_judgment_input,
)

from .email_adapter import (
    EmailExtractorAdapter,
    EmailMessage,
    ExtractedEmail,
    fetch_inbox_to_judgment_input,
)

__all__ = [
    # attention_filter
    "AttentionFilter",
    "AttentionItem",
    "IncomingMessage",
    "FilterResult",
    # pdf_adapter
    "PDFExtractorAdapter",
    "PDFBlock",
    "ExtractedPDF",
    "extract_pdf_to_judgment_input",
    # web_adapter
    "WebExtractorAdapter",
    "WebBlock",
    "ExtractedWeb",
    "extract_web_to_judgment_input",
    # rss_adapter
    "RSSExtractorAdapter",
    "RSSItem",
    "ExtractedRSS",
    "extract_rss_to_judgment_input",
    # email_adapter
    "EmailExtractorAdapter",
    "EmailMessage",
    "ExtractedEmail",
    "fetch_inbox_to_judgment_input",
]
