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
from judgment.router_utils import format_dashboard
from judgment.self_model.belief import get_belief_status
from judgment.verdict_collector import get_verdict_stats
from correlation_memory.correlation_chain import get_recent_chains

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
        .view-toggle { margin-bottom: 10px; }
        .view-toggle button { padding: 6px 16px; font-size: 14px; margin-right: 8px; background: #0f3460; }
        .view-toggle button.active { background: #e94560; }
        .dashboard { white-space: pre-wrap; font-family: 'Consolas', monospace; font-size: 14px; line-height: 1.6; color: #e0e0e0; background: #0d1b2a; padding: 16px; border-radius: 8px; border-left: 3px solid #e94560; }
        .dashboard .section-title { color: #e94560; font-weight: bold; font-size: 16px; margin-top: 12px; }
        .dashboard .dim-row { display: flex; align-items: center; margin: 4px 0; }
        .dashboard .dim-name { width: 80px; color: #aaa; }
        .dashboard .dim-bar { flex: 1; background: #1b2838; height: 12px; border-radius: 6px; margin: 0 8px; }
        .dashboard .dim-fill { height: 100%; background: linear-gradient(90deg, #e94560, #ff6b6b); border-radius: 6px; }
        .dashboard .dim-score { width: 40px; text-align: right; color: #888; }
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

    <div class="view-toggle" id="viewToggle" style="display:none">
        <button class="active" data-view="dashboard" onclick="setView('dashboard'); submitJudge()">仪表盘</button>
        <button data-view="bars" onclick="setView('bars'); submitJudge()">维度条</button>
    </div>

    <script>
    // 默认视图
    let currentView = 'dashboard';

    function setView(view) {
        currentView = view;
        document.querySelectorAll('.view-toggle button').forEach(b => {
            b.classList.toggle('active', b.dataset.view === view);
        });
    }

    // 渲染 bar 视图
    function renderBars(data) {
    
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
            
            // 渲染 bar 视图
            function renderBars(data) {
                let html = '<div class="result">';
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
                return html;
            }

            // 渲染 dashboard 视图（来源：daily_stock_analysis）
            function renderDashboard(data) {
                if (!data.dashboard) return renderBars(data);
                // dashboard 文本含分隔线，用 <pre> 渲染
                let html = '<div class="result"><div class="dashboard">' + data.dashboard + '</div></div>';
                return html;
            }

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
                    // 显示视图切换按钮
                    document.getElementById('viewToggle').style.display = 'block';
                    if (currentView === 'dashboard') {
                        document.getElementById('result').innerHTML = renderDashboard(data);
                    } else {
                        document.getElementById('result').innerHTML = renderBars(data);
                    }
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
            "chain_id": result.get("chain_id", ""),
            "dashboard": format_dashboard(result),  # 新增：四维仪表盘（来源：daily_stock_analysis）
        })
    
    except Exception as e:
        log.error(f"Judge error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/execute", methods=["POST"])
def execute_task():
    """
    途径3：执行用户任务，积累行为数据

    流程：
    1. 获取任务描述
    2. 先做判断（check10d_full）
    3. 执行感知工具（web_search / web_analyze）
    4. 记录 agent 行为日志
    5. 返回判断 + 执行结果

    Body:
        {"task": "帮我调研新能源行业", "execute": true, "channel": "web_search"}
    """
    data = request.get_json()
    task = data.get("task", "")
    do_execute = data.get("execute", False)
    channel = data.get("channel", "web_search")

    if not task:
        return jsonify({"error": "任务不能为空"}), 400

    try:
        # Step 1: 判断
        judgment = check10d_full(task)

        behavior_id = ""
        execution_result = ""
        perception_summary = ""
        tool_calls = []

        # Step 2: 执行（若请求）
        if do_execute:
            import time
            from judgment.behavior_logger import (
                log_agent_behavior, ActionChannel, ToolCall
            )
            from perception.web_adapter import WebExtractorAdapter

            exec_start = time.time()
            adapter = WebExtractorAdapter()

            # Web search channel
            if channel == "web_search":
                try:
                    extracted = adapter.extract_from_url(task)
                    perception_summary = f"提取自 {extracted.url}，标题：{extracted.title}"
                    for block in extracted.blocks[:5]:
                        perception_summary += f"\n{block.content[:200]}"
                    execution_result = f"找到 {len(extracted.blocks)} 个内容块"
                    tc = ToolCall(
                        tool_name="WebExtractorAdapter.extract_from_url",
                        arguments={"url": task},
                        result_summary=execution_result[:200],
                        duration_ms=(time.time() - exec_start) * 1000,
                        status="success",
                    )
                    tool_calls = [tc]
                except Exception as ex:
                    execution_result = f"Web extraction failed: {ex}"
                    tool_calls = []

            # 记录行为
            from judgment.behavior_logger import ActionChannel as BLChannel
            channel_map = {"web_search": BLChannel.WEB_SEARCH, "web_analyze": BLChannel.WEB_ANALYZE}
            act_ch = channel_map.get(channel, AC.WEB_SEARCH)
            behavior_id = log_agent_behavior(
                task_text=task,
                channel=act_ch,
                verdict=judgment.get("verdict", ""),
                confidence=judgment.get("confidence", 0.0),
                chain_id=judgment.get("chain_id", ""),
                tool_calls=tool_calls,
                execution_result=execution_result,
                perception_summary=perception_summary,
                outcome_score=-1.0,
                user_id="default",
            )

        return jsonify({
            "success": True,
            "verdict": judgment.get("verdict", ""),
            "confidence": judgment.get("confidence", 0.0),
            "chain_id": judgment.get("chain_id", ""),
            "behavior_id": behavior_id,
            "execution": {
                "channel": channel if do_execute else None,
                "perception_summary": perception_summary,
                "tool_calls_count": len(tool_calls),
            } if do_execute else None,
        })

    except Exception as e:
        log.error(f"Execute error: {e}")
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
