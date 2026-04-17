#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
juhuo MCP 模块

MCP (Model Context Protocol) 客户端实现，支持：
- stdio 传输（本地服务器）
- HTTP 传输（远程服务器）
- 多服务器管理

快速开始：
```python
from juhuo.mcp import MCPClient, MCPServerConfig, get_mcp_hub

# 单服务器使用
config = MCPServerConfig(
    name="filesystem",
    transport="stdio",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "."]
)
client = MCPClient(config)
client.connect()
tools = client.list_tools()
client.disconnect()

# 多服务器管理
hub = get_mcp_hub()
hub.add_server(config)
hub.connect_all()
result = hub.call_tool("filesystem", "read_file", {"path": "test.txt"})
```

常用 MCP 服务器：
- @modelcontextprotocol/server-filesystem — 文件系统访问
- @modelcontextprotocol/server-github — GitHub API
- @modelcontextprotocol/server-memory — 持久内存
- @modelcontextprotocol/server-slack — Slack 集成
"""

from .mcp_protocol import (
    MCPTool,
    MCPToolResult,
    MCPResource,
    MCPPrompt,
    validate_tool_input,
)

from .mcp_client import (
    MCPServerConfig,
    MCPClient,
    MCPServerManager,
    get_mcp_hub,
    setup_mcp_from_config,
)

__all__ = [
    # 协议类型
    "MCPTool",
    "MCPToolResult",
    "MCPResource",
    "MCPPrompt",
    "validate_tool_input",
    # 客户端
    "MCPServerConfig",
    "MCPClient",
    "MCPServerManager",
    # 快捷函数
    "get_mcp_hub",
    "setup_mcp_from_config",
]
