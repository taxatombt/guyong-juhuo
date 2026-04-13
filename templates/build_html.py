# -*- coding: utf-8 -*-
"""Generate HTML template for web console v2"""
output_path = r'E:\juhuo\templates\web_console_v2.html'

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>聚活 - 个人数字分身</title>
<style>
:root{--p:#E85A5A;--p-l:#FF7B7B;--p-d:#C94A4A;--p-bg:rgba(232,90,90,.08);--bg:#F8F9FA;--bg2:#fff;--bg3:#F1F3F5;--t:#212529;--t2:#495057;--t3:#868E96;--b:#DEE2E6;--sh:0 1px 3px rgba(0,0,0,.04);--sh2:0 4px 12px rgba(0,0,0,.08);--s4:4px;--s8:8px;--s16:16px;--s24:24px;--s32:32px;--r6:6px;--r10:10px;--r16:16px;--sw:260px;--hh:60px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Inter,Segoe UI,sans-serif;background:var(--bg);color:var(--t);line-height:1.6;min-height:100vh}
.header{position:fixed;top:0;left:0;right:0;height:var(--hh);background:var(--bg2);border-bottom:1px solid var(--b);display:flex;align-items:center;padding:0 var(--s32);z-index:100}
.logo{display:flex;align-items:center;gap:var(--s8)}
.logo-icon{width:36px;height:36px;background:var(--p);color:#fff;border-radius:var(--r10);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px}
.logo-text{font-weight:700;font-size:18px;color:var(--t)}
.header-center{flex:1;max-width:480px;margin:0 var(--s32)}
.search-box{position:relative;display:flex;align-items:center}
.search-input{width:100%;padding:var(--s8) var(--s16);padding-left:40px;border:1px solid var(--b);border-radius:var(--r16);background:var(--bg);font-size:14px;transition:all .2s}
.search-input:focus{outline:none;border-color:var(--p);box-shadow:0 0 0 3px var(--p-bg)}
.search-icon{position:absolute;left:12px;color:var(--t3)}
.search-shortcut{position:absolute;right:12px;font-size:11px;color:var(--t3);background:var(--bg3);padding:2px 6px;border-radius:4px}
.header-right{display:flex;gap:var(--s8)}
.btn{padding:var(--s8) var(--s16);border:none;border-radius:var(--r6);cursor:pointer;font-size:14px;font-weight:500;transition:all .2s}
.btn-primary{background:var(--p);color:#fff}
.btn-primary:hover{background:var(--p-d)}
.btn-secondary{background:var(--bg3);color:var(--t2)}
.btn-secondary:hover{background:var(--b)}
.sidebar{position:fixed;top:var(--hh);left:0;bottom:0;width:var(--sw);background:var(--bg2);border-right:1px solid var(--b);overflow-y:auto;padding:var(--s16) 0}
.nav-section{margin-bottom:var(--s16)}
.nav-section-title{font-size:11px;font-weight:600;color:var(--t3);text-transform:uppercase;padding:var(--s8) var(--s16);letter-spacing:.5px}
.nav-item{display:flex;align-items:center;gap:var(--s12);padding:var(--s12) var(--s16);cursor:pointer;transition:all .15s;border-left:3px solid transparent}
.nav-item:hover{background:var(--bg)}
.nav-item.active{background:var(--p-bg);border-left-color:var(--p)}
.nav-icon{width:32px;height:32px;border-radius:var(--r6);background:var(--bg3);color:var(--t2);display:flex;align-items:center;justify-content:center;transition:all .15s}
.nav-item:hover .nav-icon,.nav-item.active .nav-icon{background:var(--p);color:#fff}
.nav-text{flex:1;min-width:0}
.nav-name{font-size:14px;font-weight:500;color:var(--t)}
.nav-desc{font-size:11px;color:var(--t3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.main{margin-left:var(--sw);padding:var(--s32);margin-top:var(--hh)}
.page{display:none}
.page.active{display:block}
.page-title{font-size:28px;font-weight:700;margin-bottom:var(--s8)}
.page-subtitle{font-size:14px;color:var(--t3);margin-bottom:var(--s24)}
.card{background:var(--bg2);border-radius:var(--r16);padding:var(--s24);margin-bottom:var(--s24);box-shadow:var(--sh);border:1px solid var(--b)}
.card:hover{box-shadow:var(--sh2)}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--s16);padding-bottom:var(--s16);border-bottom:1px solid var(--b)}
.card-title{font-size:16px;font-weight:600;display:flex;align-items:center;gap:var(--s8)}
.card-icon{width:32px;height:32px;border-radius:var(--r6);background:var(--p-bg);color:var(--p);display:flex;align-items:center;justify-content:center}
.badge{font-size:11px;padding:2px 8px;border-radius:10px;font-weight:500}
.badge-success{background:rgba(64,192,87,.1);color:#40C057}
.input-group{margin-bottom:var(--s16)}
.input-label{display:block;font-size:13px;font-weight:500;color:var(--t2);margin-bottom:var(--s4)}
.input,.textarea,.select{width:100%;padding:var(--s8) var(--s12);border:1px solid var(--b);border-radius:var(--r6);font-size:14px;transition:all .2s}
.input:focus,.textarea:focus,.select:focus{outline:none;border-color:var(--p);box-shadow:0 0 0 3px var(--p-bg)}
.textarea{min-height:100px;resize:vertical}
.grid{display:grid;gap:var(--s16)}
.grid-2{grid-template-columns:repeat(2,1fr)}
.grid-3{grid-template-columns:repeat(3,1fr)}
.stat-card{background:var(--bg2);border-radius:var(--r10);padding:var(--s16);text-align:center;border:1px solid var(--b)}
.stat-value{font-size:28px;font-weight:700;color:var(--p)}
.stat-label{font-size:12px;color:var(--t3);margin-top:var(--s4)}
.loading{padding:var(--s32);text-align:center;color:var(--t3)}
.loading::after{content:"";display:inline-block;width:20px;height:20px;border:2px solid var(--b);border-top-color:var(--p);border-radius:50%;animation:spin .8s linear infinite;margin-left:var(--s8)}
@keyframes spin{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:24px;right:24px;padding:var(--s12) var(--s24);background:var(--t);color:#fff;border-radius:var(--r8);font-size:14px;z-index:1000;animation:fadeIn .2s}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}}
@media(max-width:768px){.sidebar{display:none}.main{margin-left:0}.grid-2,.grid-3{grid-template-columns:1fr}.header-center{display:none}}
</style>
</head>
<body>
<header class="header">
<div class="logo"><div class="logo-icon">聚</div><span class="logo-text">聚活</span></div>
<div class="header-center">
<div class="search-box">
<svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
<input type="text" class="search-input" placeholder="搜索功能..." id="searchInput">
</div>
</div>
<div class="header-right">
<button class="btn btn-secondary" onclick="toggleDarkMode()">暗模式