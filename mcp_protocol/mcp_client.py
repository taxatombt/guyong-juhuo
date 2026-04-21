#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_client.py — MCP 客户端实现

支持两种传输方式：
1. stdio: 通过子进程通信（本地服务器）
2. HTTP: 通过HTTP请求通信（远程服务器）

使用方式：
    from mcp import MCPClient, MCPServerConfig
    
    # 配置服务器
    config = MCPServerConfig(
        name="filesystem",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "./data"]
    )
    
    # 连接并使用
    client = MCPClient(config)
    client.connect()
    
    tools = client.list_tools()
    result = client.call_tool("read_file", {"path": "test.txt"})
    
    client.disconnect()
"""

from __future__ import annotations
import asyncio
import json
import subprocess
import threading
import queue
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime

from .mcp_protocol import MCPTool, MCPResource, MCPPrompt, MCPToolResult, validate_tool_input


# ═══════════════════════════════════════════════════════════════════════════
# MCP 服务器配置
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MCPServerConfig:
    """MCP 服务器配置"""
    name: str                           # 服务器名称
    transport: str = "stdio"           # stdio | http
    command: str = ""                  # stdio: 可执行命令
    args: List[str] = field(default_factory=list)  # stdio: 命令参数
    env: Dict[str, str] = field(default_factory=dict)  # 环境变量
    url: str = ""                       # http: 服务器URL
    headers: Dict[str, str] = field(default_factory=dict)  # http: 请求头
    timeout: int = 120                  # 超时时间（秒）
    
    def validate(self) -> Optional[str]:
        """验证配置有效性"""
        if self.transport == "stdio":
            if not self.command:
                return "stdio transport requires 'command'"
        elif self.transport == "http":
            if not self.url:
                return "http transport requires 'url'"
        else:
            return f"Unknown transport: {self.transport}"
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Stdio 传输实现
# ═══════════════════════════════════════════════════════════════════════════

class StdioTransport:
    """Stdio 传输：通过子进程通信"""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._response_queue: queue.Queue = queue.Queue()
        self._read_thread: Optional[threading.Thread] = None
        self._running = False
    
    def connect(self) -> bool:
        """启动进程并初始化"""
        try:
            # 构建命令
            cmd = [self.config.command] + self.config.args
            
            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**subprocess.os.environ, **self.config.env},
                text=True,
                bufsize=1,
            )
            
            self._running = True
            
            # 启动读取线程
            self._read_thread = threading.Thread(target=self._read_output, daemon=True)
            self._read_thread.start()
            
            # 发送 initialize
            self._send_initialize()
            
            return True
            
        except Exception as e:
            print(f"[MCP Stdio] Connect error: {e}")
            return False
    
    def _read_output(self):
        """读取进程输出"""
        while self._running and self.process:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                
                msg = json.loads(line.strip())
                
                # 处理响应
                if "id" in msg:
                    self._response_queue.put(msg)
                # 处理通知（无 id）
                elif "method" in msg:
                    self._handle_notification(msg)
                    
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"[MCP Stdio] Read error: {e}")
                break
    
    def _handle_notification(self, msg: Dict):
        """处理服务器通知"""
        method = msg.get("method", "")
        params = msg.get("params", {})
        
        # 处理进度通知
        if method == "notifications/progress":
            pass
    
    def _send_initialize(self):
        """发送初始化请求"""
        # 获取客户端能力
        capabilities = {
            "roots": {"listChanged": True},
            "sampling": {},
        }
        
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": capabilities,
                "clientInfo": {
                    "name": "juhuo-mcp-client",
                    "version": "1.0.0"
                }
            }
        }
        
        self._send(request)
        
        # 等待响应
        response = self._wait_response(request["id"])
        if response and "result" in response:
            self._server_info = response["result"]
    
    def _next_id(self) -> int:
        """生成请求ID"""
        with self._lock:
            self._request_id += 1
            return self._request_id
    
    def _send(self, request: Dict):
        """发送请求"""
        if self.process and self.process.stdin:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
    
    def _wait_response(self, request_id: int, timeout: float = 30.0) -> Optional[Dict]:
        """等待响应"""
        try:
            return self._response_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def send_request(self, method: str, params: Dict = None) -> Optional[Dict]:
        """发送请求并等待响应"""
        request_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }
        
        self._send(request)
        return self._wait_response(request_id, timeout=self.config.timeout)
    
    def disconnect(self):
        """断开连接"""
        self._running = False
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None


# ═══════════════════════════════════════════════════════════════════════════
# HTTP 传输实现
# ═══════════════════════════════════════════════════════════════════════════

class HTTPTransport:
    """HTTP 传输：通过 HTTP 请求通信"""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._request_id = 0
        self._lock = threading.Lock()
        self._session = None
    
    def connect(self) -> bool:
        """建立连接"""
        try:
            import aiohttp
            self._session = aiohttp.ClientSession(
                headers=self.config.headers
            )
            return True
        except ImportError:
            print("[MCP HTTP] aiohttp not installed. Run: pip install aiohttp")
            return False
        except Exception as e:
            print(f"[MCP HTTP] Connect error: {e}")
            return False
    
    def _next_id(self) -> int:
        """生成请求ID"""
        with self._lock:
            self._request_id += 1
            return self._request_id
    
    def send_request(self, method: str, params: Dict = None) -> Optional[Dict]:
        """发送请求"""
        if not self._session:
            return None
        
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {}
        }
        
        try:
            # 同步方式调用
            import requests
            response = requests.post(
                self.config.url,
                json=request,
                timeout=self.config.timeout,
                headers=self.config.headers
            )
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except ImportError:
            print("[MCP HTTP] requests not installed. Run: pip install requests")
            return None
        except Exception as e:
            print(f"[MCP HTTP] Request error: {e}")
            return None
    
    def disconnect(self):
        """断开连接"""
        if self._session:
            self._session.close()
            self._session = None


# ═══════════════════════════════════════════════════════════════════════════
# MCP 客户端
# ═══════════════════════════════════════════════════════════════════════════

class MCPClient:
    """
    MCP 客户端
    
    使用方式：
        config = MCPServerConfig(name="filesystem", transport="stdio",
                                 command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "."])
        client = MCPClient(config)
        client.connect()
        
        tools = client.list_tools()
        result = client.call_tool("read_file", {"path": "test.txt"})
        
        client.disconnect()
    """
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.transport: Optional[Any] = None
        self._tools: List[MCPTool] = []
        self._resources: List[MCPResource] = []
        self._prompts: List[MCPPrompt] = []
        self._connected = False
    
    @property
    def name(self) -> str:
        """服务器名称"""
        return self.config.name
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    def connect(self) -> bool:
        """连接服务器"""
        if self._connected:
            return True
        
        # 选择传输方式
        if self.config.transport == "stdio":
            self.transport = StdioTransport(self.config)
        elif self.config.transport == "http":
            self.transport = HTTPTransport(self.config)
        else:
            print(f"[MCP] Unknown transport: {self.config.transport}")
            return False
        
        # 连接
        if self.transport.connect():
            self._connected = True
            # 加载资源
            self._discover_resources()
            return True
        
        return False
    
    def _discover_resources(self):
        """发现可用的工具、资源、提示"""
        # 发现工具
        tools_response = self.transport.send_request("tools/list")
        if tools_response and "result" in tools_response:
            self._tools = [
                MCPTool.from_dict(t) 
                for t in tools_response["result"].get("tools", [])
            ]
        
        # 发现资源
        resources_response = self.transport.send_request("resources/list")
        if resources_response and "result" in resources_response:
            self._resources = [
                MCPResource.from_dict(r)
                for r in resources_response["result"].get("resources", [])
            ]
        
        # 发现提示
        prompts_response = self.transport.send_request("prompts/list")
        if prompts_response and "result" in prompts_response:
            self._prompts = [
                MCPPrompt.from_dict(p)
                for p in prompts_response["result"].get("prompts", [])
            ]
    
    def disconnect(self):
        """断开连接"""
        if self.transport:
            self.transport.disconnect()
            self.transport = None
        self._connected = False
        self._tools = []
        self._resources = []
        self._prompts = []
    
    def list_tools(self) -> List[MCPTool]:
        """列出可用工具"""
        return self._tools
    
    def list_resources(self) -> List[MCPResource]:
        """列出可用资源"""
        return self._resources
    
    def list_prompts(self) -> List[MCPPrompt]:
        """列出可用提示"""
        return self._prompts
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取工具定义"""
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None
    
    def call_tool(self, name: str, arguments: Dict = None) -> MCPToolResult:
        """
        调用工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            MCPToolResult: 工具调用结果
        """
        arguments = arguments or {}
        
        # 获取工具定义
        tool = self.get_tool(name)
        if not tool:
            return MCPToolResult(
                tool=name,
                args=arguments,
                result=None,
                error=f"Tool '{name}' not found",
                success=False
            )
        
        # 验证参数
        error = validate_tool_input(tool.input_schema, arguments)
        if error:
            return MCPToolResult(
                tool=name,
                args=arguments,
                result=None,
                error=error,
                success=False
            )
        
        # 调用工具
        try:
            response = self.transport.send_request(
                "tools/call",
                {
                    "name": name,
                    "arguments": arguments
                }
            )
            
            if response and "result" in response:
                content = response["result"].get("content", [])
                # 提取文本内容
                text = ""
                for item in content:
                    if item.get("type") == "text":
                        text += item.get("text", "")
                
                return MCPToolResult(
                    tool=name,
                    args=arguments,
                    result=text,
                    success=True
                )
            elif response and "error" in response:
                return MCPToolResult(
                    tool=name,
                    args=arguments,
                    result=None,
                    error=response["error"].get("message", "Unknown error"),
                    success=False
                )
            else:
                return MCPToolResult(
                    tool=name,
                    args=arguments,
                    result=None,
                    error="No response from server",
                    success=False
                )
                
        except Exception as e:
            return MCPToolResult(
                tool=name,
                args=arguments,
                result=None,
                error=str(e),
                success=False
            )
    
    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"<MCPClient {self.name} ({status}) tools={len(self._tools)}>"


