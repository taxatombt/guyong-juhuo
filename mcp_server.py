#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server.py — MCP Server

提供 MCP 工具：
- judgment_10d — 十维判断
- judgment_verdict — 标记 verdict
- judgment_status — 查看状态
- benchmark_run — 运行测试
"""

import json
import sys
from pathlib import Path

# MCP Protocol
def mcp_request(method: str, params: dict = None):
    """发送 MCP 请求"""
    request = {"jsonrpc": "2.0", "method": method, "id": 1}
    if params:
        request["params"] = params
    return json.dumps(request)

def mcp_response(result):
    """发送 MCP 响应"""
    return json.dumps({"jsonrpc": "2.0", "id": 1, "result": result})

def mcp_error(code: int, message: str):
    """发送 MCP 错误"""
    return json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": code, "message": message}})


# Tools
TOOLS = [
    {
        "name": "judgment_10d",
        "description": "十维判断分析",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "判断问题"},
                "profile": {"type": "string", "description": "Persona 名称"}
            },
            "required": ["task"]
        }
    },
    {
        "name": "judgment_verdict",
        "description": "标记判断结果",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chain_id": {"type": "string"},
                "correct": {"type": "boolean"}
            },
            "required": ["chain_id"]
        }
    },
    {
        "name": "judgment_status",
        "description": "查看系统状态"
    },
    {
        "name": "benchmark_run",
        "description": "运行 Benchmark",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cases": {"type": "array", "items": {"type": "string"}}
            }
        }
    },
]


def handle_tool_call(tool_name: str, arguments: dict) -> dict:
    """处理工具调用"""
    if tool_name == "judgment_10d":
        from judgment.pipeline import check10d_full
        result = check10d_full(arguments.get("task", ""))
        return {
            "verdict": result.get("verdict", ""),
            "confidence": result.get("confidence", 0),
            "chain_id": result.get("chain_id", ""),
            "dimensions": {
                d.get("name", ""): {"score": d.get("score", 0), "reasoning": d.get("reasoning", "")}
                for d in result.get("dimensions", [])
            }
        }
    
    elif tool_name == "judgment_verdict":
        from judgment.verdict_collector import mark_verdict_correct, mark_verdict_wrong
        if arguments.get("correct"):
            mark_verdict_correct(arguments["chain_id"])
        else:
            mark_verdict_wrong(arguments["chain_id"])
        return {"status": "ok", "chain_id": arguments["chain_id"]}
    
    elif tool_name == "judgment_status":
        from judgment.self_model.belief import get_belief_status
        from judgment.verdict_collector import get_verdict_stats
        return {
            "belief": get_belief_status(),
            "stats": get_verdict_stats()
        }
    
    elif tool_name == "benchmark_run":
        from judgment.benchmark import Benchmark
        bench = Benchmark()
        report = bench.run_all()
        return {
            "accuracy": report.accuracy,
            "passed": report.passed,
            "failed": report.failed,
            "avg_confidence": report.avg_confidence
        }
    
    return {"error": "Unknown tool"}


def main():
    """MCP Server 入口"""
    print("Juhuo MCP Server starting...", file=sys.stderr)
    
    # 读取初始化请求
    init_request = json.loads(sys.stdin.readline())
    print(json.dumps({"jsonrpc": "2.0", "id": init_request.get("id"), "result": {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "juhuo", "version": "1.5"}
    }}), flush=True)
    
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        
        request = json.loads(line)
        method = request.get("method", "")
        tool_call = request.get("params", {}).get("name")
        arguments = request.get("params", {}).get("arguments", {})
        
        if method == "tools/list":
            print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": {"tools": TOOLS}}), flush=True)
        
        elif method == "tools/call":
            try:
                result = handle_tool_call(tool_call, arguments)
                print(json.dumps({
                    "jsonrpc": "2.0", "id": request.get("id"),
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                }), flush=True)
            except Exception as e:
                print(json.dumps({
                    "jsonrpc": "2.0", "id": request.get("id"),
                    "error": {"code": -32603, "message": str(e)}
                }), flush=True)


if __name__ == "__main__":
    main()
