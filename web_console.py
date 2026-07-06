#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_console.py — Juhuo Web Console

轻量级 Web 界面：
- / → 主页（web_console.html）
- /api/judge → 判断 API
- /api/status → 状态/统计 API
"""

from flask import Flask, request, jsonify, send_file
from pathlib import Path
import argparse

from judgment.logging_config import get_logger
from judgment.pipeline import check10d_full, PipelineConfig, format_full_report
from judgment.router_utils import format_dashboard
from judgment.self_model.belief import get_belief_status
from judgment.verdict_collector import get_verdict_stats
from correlation_memory.correlation_chain import get_recent_chains

log = get_logger("juhuo.web")

app = Flask(__name__)
_ROOT = Path(__file__).parent


@app.route("/")
def index():
    return send_file(_ROOT / "web_console.html")


@app.route("/api/status")
def api_status():
    """轻量状态 API（供 web_console.html 统计卡片用）"""
    stats = get_verdict_stats()
    total = stats.get("total", 0)
    correct = stats.get("correct", 0)
    return jsonify({
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total * 100, 1) if total > 0 else 0,
    })


@app.route("/status")
def status():
    """完整系统状态"""
    belief = get_belief_status()
    stats = get_verdict_stats()
    chains = get_recent_chains(limit=5)
    return jsonify({
        "belief": belief,
        "verdicts": stats,
        "recent_chains": chains,
    })


@app.route("/history")
def history():
    chains = get_recent_chains(limit=20)
    return jsonify({"chains": chains})


@app.route("/api/judge", methods=["POST"])
def judge():
    data = request.get_json()
    task = data.get("task", "")
    if not task:
        return jsonify({"error": "任务不能为空"}), 400
    try:
        result = check10d_full(task)
        dimensions = {}
        for dim in result.get("dimensions", []):
            name = dim.get("name", dim.get("dimension", "unknown"))
            score = dim.get("score", 0.5)
            reasoning = dim.get("reasoning", "")
            dimensions[name] = {"score": score, "reasoning": reasoning}
        return jsonify({
            "success": True,
            "verdict": result.get("verdict", ""),
            "confidence": result.get("confidence", 0.5),
            "dimensions": dimensions,
            "chain_id": result.get("chain_id", ""),
            "dashboard": format_dashboard(result),
        })
    except Exception as e:
        log.error(f"Judge error: {e}")
        return jsonify({"error": str(e)}), 500


def run(port: int = 18768):
    log.info(f"Starting Juhuo Web Console on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Juhuo Web Console")
    parser.add_argument("--port", type=int, default=18768)
    args = parser.parse_args()
    run(args.port)
