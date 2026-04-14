"""app.py - guyong-juhuo Web UI + SSE Streaming v3"""
import os, sys, json, time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

pkg_dir = os.path.dirname(os.path.abspath(__file__))
parent = os.path.dirname(pkg_dir)
copaw = r"C:\Users\yiseg\.copaw\workspaces\default"
for p in [parent, copaw]:
    if p not in sys.path:
        sys.path.insert(0, p)

from judgment import check10d
from judgment.pipeline import check10d_full, PipelineConfig
from judgment.profile import list_profiles, load as load_profile
from judgment.memory import log_decision as _log_decision, get_recent_decisions, init as _init_mem
from config_manager import load_user_config, save_user_config, is_configured, get_api_key, write_api_key, JUHuo_USER_ENV

def log_decision(task, result_data, decision, feedback):
    checked = (result_data or {}).get("important", [])
    skipped = (result_data or {}).get("skipped", [])
    rating = 1 if feedback == "hello" else (-1 if feedback == "hai" else 0)
    return _log_decision(task=task, complexity=(result_data or {}).get("complexity", "auto"),
        checked=checked, skipped=skipped, profile=(result_data or {}).get("profile"),
        user_decision=decision, feedback=feedback, rating=rating)

def memory_summary():
    try:
        _init_mem()
        from judgment.memory import MEMORY_DIR
        import sqlite3
        db_path = MEMORY_DIR / "decisions.db"
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(CASE WHEN rating>0 THEN 1 ELSE 0 END), SUM(CASE WHEN rating<0 THEN 1 ELSE 0 END) FROM decisions")
        row = c.fetchone()
        conn.close()
        total = row[0] or 0
        good = row[1] or 0
        bad = row[2] or 0
        acc = round(good / total * 100, 1) if total > 0 else 0
        return {"total_decisions": total, "stats": {"good": good, "bad": bad, "accuracy": acc}}
    except Exception:
        return {"total_decisions": 0, "stats": {"good": 0, "bad": 0, "accuracy": 0}}

def get_lessons():
    try:
        _init_mem()
        from judgment.memory import MEMORY_DIR
        import sqlite3
        db_path = MEMORY_DIR / "decisions.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT DISTINCT checked_dims FROM decisions WHERE lesson IS NOT NULL AND lesson != '' ORDER BY id DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        lessons = []
        for r in rows:
            dims = json.loads(r[0])
            for d in dims:
                lessons.append({"dimension": d, "pattern": "from_history", "count": 1})
        return lessons
    except Exception:
        return []

