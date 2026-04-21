#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_protocol.py — MCP (Model Context Protocol) 核心协议

MCP 协议定义：
- JSON-RPC 2.0 通信
- 三类资源：Tools / Resources / Prompts
- 两种传输：stdio / HTTP
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
import json


# ═══════════════════════════════════════════════════════════════════════════
# MCP 协议类型
# ═══════════════════════════════════════════════════════════════════════════

class MCPMethod(Enum):
    """MCP JSON-RPC 方法"""
    INITIALIZE = "initialize"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MCPTool":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", data.get("input_schema", {}))
        )


@dataclass
class MCPToolResult:
    """MCP 工具调用结果"""
    tool: str
    args: Dict
    result: Any
    error: Optional[str] = None
    success: bool = True


@dataclass
class MCPResource:
    """MCP 资源"""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MCPResource":
        return cls(
            uri=data.get("uri", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            mime_type=data.get("mimeType", "text/plain")
        )


@dataclass
class MCPPrompt:
    """MCP 提示模板"""
    name: str
    description: str
    arguments: List[Dict] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MCPPrompt":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            arguments=data.get("arguments", [])
        )


def validate_tool_input(schema: Dict, args: Dict) -> Optional[str]:
    """验证工具输入参数"""
    required = schema.get("required", [])
    
    for param in required:
        if param not in args:
            return f"Missing required parameter: {param}"
    
    return None
