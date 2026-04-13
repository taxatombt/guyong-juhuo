# -*- coding: utf-8 -*-
"""Build HTML template for web console"""
import os
html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>聚活 - 个人数字分身</title>
<style>
:root{--primary:#E85A5A;--primary-light:#FF7B7B;--primary-dark:#C94A4A;--primary-bg:rgba(232,90,90,.08);--bg-primary:#F8F9FA;--bg-secondary:#fff;--bg-tertiary:#F1F3F5;--text-primary:#212529;--text-secondary:#495057;--text-muted:#868E96;--border:#DEE2E6;--shadow-sm:0 1px 3px rgba(0,0,0,.04);--shadow-md:0 4px 12px rgba(0,0,0,.08);--s-xs:4px;--s-sm:8px;--s-md:16px;--s-lg:24px;--s-xl:32px;--r-sm:6px;--r-md:10px;--r-lg:16px;--sw:260px;--hh:60px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Inter,Segoe UI,sans-serif;background:var(--bg-primary);color:var(--text-primary);line-height:1.6;min-height:100vh}
.header{position:fixed;top:0;left:0;right:0;height:var(--hh);background:var(--bg-secondary);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 var(--s-lg);z-index:100}
.logo{display:flex;align-items:center;gap:var(--s-sm)}
.logo-icon{width:32px;height:32px;background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:#fff;border-radius:var(--r-sm);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px}
.logo-text{font-size:16px;font-weight:700}
.header-right{display:flex;align-items:center;gap:var(--s-md)}
.header-btn{width:32px;height:32px;border-radius:var(--r-sm);border:none;background:var(--bg-tertiary);color:var(--text-secondary);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s}
.header-btn:hover{background:var(--border)}
.user-avatar{width:32px;height:32px;background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:14px;cursor:pointer}
.main-layout{display:flex;padding-top:var(--hh)}
.sidebar{width:var(--sw);background:var(--bg-secondary);border-right:1px solid var(--border);position:fixed;top:var(--hh);left:0;bottom:0;overflow-y:auto;padding:var(--s-md) 0}
.nav-section{margin-bottom:var(--s-md)}
.nav-section-title{font-size:11px;font-weight:600;color:var(--text-muted);text-transform:uppercase;padding:0 var(--s-md);margin-bottom:var(--s-xs)}
.nav-item{display:flex;align-items:center;gap:var(--s-sm);padding:var(--s-sm) var(--s-md);cursor:pointer;transition:all .15s;border-left:3px solid transparent}
.nav-item:hover{background:var(--bg-tertiary)}
.nav-item.active{background:var(--primary-bg);border-left-color:var(--primary)}
.nav-icon{width:28px;height:28px;border-radius:var(--r-sm);background:var(--bg-tertiary);display:flex;align-items:center;justify-content:center;font-size:14px;transition:all .2s}
.nav-item:hover .nav-icon,.nav-item.active .nav-icon{background:var(--primary);color:#fff}
.nav-name{font-size:13px;font-weight:500}
.content{flex:1;margin-left:var(--sw);padding:var(--s-xl);max-width:900px}
.page{display:none}
.page.active{display:block}
.page-title{font-size:24px;font-weight:700;margin-bottom:var(--s-xs)}
.page-subtitle{font-size:14px;color:var(--text-muted);margin-bottom:var(--s-xl)}
.card{background:var(--bg-secondary);border-radius:var(--r-lg);padding:var(--s-lg);margin-bottom:var(--s-lg);box-shadow:var(--shadow-sm);border:1px solid var(--border)}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--s-md)}
.card-title{font-size:15px;font-weight:600}
.card-badge{font-size:11px;padding:2px 8px;border-radius:20px;background:var(--primary-bg);color:var(--primary);font-weight:500}
.input{width:100%;padding:var(--s-md);border:1px solid var(--border);border-radius:var(--r-md);font-size:14px;background:var(--bg-primary);color:var(--text-primary)}
.input:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px var(--primary-bg)}
textarea.input{min-height:100px;resize:vertical}
.btn{display:inline-flex;align-items:center;gap:var(--s-sm);padding:var(--s-sm) var(--s-md);border-radius:var(--r-md);font-size:14px;font-weight:500;cursor:pointer;border:none}
.btn-primary{background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:#fff}
.btn-primary:hover{transform:translateY(-1px)}
.btn-secondary{background:var(--bg-tertiary);border:1px solid var(--border)}
.result-box{background:var(--bg-primary);border:1px solid var(--border);border-radius:var(--r-md);padding:var(--s-md);margin-top:var(--s-md);max-height:300px;overflow-y:auto}
.result-box pre{font-family:Consolas,monospace;font-size:13px;white-space:pre-wrap}
.loading{display:flex;align-items:center;padding:var(--s-lg)}
.spinner{width:20px;height:20px;border:2px solid var(--border);border-top-color:var(--primary);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:var(--s-lg);right:var(--s-lg);background:var(--bg-secondary);border:1px solid var(--border);border-radius:var(--r-md);padding:var(--s-sm) var(--s-md);box-shadow:var(--shadow-md);transform:translateY(100px);opacity:0;transition:all .3s;z-index:1000;font-size:14px}
.toast.show{transform:translateY(0);opacity:1}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--s-sm);margin-bottom:var(--s-lg)}
@media(max-width:768px){.sidebar{transform:translateX(-100%)}.content{margin-left:0}}
</style>
</head>
<body>
<header class="header">
<div class="logo"><div class="logo-icon">聚</div><span class="logo-text">聚活</span></div>
<div class="header-right">
<button class="header-btn" onclick="toggleDarkMode()" title="Dark">☾</button>
<div class="user-avatar" onclick="showToast('个人设置')">谷</div>
</div>
</header>
<div class="main-layout">
<aside class="sidebar">
<div class="nav-section">
<div class="nav-section-title">核心功能</div>
<div class="nav-item active" data-page="chat" onclick="navigateTo('chat')"><div class="nav-icon">💬</div><div class="nav-name">对话聊天</div></div>
<div class="nav-item" data-page="judgment" onclick="navigateTo('judgment')"><div class="nav-icon">🎯</div><div class="nav-name">十维判断</div></div>
<div class="nav-item" data-page="action_plan" onclick="navigateTo('action_plan')"><div class="nav-icon">⚡</div><div class="nav-name">行动规划</div></div>
<div class="nav-item" data-page="action_signal" onclick="navigateTo('action_signal')"><div class="nav-icon">🤖</div><div class="nav-name">行动信号</div></div>
</div>
<div class="nav-section">
<div class="nav-section-title">个人成长</div>
<div class="nav-item" data-page="goal" onclick="navigateTo('goal')"><div class="nav-icon">🎯</div><div class="nav-name">目标系统</div></div>
<div class="nav-item" data-page="causal_memory" onclick="navigateTo('causal