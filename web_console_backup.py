#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_console.py — 聚活 网页控制台 v2
更美、更有设计感、更有层次感的UI

Usage:
    python web_console.py
    然后打开浏览器访问 http://localhost:9876
"""

import sys
import os
import datetime
from pathlib import Path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import tempfile
from typing import Optional, List

from perception import (
    extract_pdf_to_judgment_input,
    extract_web_to_judgment_input,
    AttentionFilter,
)
from action_signal import (
    ActionSignal,
    generate_action_signals,
    format_for_robot,
    save_to_file,
)
from router import check10d, format_report
from action_system.action_system import ActionPlan, generate_action_plan
from goal_system.goal_system import get_goal_system, format_hierarchy
from causal_memory.causal_memory import get_statistics, recall_causal_history
from curiosity.curiosity_engine import CuriosityEngine, get_top_open
from openspace import get_stats as get_openspace_stats
from chat_system import load_chat_system, get_current_session


app = FastAPI(title="聚活 网页控制台", version="2.0")


# ── API 模型 ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    profile: Optional[str] = None

class ExtractWebRequest(BaseModel):
    url: str
    profile: Optional[str] = None

class ModuleRequest(BaseModel):
    profile: Optional[str] = None

class ActionSignalResponse(BaseModel):
    success: bool
    content: Optional[str] = None
    robot_json: Optional[str] = None
    error: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None

class LLMConfigRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    model_name: Optional[str] = None
    group_id: Optional[str] = None

class ExportRequest(BaseModel):
    session_id: str


# ── 功能模块定义 ─────────────────────────────────────────────────────

FUNCTION_MODULES = [
    {"id": "chat", "name": "对话聊天", "icon": "💬", "group": "核心功能", "description": "持续对话，自动触发功能"},
    {"id": "judgment", "name": "十维判断", "icon": "🎯", "group": "核心功能", "description": "对问题进行十维分析"},
    {"id": "action_plan", "name": "行动规划", "icon": "⚡", "group": "核心功能", "description": "生成四象限行动清单"},
    {"id": "action_signal", "name": "行动信号", "icon": "🤖", "group": "核心功能", "description": "输出机器人可执行信号"},
    {"id": "goal", "name": "目标系统", "icon": "🎯", "group": "个人成长", "description": "查看洋葱目标层级"},
    {"id": "causal_memory", "name": "因果记忆", "icon": "🧠", "group": "个人成长", "description": "查看个人因果链"},
    {"id": "curiosity", "name": "好奇心引擎", "icon": "✨", "group": "个人成长", "description": "探索兴趣领域"},
    {"id": "openspace", "name": "OpenSpace进化", "icon": "🔄", "group": "个人成长", "description": "查看进化状态"},
    {"id": "chat_history", "name": "对话历史", "icon": "📜", "group": "工具箱", "description": "查看历史对话"},
    {"id": "export", "name": "导出会话", "icon": "📝", "group": "工具箱", "description": "导出对话记录"},
    {"id": "llm_config", "name": "大模型配置", "icon": "🔌", "group": "工具箱", "description": "配置大模型参数"},
    {"id": "help", "name": "帮助文档", "icon": "❓", "group": "帮助", "description": "使用说明"},
]


# ── HTML 页面 ────────────────────────────────────────────────────────

HTML_CONTENT = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>聚活 - 网页控制台</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #E85A5A;
            --primary-light: #FF7B7B;
            --primary-dark: #C94A4A;
            --primary-bg: rgba(232, 90, 90, 0.08);
            --primary-border: rgba(232, 90, 90, 0.2);
            --bg-primary: #F8F9FA;
            --bg-secondary: #FFFFFF;
            --bg-tertiary: #F1F3F5;
            --text-primary: #212529;
            --text-secondary: #495057;
            --text-muted: #868E96;
            --border: #DEE2E6;
            --border-light: #E9ECEF;
            --accent: #4C6EF5;
            --accent-light: #748FFC;
            --success: #51CF66;
            --warning: #FAB005;
            --danger: #FF6B6B;
            --info: #339AF0;
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
            --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
            --shadow-lg: 0 8px 24px rgba(0,0,0,0.12);
            --shadow-card: 0 2px 8px rgba(0,0,0,0.06);
            --space-xs: 4px;
            --space-sm: 8px;
            --space-md: 16px;
            --space-lg: 24px;
            --space-xl: 32px;
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 16px;
            --sidebar-width: 260px;
            --header-height: 64px;
        }
        
        .dark-mode {
            --bg-primary: #1A1A2E;
            --bg-secondary: #16213E;
            --bg-tertiary: #0F3460;
            --text-primary: #E8E8E8;
            --text-secondary: #B0B0B0;
            --text-muted: #707070;
            --border: #2D3748;
            --border-light: #2D3748;
            --shadow-card: 0 2px 8px rgba(0,0,0,0.3);
            --primary-bg: rgba(232, 90, 90, 0.15);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }
        
        /* 顶部导航 */
        .header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: var(--header-height);
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-light);
            display: flex;
            align-items: center;
            padding: 0 var(--space-lg);
            z-index: 100;
            box-shadow: var(--shadow-sm);
        }
        
        .header-logo {
            font-size: 20px;
            font-weight: 700;
            color: var(--primary);
            margin-right: auto;
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }
        
        .header-logo span {
            background: linear-gradient