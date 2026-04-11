#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_console.py — 聚活 网页控制台
类似 OpenClaw 风格的简易网页交互界面

Usage:
    python web_console.py
    然后打开浏览器访问 http://localhost:9876
"""

import sys
import os
import datetime
from pathlib import Path
# 添加当前目录到路径，让导入能找到
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


app = FastAPI(title="聚活 网页控制台", version="1.0")


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
    {"id": "chat", "name": "💬 对话聊天", "description": "持续对话，自动触发功能"},
    {"id": "judgment", "name": "🎯 十维判断", "description": "对问题进行十维分析"},
    {"id": "action_plan", "name": "⚡ 行动规划", "description": "生成四象限行动清单"},
    {"id": "action_signal", "name": "🤖 行动信号", "description": "输出机器人可执行信号"},
    {"id": "goals", "name": "🎯 目标系统", "description": "查看目标层级与一致性"},
    {"id": "causal_memory", "name": "📚 因果记忆", "description": "检索相关历史因果"},
    {"id": "curiosity", "name": "🚀 好奇心", "description": "查看待探索议题"},
    {"id": "export", "name": "📝 导出会话", "description": "导出当前会话为 Markdown"},
    {"id": "llm_config", "name": "🔌 大模型配置", "description": "配置大模型API接入"},
    {"id": "stats", "name": "📊 系统统计", "description": "查看全系统统计信息"},
]


# ── HTML 首页 ───────────────────────────────────────────────────────

INDEX_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>聚活 — 个人数字分身控制台</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        base: {
                            900: '#f8f5f3',
                            800: '#f0ebe8',
                            700: '#e8e0dc',
                            600: '#d6c8c3',
                            500: '#bfa8a3',
                            400: '#a68f8a',
                            300: '#8d7570',
                        },
                        accent: {
                            DEFAULT: '#b76e63',     /* 莫兰迪低饱和红棕色，非常低饱和 */
                            hover: '#a55d52',
                        },
                        success: '#8aa88f',
                        warning: '#c9a382',
                        danger: '#b76e63',
                        text: {
                            DEFAULT: '#2d2a28',
                            muted: '#645e5c',
                            light: '#8a8380',
                        }
                    },
                    fontFamily: {
                        sans: ['Outfit', 'system-ui', '-apple-system', 'sans-serif'],
                    },
                    backdropBlur: {
                        xs: '2px',
                    }
                }
            }
        }
    </script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        
        * {
            box-sizing: border-box;
        }
        
        html, body {
            height: 100dvh;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }
        
        body {
            background: radial-gradient(ellipse at top, #f5ebe8 0%, #e6ddd9 100%);
            font-family: 'Outfit', system-ui, -apple-system, sans-serif;
        }
        
        /* Glassmorphism - 莫兰迪低饱和红棕 */
        .glass {
            background: rgba(255, 255, 255, 0.55);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(183, 110, 99, 0.18);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8), 0 8px 32px rgba(140, 80, 70, 0.10);
        }
        
        .glass-card {
            background: rgba(255, 255, 255, 0.4);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1px solid rgba(183, 110, 99, 0.12);
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }
        
        .glass-card:hover {
            background: rgba(255, 255, 255, 0.65);
            border-color: rgba(183, 110, 99, 0.30);
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(183, 110, 99, 0.10);
        }
        
        .glass-card.active {
            background: rgba(183, 110, 99, 0.18);
            border-color: rgba(183, 110, 99, 0.45);
            box-shadow: 0 8px 24px rgba(183, 110, 99, 0.15);
        }
        
        /* Scrollbar styling - 莫兰迪低饱和红棕 */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(183, 110, 99, 0.06);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(183, 110, 99, 0.20);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(183, 110, 99, 0.35);
        }
        
        /* Message bubbles - 莫兰迪低饱和红棕 */
        .message-user {
            background: linear-gradient(135deg, rgba(183, 110, 99, 0.25), rgba(183, 110, 99, 0.06));
            border: 1px solid rgba(183, 110, 99, 0.30);
        }
        .message-assistant {
            background: rgba(255, 255, 255, 0.45);
            border: 1px solid rgba(183, 110, 99, 0.12);
        }
        .message-system {
            background: rgba(183, 110, 99, 0.12);
            border: 1px solid rgba(183, 110, 99, 0.25);
        }
        
        /* Button hover animation */
        .btn {
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .btn:hover {
            transform: translateY(-1px);
        }
        .btn:active {
            transform: translateY(0);
        }
        
        /* Focus ring */
        .input-focus:focus {
            outline: none;
            box-shadow: 0 0 0 3px rgba(124, 102, 240, 0.25);
            border-color: rgba(124, 102, 240, 0.6);
        }
    </style>
</head>
<body class="text-text">
    <div class="flex h-full w-full gap-3 p-3">
        <!-- 左侧侧边栏 → 玻璃态 -->
        <aside class="w-64 flex flex-col glass rounded-2xl overflow-hidden">
            <div class="p-5 border-b border-base-300/40">
                <h1 class="text-2xl font-bold bg-gradient-to-r from-text to-text-muted bg-clip-text text-transparent">聚活</h1>
                <p class="text-text-muted text-sm font-light mt-1">个人数字分身控制台</p>
            </div>
            
            <div class="flex-1 overflow-y-auto p-3 space-y-2">
"""