ui_path = os.path.join(pkg_dir, "ui.html")
HTML = open(ui_path, encoding="utf-8").read()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def send_sse(self, event, data):
        self.wfile.write(("event: %s\n" % event).encode("utf-8"))
        self.wfile.write(("data: %s\n\n" % json.dumps(data, ensure_ascii=False)).encode("utf-8"))

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
        elif self.path == "/history":
            self.send_json(get_recent_decisions(limit=20))
        elif self.path == "/stats":
            self.send_json(memory_summary())
        elif self.path == "/lessons":
            self.send_json(get_lessons())
        elif self.path == "/profiles":
            self.send_json(list_profiles())
        elif self.path.startswith("/api/analyze"):
            # SSE streaming endpoint (GET with query params)
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            task = (params.get("task", [""])[0]).strip()
            profile_name = (params.get("profile", [""])[0]).strip() or None
            if not task:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "task empty"}')
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                self._stream_analysis(task, profile_name)
            except Exception as e:
                self.send_sse("error", {"message": str(e)})
            return
        elif self.path == "/api/config":
            cfg = load_user_config()
            self.send_json({
                "configured": is_configured(),
                "api_key_set": bool(get_api_key()),
                "llm_model": cfg.get("llm_model", "MiniMax-M2.7"),
                "temperature": cfg.get("temperature", 0.7),
                "max_token": cfg.get("max_token", 4096),
                "confidence_threshold": cfg.get("confidence_threshold", 0.5),
            })
        else:
            self.send_response(404)

    def do_POST(self):
        if self.path == "/analyze":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            task = data.get("task", "").strip()
            profile_name = data.get("profile", "").strip() or None
            if not task:
                self.send_json({"error": "task empty"}, 400)
                return
            profile = load_profile(profile_name) if profile_name else None
            try:
                result = check10d(task, agent_profile=profile, complexity="auto")
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
                return
            self.send_json(result)
        elif self.path == "/log":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            log_decision(data.get("task", ""), data.get("result", {}), data.get("decision", ""), data.get("feedback", ""))
            self.send_json({"ok": True})
        elif self.path.startswith("/analyze/stream"):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            task = (params.get("task", [""])[0]).strip()
            profile_name = (params.get("profile", [""])[0]).strip() or None
            if not task:
                self.send_json({"error": "task empty"}, 400)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                self._stream_analysis(task, profile_name)
            except Exception as e:
                self.send_sse("error", {"message": str(e)})
            return
        elif self.path == "/api/config":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            cfg = load_user_config()
            # API key（单独处理，写入 ~/.juhuo/.env）
            if "api_key" in data:
                api_key = data["api_key"].strip()
                if api_key:
                    write_api_key(api_key)
                elif "api_key" in cfg:
                    del cfg["api_key"]
            # 其他配置项
            for key in ("llm_model", "temperature", "max_token", "confidence_threshold"):
                if key in data:
                    val = data[key]
                    if key == "temperature":
                        val = float(val)
                    elif key in ("max_token", "confidence_threshold"):
                        val = int(val)
                    cfg[key] = val
            save_user_config(cfg)
            self.send_json({"ok": True})
        else:
            self.send_response(404)

    def _stream_analysis(self, task, profile_name):
        """Stream progressive analysis via SSE events"""
        profile = load_profile(profile_name) if profile_name else None
        cfg = PipelineConfig(agent_profile=profile, enable_adversarial=True, enable_qiushi=True,
                             enable_embedding=True, enable_lessons=True)
        result = check10d_full(task, cfg)
        dims = result.get("check_result", {}).get("dimensions", [])
        weights = result.get("weights", {})
        confidences = result.get("confidences", {})
        must_check = result.get("check_result", {}).get("must_check", [])
        important = result.get("check_result", {}).get("important", [])
        skipped_dims = result.get("check_check", {}).get("skipped", [])
        # Send init
        self.send_sse("init", {"task": task, "weights": weights, "profile": profile_name})
        time.sleep(0.05)
        # Send dimensions progressively
        for dim in dims:
            dim_id = dim.get("id", "")
            dim_name = dim.get("name", dim_id)
            raw_score = confidences.get(dim_id, 0.5)
            score = float(raw_score.score if hasattr(raw_score, "score") else raw_score) if raw_score else 0.5
            raw_weight = weights.get(dim_id, 0.5)
            weight = float(raw_weight.score if hasattr(raw_weight, "score") else raw_weight) if raw_weight else 0.0
            priority = "must" if dim_id in must_check else ("important" if dim_id in important else "skipped")
            self.send_sse("dimension", {
                "dimension_id": dim_id,
                "dimension_name": dim_name,
                "score": score,
                "weight": weight,
                "priority": priority,
                "questions": dim.get("questions", []),
                "reasoning": dim.get("reasoning", ""),
            })
            time.sleep(0.08)
        # Send confidence
        confid = result.get("confidence", {})
        self.send_sse("confidence", {
            "layered_verdict": confid.get("layered_verdict", "N/A"),
            "core_judgments": confid.get("core_judgments", []),
            "conditional": confid.get("conditional", []),
            "blind_spots": confid.get("blind_spots", []),
            "hindsight": confid.get("hindsight", {}),
        })
        time.sleep(0.05)
        # Send causal chain
        causal = result.get("causal_chain", {})
        self.send_sse("causal", causal)
        time.sleep(0.05)
        # Send recursive probes
        recursive = result.get("recursive_probes", {})
        self.send_sse("recursive", recursive)
        time.sleep(0.05)
        # Send meta verdict
        meta = result.get("meta_verdict", {})
        self.send_sse("meta", meta)
        time.sleep(0.05)
        # Send debate result
        debate = result.get("debate_result", {})
        self.send_sse("debate", debate)
        time.sleep(0.05)
        # Send final
        final_scores = {}
        for k, v in confidences.items():
            final_scores[k] = float(v.score if hasattr(v, "score") else v) if v else 0.5
        self.send_sse("final", {
            "scores": final_scores,
            "weights": {k: float(v.score if hasattr(v, "score") else v) if v else 0.0 for k, v in weights.items()},
            "causal_chain": causal,
            "confidence": confid,
            "meta_verdict": meta,
            "debate_result": debate,
            "outcome_tracking": result.get("outcome_tracking", {}),
        })


if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 18768))
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print("guyong-juhuo web UI: http://localhost:%d" % PORT)
    print("SSE endpoint: POST /analyze/stream?task=...&profile=...")
    server.serve_forever()
