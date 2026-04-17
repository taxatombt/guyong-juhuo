#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_console.py — Juhuo Web Console

轻量级 Web 界面：
- / → 主页 + 判断输入
- /api/judge → 判断 API
- /api/verdict → verdict 管理
- /api/status → 状态查看
"""

from flask import Flask, request, jsonify, render_template_string
from pathlib import Path
import argparse

from judgment.logging_config import get_logger
from judgment.pipeline import check10d_full, PipelineConfig, format_full_report
from judgment.self_model.belief import get_belief_status
from judgment.verdict_collector import get_verdict_stats
from causal_memory.causal_chain import get_recent_chains

log = get_logger("juhuo.web")

app = Flask(__name__)

# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Juhuo - Judgment System</title>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #1a1a2e; color: #eee; }
        h1 { color: #e94560; text-align: center; }
        .input-area { background: #16213e; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        textarea { width: 100%; height: 100px; background: #0f3460; color: #fff; border: none; border-radius: 5px; padding: 10px; font-size: 16px; }
        button { background: #e94560; color: #fff; border: none; padding: 10px 30px; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background: #c73e54; }
        .result { background: #16213e; padding: 20px; border-radius: 10px; margin-top: 20px; }
        .dimension { display: flex; align-items: center; margin: 10px 0; }
        .dim-name { width: 120px; font-weight: bold; }
        .dim-bar { flex: 1; background: #0f3460; height: 20px; border-radius: 10px; margin: 0 10px; }
        .dim-fill { height: 100%; background: linear-gradient(90deg, #e94560, #ff6b6b); border-radius: 10px; }
        .dim-score { width: 50px; text-align: right; }
        .verdict { text-align: center; font-size: 24px; margin-top: 20px; color: #e94560; }
        .nav { text-align: center; margin-bottom: 20px; }
        .nav a { color: #fff; margin: 0 10px; text-decoration: none; }
        .nav a:hover { color: #e94560; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
        .stat-box { background: #16213e; padding: 15px; border-radius: 10px; text-align: center; }
        .stat-num { font-size: 32px; color: #e94560; }
        .stat-label { color: #888; }
    </style>
</head>
<body>
    <h1>⚖️ Juhuo Judgment System</h1>
    
    <div class="nav">
        <a href="/">判断</a>
        <a href="/status">状态</a>
        <a href="/history">历史</a>
    </div>
    
    <div class="input-area">
        <textarea id="task" placeholder="输入你想判断的问题..."></textarea>
        <br><br>
        <button onclick="submitJudge()">判断</button>
    </div>
    
    <div id="result"></div>
    
    <script>
    function submitJudge() {
        const task = document.getElementById('task').value;
        if (!task) return;
        
        document.getElementById('result').innerHTML = '<p style="text-align:center">分析中...</p>';
        
        fetch('/api/judge', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({task})
        })
        .then(r => r.json())
        .then(data => {
            let html = '<div class="result">';
            html += '<h3>判断结果</h3>';
            html += '<div class="verdict">' + data.verdict + '</div>';
            html += '<p style="text-align:center;color:#888">置信度: ' + (data.confidence * 100).toFixed(1) + '%</p>';
            
            html += '<h4>各维度分析</h4>';
            for (const [dim, info] of Object.entries(data.dimensions || {})) {
                const pct = Math.round(info.score * 100);
                html += '<div class="dimension">';
                html += '<span class="dim-name">' + dim + '</span>';
                html += '<div class="dim-bar"><div class="dim-fill" style="width:' + pct + '%"></div></div>';
                html += '<span class="dim-score">' + pct + '%</span>';
                html += '</div>';
            }
            
            html += '</div>';
            document.getElementById('result').innerHTML = html;
        })
        .catch(e => {
            document.getElementById('result').innerHTML = '<p style="color:red">错误: ' + e + '</p>';
        });
    }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/status")
def status():
    """系统状态"""
    belief = get_belief_status()
    stats = get_verdict_stats()
    chains = get_recent_chains(limit=5)
    
    return jsonify({
        "belief": belief,
        "verdicts": stats,
        "recent_chains": chains
    })


@app.route("/history")
def history():
    """历史判断"""
    chains = get_recent_chains(limit=20)
    return jsonify({"chains": chains})


@app.route("/api/judge", methods=["POST"])
def judge():
    """判断 API"""
    data = request.get_json()
    task = data.get("task", "")
    
    if not task:
        return jsonify({"error": "任务不能为空"}), 400
    
    try:
        result = check10d_full(task)
        
        # 提取关键结果
        verdict = result.get("verdict", "")
        confidence = result.get("confidence", 0.5)
        dimensions = {}
        
        for dim in result.get("dimensions", []):
            name = dim.get("name", dim.get("dimension", "unknown"))
            score = dim.get("score", 0.5)
            reasoning = dim.get("reasoning", "")
            dimensions[name] = {"score": score, "reasoning": reasoning}
        
        return jsonify({
            "success": True,
            "verdict": verdict,
            "confidence": confidence,
            "dimensions": dimensions,
            "chain_id": result.get("chain_id", "")
        })
    
    except Exception as e:
        log.error(f"Judge error: {e}")
        return jsonify({"error": str(e)}), 500


def run(port: int = 18768):
    """启动 Web Console"""
    log.info(f"Starting Juhuo Web Console on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Juhuo Web Console")
    parser.add_argument("--port", type=int, default=18768, help="Port (default: 18768)")
    args = parser.parse_args()
    run(args.port)