# 动态生成模块按钮
for module in FUNCTION_MODULES:
    content = f'''
                <button class="module-btn w-full glass-card text-left px-4 py-3 rounded-xl cursor-pointer {('active' if module['id'] == 'chat' else '')}" data-module="{module['id']}" onclick="loadModule('{module['id']}')">
                    <div class="font-medium text-sm">{module['name']}</div>
                    <div class="text-xs text-slate-400 mt-1 font-light">{module['description']}</div>
                </button>
'''
    globals()['INDEX_HTML'] += content

INDEX_HTML += """
            </div>
            
            <div class="p-4 border-t border-base-300/40">
                <div class="text-xs text-text-light font-light">
                    聚活 · OpenSpace 驱动<br>
                    记住你的一切，代替你永远活下去
                </div>
            </div>
        </aside>

        <!-- 右侧主内容区 -->
        <main class="flex-1 flex flex-col glass rounded-2xl overflow-hidden">
            <!-- 聊天/结果区域 -->
            <div id="chatContainer" class="flex-1 overflow-y-auto p-6 space-y-6">
                <div class="message-system px-5 py-4 rounded-xl">
                    <h2 class="font-semibold text-lg mb-2 text-text">👋 欢迎来到聚活</h2>
                    <p class="text-text-muted text-sm leading-relaxed">
                        聚活是你的个人数字分身，基于 OpenSpace 自我进化引擎。<br>
                        • 在下方输入问题或对话，系统会自动触发十维判断、行动规划、因果记忆记录<br>
                        • 点击左侧按钮快速访问各个功能模块<br>
                        • 对话会自动记录，支持导出为 Markdown 存档
                    </p>
                </div>
            </div>
            
            <!-- 底部输入区 -->
            <div class="border-t border-base-300/40 p-4 glass bg-white/[0.35]">
                <div class="flex flex-col gap-3">
                    <!-- Profile selector -->
                    <div class="flex items-center gap-3">
                        <label class="text-sm text-text-muted w-20">身份档案:</label>
                        <select id="profileSelect" class="flex-1 bg-white/50 border border-base-300/40 rounded-lg px-3 py-2 text-sm text-text input-focus">
                            <option value="">default (聚活默认)</option>
                            <option value="guyong">顾庸</option>
                        </select>
                        <label for="pdfUpload" class="cursor-pointer btn bg-white/50 hover:bg-white/70 border border-base-300/40 rounded-lg px-4 py-2 text-sm text-text whitespace-nowrap">
                            📄 上传 PDF
                        </label>
                        <input id="pdfUpload" type="file" accept=".pdf" hidden>
                    </div>
                    <!-- Input area -->
                    <div class="flex gap-3">
                        <input 
                            id="messageInput" 
                            type="text" 
                            placeholder="输入你的问题或对话..."
                            class="flex-1 bg-white/50 border border-base-300/40 rounded-xl px-4 py-3 text-text input-focus"
                        >
                        <button id="sendButton" onclick="sendMessage()" class="btn bg-accent hover:bg-accent-hover px-8 py-3 rounded-xl font-medium text-white shadow-lg shadow-accent/25">
                            发送
                        </button>
                    </div>
                    <div id="pdfStatus" class="text-xs text-text-muted px-1"></div>
                </div>
            </div>
        </main>
    </div>

    <script>
        const chatContainer = document.getElementById('chatContainer');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const profileSelect = document.getElementById('profileSelect');
        const pdfUpload = document.getElementById('pdfUpload');
        const pdfStatus = document.getElementById('pdfStatus');
        
        let currentModule = 'chat';
        let currentPdfFile = null;
        
        function addMessage(content, isUser = false, isSystem = false) {
            const div = document.createElement('div');
            div.className = `message ${isUser ? 'message-user' : (isSystem ? 'message-system' : 'message-assistant')} px-5 py-4 rounded-xl leading-relaxed`;
            
            // 支持换行
            content = content.replace(/\n/g, '<br>');
            div.innerHTML = content;
            
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        
        // 高亮当前模块按钮
        function loadModule(moduleId) {
            // 高亮按钮
            document.querySelectorAll('.module-btn').forEach(b => {
                b.classList.toggle('active', b.dataset.module === moduleId);
            });
            currentModule = moduleId;
            
            addMessage(`正在加载功能模块: ${moduleId}`, true);
            
            fetch('/api/module/' + moduleId, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({profile: profileSelect.value || null, message: messageInput.value})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    addMessage(data.content, false, true);
                } else {
                    addMessage(`错误: ${data.error}`, false, true);
                }
            })
            .catch(e => {
                addMessage(`网络错误: ${e}`, false, true);
            });
            
            sendButton.disabled = false;
            sendButton.textContent = "发送";
        }
        
        async function sendMessage() {
            const text = messageInput.value.trim();
            const profile = profileSelect.value || null;
            
            if (!text && !currentPdfFile) {
                return;
            }
            
            addMessage(text || `[上传 PDF: ${currentPdfFile.name}]`, true);
            messageInput.value = "";
            
            sendButton.disabled = true;
            sendButton.textContent = "思考中...";
            
            if (currentPdfFile) {
                // 上传PDF
                const formData = new FormData();
                formData.append('file', currentPdfFile);
                
                try {
                    const res = await fetch('/api/upload-pdf', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await res.json();
                    if (data.success) {
                        addMessage(data.content, false);
                    } else {
                        addMessage(`错误: ${data.error}`, false, true);
                    }
                } catch (e) {
                    addMessage(`网络错误: ${e}`, false, true);
                }
                
                // 清空
                currentPdfFile = null;
                pdfStatus.textContent = "";
                pdfUpload.value = "";
            } else {
                // 普通聊天
                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({message: text, profile: profile})
                    });
                    const data = await res.json();
                    if (data.success) {
                        addMessage(data.content, false);
                    } else {
                        addMessage(`错误: ${data.error}`, false, true);
                    }
                } catch (e) {
                    addMessage(`网络错误: ${e}`, false, true);
                }
            }
            
            sendButton.disabled = false;
            sendButton.textContent = "发送";
        }
        
        // PDF文件选择
        pdfUpload.onchange = function(e) {
            const file = e.target.files[0];
            if (file) {
                currentPdfFile = file;
                pdfStatus.textContent = ` ✓ 已选择: ${file.name}`;
            }
        };

        // 保存大模型配置
        async function saveLLMConfig(e) {
            e.preventDefault();
            
            const form = e.target;
            const data = {
               
            padding: 10px 12px;
            margin-bottom: 8px;
            background: #333;
            border: 1px solid #444;
            border-radius: 6px;
            color: #ddd;
            text-align: left;
            cursor: pointer;
            transition: all 0.2s;
        }
        .module-btn:hover {
            background: #404040;
            border-color: #2563eb;
        }
        .module-btn.active {
            background: #2563eb;
            border-color: #2563eb;
            color: white;
        }
        .module-btn .desc {
            font-size: 11px;
            color: #999;
            margin-top: 2px;
        }
        .module-btn.active .desc {
            color: #bfdbfe;
        }
        .sidebar-footer {
            margin-top: auto;
            padding-top: 12px;
            border-top: 1px solid #404040;
            font-size: 11px;
            color: #666;
            text-align: center;
        }
        /* 主内容区 */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: #2d2d2d;
            padding: 12px 20px;
            border-bottom: 1px solid #404040;
        }
        .header h1 {
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
        }
        .header p {
            font-size: 12px;
            color: #888;
            margin-top: 4px;
        }
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }
        .message {
            margin-bottom: 16px;
            padding: 12px 16px;
            border-radius: 8px;
            max-width: 95%;
        }
        .message.user {
            background: #2563eb;
            color: white;
            margin-left: auto;
        }
        .message.assistant {
            background: #374151;
            color: white;
            margin-right: auto;
            white-space: pre-wrap;
            line-height: 1.6;
        }
        .message.system {
            background: #2d2d2d;
            color: #888;
            font-size: 13px;
            text-align: center;
            margin: 8px auto;
        }
        .input-area {
            background: #2d2d2d;
            padding: 12px 16px;
            border-top: 1px solid #404040;
            display: flex;
            gap: 12px;
            align-items: center;
        }
        .input-area input[type="text"] {
            flex: 1;
            padding: 12px 16px;
            background: #404040;
            border: 1px solid #555;
            border-radius: 8px;
            color: white;
            font-size: 14px;
            outline: none;
        }
        .input-area input[type="text"]:focus {
            border-color: #2563eb;
        }
        .input-area button {
            padding: 12px 24px;
            background: #2563eb;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
        }
        .input-area button:hover {
            background: #1d4ed8;
        }
        .input-area button:disabled {
            background: #64748b;
            cursor: not-allowed;
        }
        .upload-area {
            padding: 8px 20px;
            background: #2d2d2d;
            border-top: 1px solid #404040;
            display: flex;
            gap: 16px;
            align-items: center;
        }
        .upload-area label {
            font-size: 12px;
            color: #aaa;
        }
        .upload-area input[type="file"] {
            font-size: 12px;
            color: #aaa;
        }
        .upload-area #pdf-status {
            font-size: 12px;
            color: #10b981;
        }
        .loading {
            color: #f59e0b;
        }
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #2d2d2d;
        }
        ::-webkit-scrollbar-thumb {
            background: #555;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #777;
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-header">
            <h2>功能模块</h2>
            <p>点击按钮快速访问</p>
        </div>
        <!-- 动态生成模块按钮 -->
        <div id="module-buttons">
            <!-- JS 填充 -->
        </div>
        <div class="sidebar-footer">
            聚活 / guyong-juhuo<br>
            记住你的一切，代替你永远活下去
        </div>
    </div>

    <div class="main-content">
        <div class="header">
            <h1>聚活 — 数字分身控制台</h1>
            <p>左侧点击功能模块 · 输入问题 · 支持PDF/网页提取</p>
        </div>
        <div class="chat-container" id="chat-container">
            <div class="message assistant">
                👋 欢迎来到聚活！
                <br><br>
                <b>左侧就是各个功能模块按钮，点击即可访问：</b>
                <br>
                • <b>十维判断</b> — 对问题进行完整十维分析
                • <b>行动规划</b> — 生成四象限优先级排序
                • <b>行动信号</b> — 输出机器人可执行JSON格式
                • <b>目标系统</b> — 查看目标层级与一致性检查
                • <b>因果记忆</b> — 检索历史相关因果记忆
                • <b>好奇心</b> — 查看待探索开放议题
                • <b>系统统计</b> — 查看全系统统计信息
                <br><br>
                你也可以直接在下方输入问题，或上传PDF、粘贴网页URL。
            </div>
        </div>
        <div class="upload-area">
            <div>
                <input type="file" id="pdf-upload" accept=".pdf">
                <span id="pdf-status"></span>
            </div>
            <div style="margin-left: auto;">
                <label for="profile">Profile: </label>
                <select id="profile" style="background: #404040; color: white; padding: 4px 8px; border-radius: 4px; border: 1px solid #555;">
                    <option value="">default</option>
                </select>
            </div>
        </div>
        <div class="input-area">
            <input type="text" id="message-input" placeholder="输入问题或者网页 URL...">
            <button id="send-button" onclick="sendMessage()">发送</button>
        </div>
    </div>

<script>
// 功能模块定义
const MODULES = [
    {id: "judgment", name: "十维判断", desc: "对问题进行十维分析"},
    {id: "action_plan", name: "行动规划", desc: "生成四象限行动清单"},
    {id: "action_signal", name: "行动信号", desc: "输出机器人可执行信号"},
    {id: "goals", name: "目标系统", desc: "查看目标层级与一致性"},
    {id: "causal_memory", name: "因果记忆", desc: "检索相关历史因果"},
    {id: "curiosity", name: "好奇心", desc: "查看待探索议题"},
    {id: "stats", name: "系统统计", desc: "查看全系统统计信息"},
];

// 生成模块按钮
const moduleContainer = document.getElementById('module-buttons');
MODULES.forEach(m => {
    const btn = document.createElement('button');
    btn.className = 'module-btn';
    btn.dataset.module = m.id;
    btn.innerHTML = `
        <div><b>${m.name}</b></div>
        <div class="desc">${m.desc}</div>
    `;
    btn.onclick = () => loadModule(m.id);
    moduleContainer.appendChild(btn);
});

const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const pdfUpload = document.getElementById('pdf-upload');
const pdfStatus = document.getElementById('pdf-status');
const profileSelect = document.getElementById('profile');

let currentPdfFile = null;
let currentModule = null;

function addMessage(content, isUser, isSystem) {
    const div = document.createElement('div');
    div.className = `message ${isUser ? 'user' : (isSystem ? 'system' : 'assistant')}`;
    
    // 支持换行
    content = content.replace(/\n/g, '<br>');
    div.innerHTML = content;
    
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 加载功能模块
async function loadModule(moduleId) {
    // 高亮按钮
    document.querySelectorAll('.module-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.module === moduleId);
    });
    currentModule = moduleId;
    
    addMessage(`正在加载功能模块: ${moduleId}`, true);
    
    try {
        const res = await fetch('/api/module/' + moduleId, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({profile: profileSelect.value || null, message: messageInput.value})
        });
        const data = await res.json();
        if (data.success) {
            addMessage(data.content, false);
        } else {
            addMessage(`错误: ${data.error}`, false);
        }
    } catch (e) {
        addMessage(`网络错误: ${e}`, false);
    }
    
    sendButton.disabled = false;
    sendButton.textContent = "发送";
}

async function sendMessage() {
    const text = messageInput.value.trim();
    const profile = profileSelect.value || null;
    
    if (!text && !currentPdfFile) {
        return;
    }
    
    sendButton.disabled = true;
    sendButton.textContent = "思考中...";
    
    if (currentPdfFile) {
        // 上传PDF
        addMessage(`正在处理 PDF: ${currentPdfFile.name}`, true);
        const formData = new FormData();
        formData.append('file', currentPdfFile);
        if (profile) {
            formData.append('profile', profile);
        }
        
        try {
            const res = await fetch('/api/upload-pdf', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                addMessage(data.content, false);
            } else {
                addMessage(`错误: ${data.error}`, false);
            }
        } catch (e) {
            addMessage(`网络错误: ${e}`, false);
        }
        pdfStatus.textContent = "";
        currentPdfFile = null;
        pdfUpload.value = "";
    } else if (text.startsWith('http://') || text.startsWith('https://')) {
        // 处理网页URL
        addMessage(`正在提取网页: ${text}`, true);
        try {
            const res = await fetch('/api/extract-web', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: text, profile: profile})
            });
            const data = await res.json();
            if (data.success) {
                addMessage(data.content, false);
            } else {
                addMessage(`错误: ${data.error}`, false);
            }
        } catch (e) {
            addMessage(`网络错误: ${e}`, false);
        }
        messageInput.value = "";
    } else {
        // 普通文本问题，直接十维判断
        addMessage(text, true);
        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: text, profile: profile})
            });
            const data = await res.json();
            if (data.success) {
                addMessage(data.content, false);
            } else {
                addMessage(`错误: ${data.error}`, false);
            }
        } catch (e) {
            addMessage(`网络错误: ${e}`, false);
        }
        messageInput.value = "";
    }
    
    sendButton.disabled = false;
    sendButton.textContent = "发送";
}

// PDF文件选择
pdfUpload.onchange = function(e) {
    const file = e.target.files[0];
    if (file) {
        currentPdfFile = file;
        pdfStatus.textContent = ` ✓ 已选择: ${file.name}`;
    }
};

// 回车发送
messageInput.onkeypress = function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
};

// 保存大模型配置
async function saveLLMConfig(e) {
    e.preventDefault();
    
    const form = e.target;
    const data = {
        provider: form.provider.value,
        api_key: form.api_key.value,
        api_base: form.api_base.value,
        model_name: form.model_name.value,
        group_id: form.group_id ? form.group_id.value : undefined,
    };
    
    const resultDiv = document.getElementById('llm-config-result');
    resultDiv.innerHTML = '保存中...';
    
    try {
        const res = await fetch('/api/save-llm-config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await res.json();
        if (result.success) {
            resultDiv.innerHTML = '<div style="color: #10b981; padding: 12px; border-radius: 6px; background: rgba(16, 185, 129, 0.1); margin-top: 10px;">' + result.content + '</div>';
            addMessage('✅ 大模型配置保存成功，请重启网页控制台生效', false);
        } else {
            resultDiv.innerHTML = '<div style="color: #ef4444; padding: 12px; border-radius: 6px; background: rgba(239, 68, 68, 0.1); margin-top: 10px;">保存失败: ' + result.error + '</div>';
        }
    } catch (e) {
        resultDiv.innerHTML = '<div style="color: #ef4444; padding: 12px; border-radius: 6px; background: rgba(239, 68, 68, 0.1); margin-top: 10px;">网络错误: ' + e + '</div>';
    }
}
</script>
</body>
</html>
"""


