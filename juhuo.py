#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""juhuo.py - 聚活控制台"""
import os, sys, json, datetime
import http.server, socketserver, webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 9876

HTML = open(os.path.join(ROOT, 'web_console.html'), 'r', encoding='utf-8').read()

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode('utf-8'))
        elif self.path == '/api/status':
            self.send_json({'status': 'running', 'version': '1.3.0', 'uptime': datetime.datetime.now().isoformat()})
        elif self.path == '/api/models':
            self.send_json({'models': ['gpt-4', 'gpt-3.5-turbo', 'claude-3', 'local-model']})
        elif self.path == '/api/memory':
            db = os.path.join(ROOT, 'data', 'judgment_data', 'juhuo_judgment.db')
            if os.path.exists(db):
                import sqlite3
                try:
                    conn = sqlite3.connect(db)
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM judgment_records")
                    count = c.fetchone()[0]
                    conn.close()
                    self.send_json({'records': count})
                except: self.send_json({'records': 0})
            else: self.send_json({'records': 0})
        else:
            self.send_error(404)
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        
        if self.path == '/api/chat':
            self.send_json({'content': 'Chat response - Demo mode', 'timestamp': datetime.datetime.now().isoformat()})
        elif self.path == '/api/judgment':
            self.send_json({'question': body, 'dimensions': {'cognitive': 0.75, 'game': 0.60, 'economy': 0.80, 'dialogue': 0.70, 'emotion': 0.65, 'intuition': 0.55, 'moral': 0.70, 'social': 0.60, 'temporal': 0.50, 'meta': 0.45}, 'summary': 'Demo judgment - configure LLM for full analysis'})
        elif self.path == '/api/action_plan':
            self.send_json({'goal': body, 'plan': {'urgent': [], 'important': [], 'delegate': [], 'eliminate': []}})
        elif self.path == '/api/action_signal':
            self.send_json({'signal': body, 'action': 'pending'})
        elif self.path == '/api/llm':
            self.send_json({'status': 'saved', 'message': 'LLM configuration saved'})
        elif self.path == '/api/export':
            self.send_json({'export': 'data'})
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

def main():
    print("=" * 50)
    print("  juhuo - Personal AI Agent")
    print("  ==============================")
    print()
    print(f"  Server: http://localhost:{PORT}")
    print()
    print("  Pages:")
    print("  - Chat")
    print("  - Judgment (10D)")
    print("  - LLM Console")
    print("  - Causal Memory")
    print("  - OpenSpace")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    
    webbrowser.open(f"http://localhost:{PORT}")
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    main()
