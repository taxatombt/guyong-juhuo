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

from .scraping_adapter import (
    ScrapedPage,
    SpiderItem,
    scrape_url,
    scrape,
    spider_crawl,
    save_to_intents,
)

from .summary import (
    PerceptionEntry,
    PerceptionSummary,
    get_perception_summary,
    get_recent_topics,
)

from .git_nexus_adapter import (
    NexusRepo,
    NexusSymbol,
    NexusContext,
    NexusImpact,
    is_available as gitnexus_available,
    analyze as gitnexus_analyze,
    status as gitnexus_status,
    query_graph,
    symbol_context,
    symbol_impact,
    detect_changes,
    generate_wiki,
    list_repos,
    index_juhuo,
    save_to_perception_intents,
    context_for_judgment,
    start_mcp_server,
    stop_mcp_server,
    start_web_ui,
    stop_web_ui,
    start_auto_update,
    stop_auto_update,
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
    # scraping_adapter
    "ScrapedPage",
    "SpiderItem",
    "scrape_url",
    "scrape",
    "spider_crawl",
    "save_to_intents",
    # summary
    "PerceptionEntry",
    "PerceptionSummary",
    "get_perception_summary",
    "get_recent_topics",
    # git_nexus_adapter
    "NexusRepo",
    "NexusSymbol",
    "NexusContext",
    "NexusImpact",
    "gitnexus_available",
    "gitnexus_analyze",
    "gitnexus_status",
    "query_graph",
    "symbol_context",
    "symbol_impact",
    "detect_changes",
    "generate_wiki",
    "list_repos",
    "index_juhuo",
    "save_to_perception_intents",
    "context_for_judgment",
    "start_mcp_server",
    "stop_mcp_server",
    "start_web_ui",
    "stop_web_ui",
    "start_auto_update",
    "stop_auto_update",
]