# ── API 端点 ───────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(INDEX_HTML)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        # 十维判断
        result = check10d(request.message)
        report = format_report(result)
        return ChatResponse(success=True, content=report)
    except Exception as e:
        return ChatResponse(success=False, error=str(e))


@app.post("/api/module/{module_id}")
async def get_module(module_id: str, request: ModuleRequest):
    try:
        if module_id == "chat":
            # 初始化聊天系统
            cs = load_chat_system()
            current = get_current_session(cs)
            if current:
                content = f"""【💬 对话聊天系统】
当前已有会话: {current.title}
消息数: {len(current.messages)}

对话系统会：
• 完整记录所有对话历史到文件（chat_history/目录）
• 自动分析内容触发各个功能模块：
  → 收到问题自动触发十维判断
  → 低置信度自动触发好奇心引擎记录
  → 自动生成行动规划
  → 自动输出机器人行动信号
  → 自动记录因果事件供后续进化
• 每日可自动生成进化建议
• 只有你固定使用，身份特质完全锁定

直接在下方输入消息开始对话！
"""
            else:
                content = """【💬 对话聊天系统】
对话系统会：
• 完整记录所有对话历史到文件（chat_history/目录）
• 自动分析内容触发各个功能模块：
  → 收到问题自动触发十维判断
  → 低置信度自动触发好奇心引擎记录
  → 自动生成行动规划
  → 自动输出机器人行动信号
  → 自动记录因果事件供后续进化
• 每日可自动生成进化建议
• 只有你固定使用，身份特质完全锁定

直接在下方输入消息开始对话，新会话会自动创建。
"""
            return ChatResponse(success=True, content=content)
        
        elif module_id == "judgment":
            content = """【十维判断模块】
直接在下方输入框输入问题，点击发送即可进行完整十维分析。

十维包括：
1. 认知维度 — 事实清楚吗？逻辑自洽吗？
2. 博弈维度 — 各方立场利益是什么？
3. 经济维度 — 机会成本？投入产出比？
4. 辩证维度 — 对立面是什么？反方观点？
5. 情绪维度 — 当前情绪影响判断吗？
6. 直觉维度 — 第一感觉是什么？
7. 道德维度 — 符合价值观吗？
8. 社会维度 — 放在环境里合适吗？
9. 时间维度 — 长远看还是急着解决？
10.元认知维度 — 我哪里可能错？有盲区？
"""
            return ChatResponse(success=True, content=content)
        
        elif module_id == "action_plan":
            content = """【行动规划模块】
输入问题后，系统会自动生成四象限行动规划：
- 重要紧急 → 立即处理
- 重要不紧急 → 长期成长，核心是这个，永远不会被遗忘
- 不重要紧急 → 能 delegation 就 delegation
- 不重要不紧急 → 可做可不做

行动规划会按时间压强公式自动排序优先级：
score = importance × (1 + 1/max(days_to_deadline, 1)) × 100
"""
            return ChatResponse(success=True, content=content)
        
        elif module_id == "action_signal":
            content = """【行动信号模块】
生成标准化JSON格式行动信号，输出给机器人/执行器。
机器人可以直接解析JSON执行。

格式包括：
- action_id: 唯一ID
- session_id: 会话ID
- action_type: 预定义类型 (speak/move/click/run_command 等)
- content: 行动内容
- priority: 优先级 1-5
- deadline: 截止时间
- parameters: 自定义参数字典
- metadata: 来源元数据 (置信度/判断来源等)
"""
            return ChatResponse(success=True, content=content)
        
        elif module_id == "goals":
            gs = get_goal_system()
            content = format_hierarchy(gs)
            return ChatResponse(success=True, content=content)
        
        elif module_id == "causal_memory":
            stats = get_statistics()
            content = f"""【因果记忆统计】
总事件数: {stats.total_events}
总因果链接: {stats.total_links}
推断链接: {stats.inferred_links}
个人亲身链接: {stats.personal_links}
平均置信度: {stats.avg_confidence:.2f}
低质量链接待重新验证: {stats.low_quality_links}

输入问题在发送框，可以检索相关因果记忆。
"""
            return ChatResponse(success=True, content=content)
        
        elif module_id == "curiosity":
            ce = CuriosityEngine()
            topics = get_top_open(ce, limit=10)
            content = "【好奇心引擎 — 待探索议题】\n\n"
            for i, topic in enumerate(topics, 1):
                content += f"{i}. {topic.title} (priority: {topic.priority})\n"
                content += f"   触发: {topic.trigger_reason}\n\n"
            content += "总待探索: " + str(len(ce.get_all_open())) + "\n"
            content += "\n锁定兴趣域: 只探索预先锁定的兴趣方向，不浪费认知资源"
            return ChatResponse(success=True, content=content)
        
        elif module_id == "stats":
            # 全系统统计
            causal_stats = get_statistics()
            os_stats = get_openspace_stats()
            ce = CuriosityEngine()
            
            content = "【聚活全系统统计】\n\n"
            content += f"因果记忆:\n  总事件: {causal_stats.total_events}\n  总链接: {causal_stats.total_links}\n  平均置信度: {causal_stats.avg_confidence:.2f}\n\n"
            content += f"OpenSpace 进化:\n  总技能节点: {os_stats.get('total_nodes', 0)}\n  CAPTURED: {os_stats.get('captured', 0)}\n  DERIVED: {os_stats.get('derived', 0)}\n  FIX: {os_stats.get('fix', 0)}\n\n"
            content += f"好奇心:\n  待探索议题: {len(ce.get_all_open())}\n  已解决: {len(ce.get_all_resolved())}\n\n"
            content += "系统状态: 所有模块正常运行\n"
            content += "每个子模块都有独特核心技术支撑\n"
            return ChatResponse(success=True, content=content)
        
        elif module_id == "llm_config":
            # 读取当前配置
            from llm_adapter.config import load_config
            config = load_config()
            
            # 检测当前是否已配置
            from llm_adapter.config import get_adapter
            adapter = get_adapter()
            status = "✅ 已配置并可用" if adapter else "❌ 未配置/配置不正确"
            
            # 填充值
            provider = config["provider"]
            api_key_val = config.get(f"{provider}_api_key", "")
            api_base_val = config.get(f"{provider}_api_base", "") or config.get("openai_api_base", "")
            model_val = config.get(f"{provider}_model", "")
            group_id_val = config.get("minimax_group_id", "")
            
            content = """【🔌 大模型配置】

聚活核心功能**不需要大模型也能完全正常用**！
大模型只用来辅助每日自动进化和知识提取，属于**可选增强**。

当前状态: {status}

当前配置:
• 厂商: {provider}
• 模型: {model}
• API Base / URL: {api_base}
• API Key: {api_key_mask}
• {extra}

请在下方表单填写配置，点击保存即可：

<form id="llm-config-form" onsubmit="saveLLMConfig(event)">
  <div style="margin: 12px 0;">
    <label style="display: block; margin-bottom: 4px;">厂商:</label><br>
    <select name="provider" style="padding: 8px; min-width: 250px; background: #404040; color: white; border: 1px solid #555; border-radius: 6px;">
      <option value="minimax" {sel_minimax}>MiniMax</option>
      <option value="openai" {sel_openai}>OpenAI / 兼容接口</option>
      <option value="ollama" {sel_ollama}>Ollama (本地)</option>
    </select>
  </div>
  <div style="margin: 12px 0;">
    <label style="display: block; margin-bottom: 4px;">API Key:</label><br>
    <input type="password" name="api_key" value="{api_key_val}" placeholder="你的API Key" style="padding: 8px; width: 80%; background: #404040; color: white; border: 1px solid #555; border-radius: 6px;">
  </div>
  <div style="margin: 12px 0;">
    <label style="display: block; margin-bottom: 4px;">API Base / URL (OpenAI/Ollama 需要):</label><br>
    <input type="text" name="api_base" value="{api_base_val}" placeholder="https://api.openai.com/v1 或 http://localhost:11434" style="padding: 8px; width: 80%; background: #404040; color: white; border: 1px solid #555; border-radius: 6px;">
  </div>
  <div style="margin: 12px 0;">
    <label style="display: block; margin-bottom: 4px;">Model Name:</label><br>
    <input type="text" name="model_name" value="{model_val}" placeholder="mini-max-latest" style="padding: 8px; width: 80%; background: #404040; color: white; border: 1px solid #555; border-radius: 6px;">
  </div>
  <div style="margin: 12px 0;" id="minimax-group-section">
    <label style="display: block; margin-bottom: 4px;">MiniMax Group ID:</label><br>
    <input type="text" name="group_id" value="{group_id_val}" placeholder="你的 Group ID" style="padding: 8px; width: 80%; background: #404040; color: white; border: 1px solid #555; border-radius: 6px;">
  </div>
  <div style="margin: 16px 0;">
    <button type="submit" style="background: #2563eb; color: white; border: none; padding: 10px 30px; border-radius: 8px; cursor: pointer; font-size: 15px;">保存配置</button>
  </div>
</form>

<div id="llm-config-result"></div>

💡 提示: 配置保存后需要重启网页控制台生效。
""".format(
                provider=provider,
                status=status,
                model=model_val or "(默认)",
                api_base=(api_base_val or "默认"),
                api_key_mask="***" if api_key_val else "(未设置)",
                api_key_val=api_key_val,
                api_base_val=api_base_val,
                model_val=model_val,
                group_id_val=group_id_val,
                sel_minimax="selected" if provider == "minimax" else "",
                sel_openai="selected" if provider == "openai" else "",
                sel_ollama="selected" if provider == "ollama" else "",
                extra="MiniMax 需要 Group ID" if provider == "minimax" else "",
            )
            return ChatResponse(success=True, content=content)
        
        elif module_id == "export":
            # 导出当前会话为 Markdown
            cs = load_chat_system()
            current = get_current_session(cs)
            if not current:
                content = """❌ 当前没有活跃会话，请先开始对话

导出选项：
- **默认 level=1**：只保留中+高重要性（去冗余，推荐）
- level=0：只保留高重要性（仅决策/反馈，最小存档）
- level=2：保留全部（完整存档，含闲聊）

你可以输入 `export 1` 选择层级，或者直接点按钮导出用默认。
"""
                return ChatResponse(success=True, content=content)
            
            # 从用户输入解析层级
            # 用户可能点按钮或输入 "export 0/1/2"
            level = 1
            if request.message and " " in request.message:
                try:
                    level = int(request.message.strip().split()[-1])
                    if level not in [0, 1, 2]:
                        level = 1
                except:
                    level = 1
            
            # 创建导出目录
            export_dir = Path("exports")
            export_dir.mkdir(exist_ok=True)
            filename = f"dialogue_{current.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_level{level}.md"
            filepath = str(export_dir / filename)
            
            from chat_system import save_dialogue_to_file
            save_dialogue_to_file(current, filepath, level=level)
            
            # 统计一下
            from chat_system import get_importance_level
            stats = {0: 0, 1: 0, 2: 0}
            for msg in current.messages:
                stats[get_importance_level(msg)] += 1
            
            content = f"""✅ 导出成功！

当前会话已保存为 Markdown 文件：

`{filepath}`

## 筛选层级：level={level}
- 🔴 **高重要性**：{stats[2]} 条（完整保存）— 十维判断/进化/反馈/因果/系统消息
- 🟡 **中等重要性**：{stats[1]} 条（完整保存）— 8-20字内容
- 🟢 **低重要性**：{stats[0]} 条（仅摘要）— <8字短消息/闲聊

## 保存内容：
- 按重要性分层归档
- 完整对话（根据筛选层级）
- 触发功能统计
- 进化记录（如果有）

你可以在 `exports/` 目录找到所有导出文件。
想要不同筛选等级？输入 `export 0` 或 `export 2` 重新导出。
"""
            return ChatResponse(success=True, content=content)
        
        else:
            return ChatResponse(success=False, error=f"未知模块: {module_id}")
            
    except Exception as e:
        return ChatResponse(success=False, error=str(e))