# ═══════════════════════════════════════════════════════════════════════════
# MCP 服务器管理器
# ═══════════════════════════════════════════════════════════════════════════

class MCPServerManager:
    """
    MCP 服务器管理器
    
    管理多个 MCP 服务器连接，统一工具访问接口。
    
    使用方式：
        manager = MCPServerManager()
        
        # 添加服务器
        manager.add_server(MCPServerConfig(
            name="filesystem",
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "."]
        ))
        
        # 连接所有服务器
        manager.connect_all()
        
        # 列出所有工具
        all_tools = manager.list_all_tools()
        
        # 调用工具
        result = manager.call_tool("filesystem", "read_file", {"path": "test.txt"})
        
        # 断开所有
        manager.disconnect_all()
    """
    
    def __init__(self):
        self._servers: Dict[str, MCPClient] = {}
        self._configs: Dict[str, MCPServerConfig] = {}
    
    def add_server(self, config: MCPServerConfig) -> Optional[str]:
        """
        添加服务器配置
        
        Returns:
            错误信息，或 None 表示成功
        """
        error = config.validate()
        if error:
            return error
        
        self._configs[config.name] = config
        return None
    
    def remove_server(self, name: str) -> bool:
        """移除服务器"""
        if name in self._servers:
            self._servers[name].disconnect()
            del self._servers[name]
        if name in self._configs:
            del self._configs[name]
        return True
    
    def get_server(self, name: str) -> Optional[MCPClient]:
        """获取服务器客户端"""
        return self._servers.get(name)
    
    def connect_all(self) -> Dict[str, bool]:
        """连接所有服务器"""
        results = {}
        
        for name, config in self._configs.items():
            client = MCPClient(config)
            if client.connect():
                self._servers[name] = client
                results[name] = True
            else:
                results[name] = False
        
        return results
    
    def disconnect_all(self):
        """断开所有服务器"""
        for client in self._servers.values():
            client.disconnect()
        self._servers = {}
    
    def list_all_tools(self) -> Dict[str, List[MCPTool]]:
        """列出所有服务器的工具"""
        return {
            name: client.list_tools()
            for name, client in self._servers.items()
        }
    
    def find_tool(self, tool_name: str) -> Optional[tuple]:
        """
        查找工具属于哪个服务器
        
        Returns:
            (server_name, tool) 或 None
        """
        for name, client in self._servers.items():
            tool = client.get_tool(tool_name)
            if tool:
                return (name, tool)
        return None
    
    def call_tool(self, server_name: str, tool_name: str, arguments: Dict = None) -> MCPToolResult:
        """
        调用工具
        
        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数
        """
        client = self._servers.get(server_name)
        if not client:
            return MCPToolResult(
                tool=tool_name,
                args=arguments or {},
                result=None,
                error=f"Server '{server_name}' not found",
                success=False
            )
        
        return client.call_tool(tool_name, arguments)
    
    def find_and_call_tool(self, tool_name: str, arguments: Dict = None) -> MCPToolResult:
        """
        自动查找并调用工具（跨服务器）
        
        遍历所有服务器，找到第一个匹配的工具并调用。
        如果多个服务器有同名工具，只调用第一个。
        """
        result = self.find_tool(tool_name)
        if not result:
            return MCPToolResult(
                tool=tool_name,
                args=arguments or {},
                result=None,
                error=f"Tool '{tool_name}' not found in any server",
                success=False
            )
        
        server_name, _ = result
        return self.call_tool(server_name, tool_name, arguments)
    
    def list_servers(self) -> List[str]:
        """列出已配置的服务器名称"""
        return list(self._configs.keys())
    
    def get_server_status(self) -> Dict[str, str]:
        """获取所有服务器状态"""
        return {
            name: "connected" if name in self._servers else "disconnected"
            for name in self._configs.keys()
        }
    
    def __repr__(self) -> str:
        connected = len(self._servers)
        total = len(self._configs)
        return f"<MCPServerManager servers={connected}/{total}>"


