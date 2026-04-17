#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_mcp.py - MCP 客户端测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp import (
    MCPServerConfig,
    MCPClient,
    MCPServerManager,
    get_mcp_hub,
    MCPTool,
    MCPToolResult,
    validate_tool_input,
)


def test_mcp_protocol():
    """Test 1: MCP 协议类型"""
    print("[Test 1] MCP Protocol Types")
    
    # 测试 MCPTool
    tool_data = {
        "name": "read_file",
        "description": "Read a file from the filesystem",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"}
            },
            "required": ["path"]
        }
    }
    
    tool = MCPTool.from_dict(tool_data)
    assert tool.name == "read_file"
    assert tool.description == "Read a file from the filesystem"
    print(f"  - MCPTool: {tool.name}")
    
    # 测试参数验证
    error = validate_tool_input(tool.input_schema, {"path": "test.txt"})
    assert error is None, "Valid params should pass"
    
    error = validate_tool_input(tool.input_schema, {})  # 缺少必需参数
    assert error is not None, "Missing params should fail"
    print(f"  - validate_tool_input: OK (rejects missing params)")
    
    return True


def test_server_config():
    """Test 2: 服务器配置"""
    print("[Test 2] Server Configuration")
    
    # stdio 配置
    config = MCPServerConfig(
        name="filesystem",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "."]
    )
    
    error = config.validate()
    assert error is None, "Valid stdio config"
    print(f"  - stdio config: OK")
    
    # 无效配置
    bad_config = MCPServerConfig(name="test", transport="stdio")
    error = bad_config.validate()
    assert error is not None, "Invalid stdio config should fail"
    print(f"  - invalid config rejected: OK")
    
    # HTTP 配置
    http_config = MCPServerConfig(
        name="remote",
        transport="http",
        url="https://example.com/mcp"
    )
    error = http_config.validate()
    assert error is None, "Valid http config"
    print(f"  - http config: OK")
    
    return True


def test_server_manager():
    """Test 3: 服务器管理器"""
    print("[Test 3] Server Manager")
    
    manager = MCPServerManager()
    
    # 添加服务器
    config1 = MCPServerConfig(
        name="fs",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "."]
    )
    
    config2 = MCPServerConfig(
        name="gh",
        transport="http",
        url="https://api.github.com/mcp"
    )
    
    manager.add_server(config1)
    manager.add_server(config2)
    
    assert len(manager.list_servers()) == 2
    print(f"  - add_server: OK ({len(manager.list_servers())} servers)")
    
    # 状态检查
    status = manager.get_server_status()
    assert status["fs"] == "disconnected"
    print(f"  - server status: OK")
    
    # 移除服务器
    manager.remove_server("gh")
    assert len(manager.list_servers()) == 1
    print(f"  - remove_server: OK")
    
    return True


def test_mcp_client_init():
    """Test 4: MCP 客户端初始化"""
    print("[Test 4] MCP Client Init")
    
    config = MCPServerConfig(
        name="test",
        transport="stdio",
        command="echo",
        args=["test"]
    )
    
    client = MCPClient(config)
    assert client.name == "test"
    assert not client.is_connected
    print(f"  - client init: OK")
    
    return True


def test_hub_singleton():
    """Test 5: Hub 单例"""
    print("[Test 5] Hub Singleton")
    
    hub1 = get_mcp_hub()
    hub2 = get_mcp_hub()
    
    assert hub1 is hub2, "Should be same instance"
    print(f"  - singleton: OK")
    
    return True


def run_all_tests():
    print("=" * 50)
    print("Juhuo MCP Client Tests")
    print("=" * 50)
    
    tests = [
        ("MCP Protocol", test_mcp_protocol),
        ("Server Config", test_server_config),
        ("Server Manager", test_server_manager),
        ("MCP Client Init", test_mcp_client_init),
        ("Hub Singleton", test_hub_singleton),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
                print(f"[PASS] {name}\n")
            else:
                failed += 1
                print(f"[FAIL] {name}\n")
        except Exception as e:
            failed += 1
            print(f"[ERROR] {name}: {e}\n")
            import traceback
            traceback.print_exc()
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