@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        # 保存到临时文件
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            content = await file.read()
            f.write(content)
            temp_path = f.name
        
        # 提取并判断
        af = AttentionFilter()
        md = extract_pdf_to_judgment_input(temp_path, af)
        result = check10d(md)
        report = format_report(result)
        
        # 删除临时文件
        os.unlink(temp_path)
        
        return ChatResponse(success=True, content=report)
    except Exception as e:
        return ChatResponse(success=False, error=str(e))


@app.post("/api/extract-web")
async def extract_web(request: ExtractWebRequest):
    try:
        af = AttentionFilter()
        md = extract_web_to_judgment_input(request.url, af)
        result = check10d(md)
        report = format_report(result)
        return ChatResponse(success=True, content=report)
    except Exception as e:
        return ChatResponse(success=False, error=str(e))


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        # 使用聊天系统自动处理，自动触发所有功能
        cs = load_chat_system()
        response, result = cs.process_user_message(request.message, auto_trigger=True)
        return ChatResponse(success=True, content=response)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ChatResponse(success=False, error=str(e))


@app.post("/api/save-llm-config")
async def save_llm_config(request: LLMConfigRequest):
    """保存大模型配置到 .env 文件"""
    try:
        env_lines = []
        
        # 写入配置
        env_lines.append(f"JUHUO_LLM_PROVIDER={request.provider}")
        
        if request.provider == "minimax":
            if request.api_key:
                env_lines.append(f"MINIMAX_API_KEY={request.api_key}")
            if request.group_id:
                env_lines.append(f"MINIMAX_GROUP_ID={request.group_id}")
            if request.model_name:
                env_lines.append(f"MINIMAX_MODEL={request.model_name}")
                
        elif request.provider == "openai":
            if request.api_key:
                env_lines.append(f"OPENAI_API_KEY={request.api_key}")
            if request.api_base:
                env_lines.append(f"OPENAI_API_BASE={request.api_base}")
            if request.model_name:
                env_lines.append(f"OPENAI_MODEL={request.model_name}")
                
        elif request.provider == "ollama":
            if request.api_base:
                env_lines.append(f"OLLAMA_API_BASE={request.api_base}")
            if request.model_name:
                env_lines.append(f"OLLAMA_MODEL={request.model_name}")
        
        # 写入 .env 文件
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(env_lines) + "\n")
        
        content = """✅ 配置保存成功！

配置已写入 `.env` 文件。

**请重启网页控制台生效**：
- 关闭当前运行的 `python web_console.py`
- 重新启动 `python web_console.py`

重启后配置就会生效了。
"""
        return ChatResponse(success=True, content=content)
    except Exception as e:
        return ChatResponse(success=False, error=str(e))


