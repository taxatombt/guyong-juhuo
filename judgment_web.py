# -*- coding: utf-8 -*-
"""
judgment_web.py ?Web 实时流可视化

Usage:
    python judgment_web.py
    访问 http://localhost:18765
"""
import sys, os, asyncio, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from pipeline import check10d_full, PipelineConfig

app = FastAPI(title="guyong-Judgment v2", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

HTML_UI = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>guyong-Judgment v2</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}
.container{max-width:900px;margin:0 auto;padding:2rem}
h1{color:#58a6ff;margin-bottom:0.5rem}
.subtitle{color:#8b949e;margin-bottom:2rem}
.input-row{display:flex;gap:0.5rem;margin-bottom:2rem}
input{flex:1;padding:0.75rem 1rem;border:1px solid #30363d;border-radius:6px;background:#161b22;color:#e6edf3;font-size:1rem}
button{padding:0.75rem 1.5rem;background:#238636;border:none;border-radius:6px;color:white;cursor:pointer;font-size:1rem}
button:hover{background:#2ea043}
.stream-box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1.5rem;min-height:400px;white-space:pre-wrap;font-family:'Cascadia Code',monospace;font-size:0.9rem;line-height:1.6}
.verdict-PASS{background:#238636;color:white;padding:0.2rem 0.6rem;border-radius:4px}
.verdict-MODIFY{background:#d29922;color:black;padding:0.2rem 0.6rem;border-radius:4px}
.verdict-REJECT{background:#da3633;color:white;padding:0.2rem 0.6rem;border-radius:4px}
.warning{color:#d29922}
.ok{color:#3fb950}
.footer{margin-top:2rem;color:#484f58;font-size:0.8rem;text-align:center}
</style></head>
<body><div class="container">
<h1>guyong-Judgment v2</h1>
<p class="subtitle">十维判断框架 ?Streaming 可视?/p>
<div class="input-row">
<input id="taskInput" placeholder="输入你的判断问题，如：要不要辞职创业" value="要不要辞职创?>
<button onclick="doStream()">判断</button>
</div>
<div class="stream-box" id="output">等待输入...</div>
<div class="footer">Pipeline v2 | 置信?+ 对抗?+ 求是与动态权?/div>
</div>
<script>
let es;
function doStream(){
  const task=document.getElementById('taskInput').value;
  const out=document.getElementById('output');
  if(es)es.close();
  out.textContent='';
  es=new EventSource('/stream?task='+encodeURIComponent(task));
  es.onmessage=function(e){
    const d=JSON.parse(e.data);
    if(d.type==='chunk')out.textContent+=d.text;
    else if(d.type==='done'){out.textContent+='\\n\\n[完成]';es.close();}
    else if(d.type==='error'){out.textContent+='\\n[错误]'+d.message;es.close();}
  };
  es.onerror=function(){es.close();};
}
document.getElementById('taskInput').addEventListener('keydown',function(e){if(e.key==='Enter')doStream();});
</script></body></html>"""

@app.get("/")
async def index():
    return HTMLResponse(HTML_UI)

@app.get("/stream")
async def stream(task: str = Query(...)):
    async def generate():
        cfg = PipelineConfig(enable_adversarial=True, enable_qiushi=True,
                            enable_embedding=True, enable_lessons=True)
        result = check10d_full(task, config=cfg)
        r = result

        def sse(text):
            return json.dumps({"type":"chunk","text":text}, ensure_ascii=False)

        yield "event:message\ndata:"+sse(f"\n{'='*50}\n  {r['task']}\n  复杂? {r['complexity']}  |  类型: {', '.join(r['task_types'])}\n{'='*50}\n\n")+"\n\n"
        await asyncio.sleep(0.05)

        yield "event:message\ndata:"+sse("\n[动态权重]\n")+"\n\n"
        for k,v in sorted(r['weights'].items(),key=lambda x:-x[1]):
            bar="="*int(v*30)
            yield "event:message\ndata:"+sse(f"  {k:12s} {bar:20s} {str(round(v*100)):3s}%\n")+"\n\n"
            await asyncio.sleep(0.02)

        adv = r.get("adversarial")
        if adv:
            yield "event:message\ndata:"+sse(f"\n[对抗性验证] 稳健? {adv['robustness']}%  |  判定: {adv['verdict']}\n")+"\n\n"
            for obj in adv.get("strong_objections",[]):
                yield "event:message\ndata:"+sse(f"  x [{obj['dimension']}] {obj['text']}\n")+"\n\n"
                await asyncio.sleep(0.02)

        qiushi = r.get("qiushi")
        if qiushi and not qiushi.get("is_qiushi", True):
            yield "event:message\ndata:"+sse(f"\n[求是警告] {qiushi.get('verdict','')}\n")+"\n\n"

        low_conf = r.get("low_confidence_dims",[])
        if low_conf:
            yield "event:message\ndata:"+sse(f"\n[低置信度] {', '.join(low_conf)}\n")+"\n\n"

        meta = r.get("meta",{})
        yield "event:message\ndata:"+sse(f"\n{'='*50}\n耗时: {meta.get('elapsed_ms','?')}ms\n")+"\n\n"
        yield "event:message\ndata:"+json.dumps({"type":"done"})+"\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

def main():
    print("聚活 · 认知观测台 启动")
    print("访问: http://localhost:18765")
    uvicorn.run(app, host="0.0.0.0", port=18765, log_level="warning")

if __name__ == "__main__":
    main()
