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
            self.send_json({'status': 'running', 'version': '1.3.0'})
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
            else:
                self.send_json({'records': 0})
        elif self.path.startswith('/api/module/'):
            module = self.path.replace('/api/module/', '')
            self.send_json({'content': f'{module} data - Demo mode'})
        else:
            self.send_error(404)
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        
        if self.path == '/api/chat':
            self.send_json({'content': 'Chat response - Demo mode. Configure LLM in Settings.'})
        elif self.path == '/api/judgment':
            self.send_json({'content': 'Judgment analysis - Demo mode. Configure LLM in Settings.'})
        elif self.path == '/api/action_plan':
            self.send_json({'content': 'Action Plan - Demo mode'})
        elif self.path == '/api/action_signal':
            self.send_json({'content': 'Action Signal - Demo mode'})
        elif self.path == '/api/export':
            self.send_json({'content': 'Export - Demo mode'})
        elif self.path == '/api/save_llm_config':
            self.send_json({'content': 'LLM config saved'})
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
    print("=" * 50)
    print(f"\n  Server: http://localhost:{PORT}")
    print("\n  Press Ctrl+C to stop")
    print("=" * 50)
    
    webbrowser.open(f"http://localhost:{PORT}")
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    main()