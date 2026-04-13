#!/usr/bin/env python3
# Juhuo Console v2.0 - Minimal Version
import os, sys, datetime, json
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Juhuo Console", version="2.0")

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Juhuo Console</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Segoe UI,sans-serif;background:#F8F9FA;color:#212529;line-height:1.6}
.header{position:fixed;top:0;left:0;right:0;height:60px;background:#fff;border-bottom:1px solid #DEE2E6;display:flex;align-items:center;padding:0 32px}
.logo{display:flex;align-items:center;gap:8px}
.logo-icon{width:32px;height:32px;background:#E85A5A;color:#fff;border-radius:6px;display:flex;align-items:center;justify-content:center;font-weight:700}
.logo-text{font-size:16px;font-weight:700}
.main-layout{display:flex;padding-top:60px}
.sidebar{width:260px;background:#fff;border-right:1px solid #DEE2E6;position:fixed;top:60px;left:0;bottom:0;overflow-y:auto}
.nav-section{margin-bottom:16px}
.nav-section-title{font-size:11px;font-weight:600;color:#868E96;text-transform:uppercase;padding:0 16px;margin-bottom:8px}
.nav-item{display:flex;align-items:center;gap:8px;padding:8px 16px;cursor:pointer;border-left:3px solid transparent}
.nav-item:hover{background:#F1F3F5}
.nav-item.active{background:rgba(232,90,90,.08);border-left-color:#E85A5A;color:#E85A5A}
.nav-icon{width:28px;height:28px;border-radius:6px;background:#F1F3F5;display:flex;align-items:center;justify-content:center;font-size:14px}
.nav-item.active .nav-icon{background:#E85A5A;color:#fff}
.nav-name{font-size:13px;font-weight:500}
.content{flex:1;margin-left:260px;padding:32px;max-width:900px}
.page{display:none}
.page.active{display:block}
.page-title{font-size:24px;font-weight:700;margin-bottom:8px}
.page-subtitle{font-size:14px;color:#868E96;margin-bottom:32px}
.card{background:#fff;border-radius:16px;padding:24px;margin-bottom:24px;border:1px solid #DEE2E6}
.input{width:100%;padding:16px;border:1px solid #DEE2E6;border-radius:10px;font-size:14px;background:#F8F9FA;color:#212529}
.input:focus{outline:none;border-color:#E85A5A}
textarea.input{min-height:100px;resize:vertical}
.btn{display:inline-flex;padding:8px 16px;border-radius:10px;font-size:14px;font-weight:500;cursor:pointer;border:none;background:#E85A5A;color:#fff}
.result-box{background:#F8F9FA;border:1px solid #DEE2E6;border-radius:10px;padding:16px;margin-top:16px;max-height:300px;overflow-y:auto}
.result-box pre{font-family:Consolas,monospace;font-size:13px;white-space:pre-wrap}
.toast{position:fixed;bottom:24px;right:24px;background:#fff;border:1px solid #DEE2E6;border-radius:10px;padding:8px 16px;transform:translateY(100px);opacity:0;transition:all .3s;z-index:1000;font-size:14px}
.toast.show{transform:translateY(0);opacity:1}
</style>
</head>
<body>
<header class="header">
<div class="logo"><div class="logo-icon">J</div><span class="logo-text">Juhuo</span></div>
</header>
<div class="main-layout">
<aside class="sidebar">
<div class="nav-section">
<div class="nav-section-title">Core</div>
<div class="nav-item active" data-page="chat" onclick="navigateTo('chat')"><div class="nav-icon">C</div><div class="nav-name">Chat</div></div>
<div class="nav-item" data-page="judgment" onclick="navigateTo('judgment')"><div class="nav-icon">J</div><div class="nav-name">Judgment</div></div>
<div class="nav-item" data-page="action_plan" onclick="navigateTo('action_plan')"><div class="nav-icon">A</div><div class="nav-name">Action Plan</div></div>
<div class="nav-item" data-page="action_signal" onclick="navigateTo('action_signal')"><div class="nav-icon">S</div><div class="nav-name">Action Signal</div></div>
</div>
<div class="nav-section">
<div class="nav-section-title">Growth</div>
<div class="nav-item" data-page="goal" onclick="navigateTo('goal')"><div class="nav-icon">G</div><div class="nav-name">Goal</div></div>
<div class="nav-item" data-page="causal_memory" onclick="navigateTo('causal_memory')"><div class="nav-icon">M</div><div class="nav-name">Causal Memory</div></div>
<div class="nav-item" data-page="curiosity" onclick="navigateTo('curiosity')"><div class="nav-icon">X</div><div class="nav-name">Curiosity</div></div>
<div class="nav-item" data-page="openspace" onclick="navigateTo('openspace')"><div class="nav-icon">O</div><div class="nav-name">OpenSpace</div></div>
</div>
<div class="nav-section">
<div class="nav-section-title">Tools</div>
<div class="nav-item" data-page="chat_history" onclick="navigateTo('chat_history')"><div class="nav-icon">H</div><div class="nav-name">History</div></div>
<div class="nav-item" data-page="export" onclick="navigateTo('export')"><div class="nav-icon">E</div><div class="nav-name">Export</div></div>
<div class="nav-item" data-page="llm_config" onclick="navigateTo('llm_config')"><div class="nav-icon">S</div><div class="nav-name">Settings</div></div>
</div>
</aside>
<main class="content">
<div id="page-chat" class="page active">
<h1 class="page-title">Chat</h1>
<p class="page-subtitle">Continuous dialogue</p>
<div class="card">
<textarea class="input" id="chatInput" placeholder="Type your message..." rows="3"></textarea>
<div style="margin-top:16px"><button class="btn" onclick="sendChat()">Send</button></div>
</div>
<div class="card" id="chatResult" style="display:none">
<div class="result-box" id="chatResultContent"></div>
</div>
</div>
<div id="page-judgment" class="page">
<h1 class="page-title">10D Judgment</h1>
<p class="page-subtitle">Cog/Gam/Eco/Dia/Emo/Int/Mor/Soc/Tem/Met</p>
<div class="card">
<textarea class="input" id="judgmentInput" placeholder="Enter question..." rows="3"></textarea>
<div style="margin-top:16px"><button class="btn" onclick="runJudgment()">Analyze</button></div>
</div>
<div class="card" id="judgmentResult" style="display:none">
<div class="result-box" id="judgmentResultContent"></div>
</div>
</div>
<div id="page-action_plan" class="page">
<h1 class="page-title">Action Plan</h1>
<p class="page-subtitle">Eisenhower Matrix</p>
<div class="card">
<textarea class="input" id="actionPlanInput" placeholder="Describe goal..." rows="3"></textarea>
<div style="margin-top:16px"><button class="btn" onclick="generateActionPlan()">Generate</button></div>
</div>
<div class="card" id="actionPlanResult" style="display:none">
<div class="result-box" id="actionPlanResultContent"></div>
</div>
</div>
<div id="page-action_signal" class="page">
<h1 class="page-title">Action Signal</h1>
<p class="page-subtitle">Robot executable signal</p>
<div class="card">
<textarea class="input" id="actionSignalInput" placeholder="Describe task..." rows="3"></textarea>
<div style="margin-top:16px"><button class="btn" onclick="generateActionSignal()">Generate</button></div>
</div>
<div class="card" id="actionSignalResult" style="display:none">
<div class="result-box" id="actionSignalResultContent"></div>
</div>
</div>
<div id="page-goal" class="page">
<h1 class="page-title">Goal System</h1>
<p class="page-subtitle">Onion Time Anchoring</p>
<div class="card"><div class="result-box" id="goalContent">Loading...</div></div>
</div>
<div id="page-causal_memory" class="page">
<h1 class="page-title">Causal Memory</h1>
<p class="page-subtitle">Fast/Slow Dual Flow</p>
<div class="card"><div class="result-box" id="causalMemoryContent">Loading...</div></div>
</div>
<div id="page-curiosity" class="page">
<h1 class="page-title">Curiosity</h1>
<p class="page-subtitle">Dual Random Walk</p>
<div class="card"><div class="result-box" id="curiosityContent">Loading...</div></div>
</div>
<div id="page-openspace" class="page">
<h1 class="page-title">OpenSpace</h1>
<p class="page-subtitle">Version DAG Evolution</p>
<div class="card"><div class="result-box" id="openspaceContent">Loading...</div></div>
</div>
<div id="page-chat_history" class="page">
<h1 class="page-title">History</h1>
<p class="page-subtitle">View past sessions</p>
<div class="card"><div class="result-box" id="chatHistoryContent">Loading...</div></div>
</div>
<div id="page-export" class="page">
<h1 class="page-title">Export</h1>
<p class="page-subtitle">Markdown format</p>
<div class="card">
<select class="input" id="exportLevel" style="max-width:200px;margin-bottom:16px">
<option value="high">High</option>
<option value="medium">Medium</option>
<option value="low">Low</option>
<option value="all">All</option>
</select>
<button class="btn" onclick="exportDialogue()">Export</button>
</div>
</div>
<div id="page-llm_config" class="page">
<h1 class="page-title">LLM Settings</h1>
<p class="page-subtitle">MiniMax/OpenAI/Ollama</p>
<div class="card">
<div style="margin-bottom:16px">
<label style="display:block;margin-bottom:4px">Provider</label>
<select class="input" id="llmProvider" style="max-width:200px">
<option value="minimax">MiniMax</option>
<option value="openai">OpenAI</option>
<option value="ollama">Ollama</option>
</select>
</div>
<div style="margin-bottom:16px">
<label style="display:block;margin-bottom:4px">API Key</label>
<input type="password" class="input" id="llmApiKey" style="max-width:400px">
</div>
<div style="margin-bottom:16px">
<label style="display:block;margin-bottom:4px">API Base URL</label>
<input type="text" class="input" id="llmApiBase" placeholder="https://api.minimax.chat/v1" style="max-width:400px">
</div>
<div style="margin-bottom:16px">
<label style="display:block;margin-bottom:4px">Model</label>
<input type="text" class="input" id="llmModel" placeholder="mini-max-latest" style="max-width:200px">
</div>
<button class="btn" onclick="saveLlmConfig()">Save</button>
</div>
</div>
</main>
</div>
<div class="toast" id="toast"></div>
<script>
function navigateTo(page){
document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
document.getElementById('page-'+page).classList.add('active');
document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
document.querySelector('.nav-item[data-page="'+page+'"]').classList.add('active');
if(page==='goal')loadGoalData();
if(page==='causal_memory')loadCausalMemoryData();
if(page==='curiosity')loadCuriosityData();
if(page==='openspace')loadOpenSpaceData();
if(page==='chat_history')loadChatHistoryData();
}
function showToast(msg){
const t=document.getElementById('toast');
t.textContent=msg;t.classList.add('show');
setTimeout(()=>t.classList.remove('show'),3000);
}
async function sendChat(){
const m=document.getElementById('chatInput').value.trim();
if(!m)return;
const r=document.getElementById('chatResult');
const c=document.getElementById('chatResultContent');
r.style.display='block';c.textContent='Processing...';
try{
const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});
const d=await res.json();
c.innerHTML='<pre>'+(d.content||d.error||'No response')+'</pre>';
}catch(e){c.textContent='Error: '+e.message;}
}
async function runJudgment(){
const m=document.getElementById('judgmentInput').value.trim();
if(!m)return;
const r=document.getElementById('judgmentResult');
const c=document.getElementById('judgmentResultContent');
r.style.display='block';c.textContent='Analyzing...';
try{
const res=await fetch('/api/judgment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});
const d=await res.json();
c.innerHTML='<pre>'+(d.content||d.error||'No response')+'</pre>';
}catch(e){c.textContent='Error: '+e.message;}
}
async function generateActionPlan(){
const m=document.getElementById('actionPlanInput').value.trim();
if(!m)return;
const r=document.getElementById('actionPlanResult');
const c=document.getElementById('actionPlanResultContent');
r.style.display='block';c.textContent='Generating...';
try{
const res=await fetch('/api/action_plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});
const d=await res.json();
c.innerHTML='<pre>'+(d.content||d.error||'No response')+'</pre>';
}catch(e){c.textContent='Error: '+e.message;}
}
async function generateActionSignal(){
const m=document.getElementById('actionSignalInput').value.trim();
if(!m)return;
const r=document.getElementById('actionSignalResult');
const c=document.getElementById('actionSignalResultContent');
r.style.display='block';c.textContent='Generating...';
try{
const res=await fetch('/api/action_signal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});
const d=await res.json();
c.innerHTML='<pre>'+(d.robot_json||d.content||d.error||'No response')+'</pre>';
}catch(e){c.textContent='Error: '+e.message;}
}
async function loadGoalData(){try{const r=await fetch('/api/module/goal');const d=await r.json();document.getElementById('goalContent').innerHTML='<pre>'+(d.content||'No data')+'</pre>';}catch(e){document.getElementById('goalContent').textContent='Load failed';}}
async function loadCausalMemoryData(){try{const r=await fetch('/api/module/causal_memory');const d=await r.json();document.getElementById('causalMemoryContent').innerHTML='<pre>'+(d.content||'No data')+'</pre>';}catch(e){document.getElementById('causalMemoryContent').textContent='Load failed';}}
async function loadCuriosityData(){try{const r=await fetch('/api/module/curiosity');const d=await r.json();document.getElementById('curiosityContent').innerHTML='<pre>'+(d.content||'No data')+'</pre>';}catch(e){document.getElementById('curiosityContent').textContent='Load failed';}}
async function loadOpenSpaceData(){try{const r=await fetch('/api/module/openspace');const d=await r.json();document.getElementById('openspaceContent').innerHTML='<pre>'+(d.content||'No data')+'</pre>';}catch(e){document.getElementById('openspaceContent').textContent='Load failed';}}
async function loadChatHistoryData(){try{const r=await fetch('/api/module/chat_history');const d=await r.json();document.getElementById('chatHistoryContent').innerHTML='<pre>'+(d.content||'No data')+'</pre>';}catch(e){document.getElementById('chatHistoryContent').textContent='Load failed';}}
async function exportDialogue(){const l=document.getElementById('exportLevel').value;try{const r=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:'current',level:l})});const d=await r.json();showToast(d.content||'Exported');}catch(e){showToast('Export failed');}}
async function saveLlmConfig(){const pr=document.getElementById('llmProvider').value;const ak=document.getElementById('llmApiKey').value;const ab=document.getElementById('llmApiBase').value;const m=document.getElementById('llmModel').value;try{const r=await fetch('/api/save_llm_config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:pr,api_key:ak,api_base:ab,model_name:m})});const d=await r.json();showToast(d.content||'Saved');}catch(e){showToast('Save failed');}}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML

class ChatRequest(BaseModel):
    message: str
    profile: str = None

class JudgmentRequest(BaseModel):
    message: str

class ActionPlanRequest(BaseModel):
    message: str

class ActionSignalRequest(BaseModel):
    message: str

class LLMConfigRequest(BaseModel):
    provider: str
    api_key: str = None
    api_base: str = None
    model_name: str = None
    group_id: str = None

class ExportRequest(BaseModel):
    session_id: str
    level: str = "high"

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        from chat_system import load_chat_system
        system = load_chat_system()
        result = system.chat(req.message)
        return {"content": str(result), "success": True}
    except Exception as e:
        return {"content": None, "error": str(e)}

@app.post("/api/judgment")
async def judgment(req: JudgmentRequest):
    try:
        from judgment import check10d, format_report
        result = check10d(req.message)
        report = format_report(result)
        return {"content": report, "success": True}
    except Exception as e:
        return {"content": None, "error": str(e)}

@app.post("/api/action_plan")
async def action_plan(req: ActionPlanRequest):
    try:
        from action_system.action_system import generate_action_plan
        result = generate_action_plan(req.message)
        return {"content": str(result), "success": True}
    except Exception as e:
        return {"content": None, "error": str(e)}

@app.post("/api/action_signal")
async def action_signal(req: ActionSignalRequest):
    try:
        from judgment import check10d, format_report
        from action_signal import format_for_robot
        judgment_result = check10d(req.message)
        action_signals = [{"type": "judgment", "content": format_report(judgment_result)}, {"type": "plan", "content": req.message}]
        robot_json = format_for_robot(action_signals)
        return {"content": str(action_signals), "robot_json": robot_json, "success": True}
    except Exception as e:
        return {"content": None, "robot_json": None, "error": str(e)}

@app.get("/api/module/{module_name}")
async def get_module_data(module_name: str):
    try:
        if module_name == "goal":
            from goal_system.goal_system import get_goal_system, format_hierarchy
            goal_system = get_goal_system()
            hierarchy = format_hierarchy(goal_system)
            return {"content": hierarchy, "success": True}
        elif module_name == "causal_memory":
            from causal_memory.causal_memory import get_statistics, recall_causal_history
            stats = get_statistics()
            recent = recall_causal_history("recent", limit=10)
            content = "Stats: " + str(stats) + "\n\nRecent:\n" + str(recent)
            return {"content": content, "success": True}
        elif module_name == "curiosity":
            from curiosity.curiosity_engine import get_top_open
            top_open = get_top_open(limit=10)
            content = "Interests:\n" + "\n".join(["- " + str(item) for item in top_open]) if top_open else "No data"
            return {"content": content, "success": True}
        elif module_name == "openspace":
            from openspace import get_stats as get_openspace_stats
            stats = get_openspace_stats()
            return {"content": str(stats), "success": True}
        elif module_name == "chat_history":
            from chat_system import list_sessions
            sessions = list_sessions()
            if not sessions:
                return {"content": "No history", "success": True}
            content = "Sessions:\n\n"
            for s in sessions[:10]:
                content += "- " + str(s.get('title', 'No title')) + " (" + str(s.get('date', 'Unknown')) + ")\n"
            return {"content": content, "success": True}
        else:
            return {"content": "Unknown: " + module_name, "success": False}
    except Exception as e:
        return {"content": None, "error": str(e)}

@app.post("/api/export")
async def export(req: ExportRequest):
    try:
        from chat_system import list_sessions, get_current_session
        sessions = list_sessions()
        if not sessions:
            return {"content": "No sessions", "success": False}
        session = get_current_session()
        if not session:
            return {"content": "Cannot get session", "success": False}
        messages = session.get('messages', [])
        if req.level != "all":
            messages = [m for m in messages if m.get('importance', 'medium') in [req.level, 'high']]
        md = "# Export\n\nDate: " + datetime.datetime.now().strftime('%Y-%m-%d %H:%M') + "\n\n"
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            md += "**" + role + "**: " + content + "\n\n"
        export_dir = Path(__file__).parent / "exports"
        export_dir.mkdir(exist_ok=True)
        filename = "dialogue_" + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + ".md"
        (export_dir / filename).write_text(md, encoding='utf-8')
        return {"content": "Exported to exports/" + filename, "success": True}
    except Exception as e:
        return {"content": None, "error": str(e)}

@app.post("/api/save_llm_config")
async def save_llm_config(req: LLMConfigRequest):
    try:
        config = {"provider": req.provider, "api_key": req.api_key or "", "api_base": req.api_base or "", "model_name": req.model_name or "", "group_id": req.group_id or ""}
        config_path = Path(__file__).parent / "config" / "llm_config.json"
        config_path.parent.mkdir(exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return {"content": "Config saved", "success": True}
    except Exception as e:
        return {"content": None, "error": str(e)}

@app.get("/api/status")
async def status():
    return {"status": "running", "version": "2.0"}

if __name__ == "__main__":
    port = 9876
    print("Starting Juhuo Console on http://localhost:" + str(port))
    uvicorn.run(app, host="0.0.0.0", port=port)