# ═══════════════════════════════════════════════════════════════════════════
# MCP Hub — 全局 MCP 管理器（单例）
# ═══════════════════════════════════════════════════════════════════════════

_mcp_hub: Optional[MCPServerManager] = None


def get_mcp_hub() -> MCPServerManager:
    """获取全局 MCP Hub 单例"""
    global _mcp_hub
    if _mcp_hub is None:
        _mcp_hub = MCPServerManager()
    return _mcp_hub


def setup_mcp_from_config(config: Dict) -> Dict[str, bool]:
    """
    从配置初始化 MCP 服务器
    
    配置格式：
    ```yaml
    mcp:
      servers:
        filesystem:
          transport: stdio
          command: npx
          args: ["-y", "@modelcontextprotocol/server-filesystem", "."]
        github:
          transport: http
          url: https://api.github.com/mcp
          headers:
            Authorization: "Bearer ${GITHUB_TOKEN}"
    ```
    """
    hub = get_mcp_hub()
    results = {}
    
    servers = config.get("mcp", {}).get("servers", {})
    for name, server_config in servers.items():
        cfg = MCPServerConfig(
            name=name,
            transport=server_config.get("transport", "stdio"),
            command=server_config.get("command", ""),
            args=server_config.get("args", []),
            env=server_config.get("env", {}),
            url=server_config.get("url", ""),
            headers=server_config.get("headers", {}),
            timeout=server_config.get("timeout", 120),
        )
        
        error = hub.add_server(cfg)
        if error:
            print(f"[MCP] Failed to add server '{name}': {error}")
            results[name] = False
        else:
            results[name] = True
    
    # 连接所有服务器
    connect_results = hub.connect_all()
    for name, success in connect_results.items():
        results[f"{name}.connect"] = success
    
    return results