@app.post("/api/generate-action-signal")
async def generate_action_signal(request: ChatRequest):
    try:
        # 先判断，再生成行动规划，再生成信号
        result = check10d(request.message)
        action_plan = generate_action_plan(request.message, result)
        signals = generate_action_signals(action_plan, session_id="web-console")
        robot_json = format_for_robot(signals)
        content = f"""生成完成！共 {len(signals)} 个行动信号:\n\n{robot_json}
        
可以复制这个JSON给机器人直接执行。
"""
        return ActionSignalResponse(
            success=True,
            content=content,
            robot_json=robot_json
        )
    except Exception as e:
        return ActionSignalResponse(success=False, error=str(e))


@app.post("/api/save-llm-config")
async def save_llm_config(request: LLMConfigRequest):
    """保存大模型配置到配置文件"""
    try:
        # 保存到 llm_adapter/user_config.json
        config_path = os.path.join(os.path.dirname(__file__), "llm_adapter", "user_config.json")
        
        config = {
            "provider": request.provider,
            "minimax_api_key": request.api_key if request.provider == "minimax" else "",
            "minimax_group_id": request.group_id if request.provider == "minimax" else "",
            "minimax_model": request.model_name or "mini-max-latest",
            "openai_api_key": request.api_key if request.provider == "openai" else "",
            "openai_model": request.model_name or "gpt-4o",
            "openai_api_base": request.api_base or "https://api.openai.com/v1",
            "ollama_model": request.model_name or "llama3:8b",
            "ollama_api_base": request.api_base or "http://localhost:11434",
        }
        
        # 目录不存在创建
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            import json
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return ChatResponse(
            success=True,
            content=f"""✅ 配置保存成功！

配置已保存到：
{config_path}

请重启网页控制台生效。

配置内容：
- 厂商: {request.provider}
- 模型: {request.model_name or '(默认)'}
- API Base: {request.api_base or '(默认)'}
"""
        )
    except Exception as e:
            return ChatResponse(success=False, error=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9876)
