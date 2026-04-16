#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
juhuo.py - 聚活
使用Python内置http.server，无需fastapi/uvicorn/ssl
"""

import sys
import os
import webbrowser
import http.server
import socketserver
import threading
import time

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(__file__))

def main():
    print("=" * 50)
    print("  juhuo - Personal AI Agent")
    print("=" * 50)
    print()
    
    port = 9876
    
    # 生成HTML页面
    html = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>juhuo - 聚活</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        h1 { color: #333; }
        .info { background: #f5f5f5; padding: 20px; border-radius: 8px; }
        .feature { margin: 15px 0; }
        .tag { background: #4CAF50; color: white; padding: 5px 10px; border-radius: 4px; font-size: 14px; }
        code { background: #eee; padding: 2px 6px; border-radius: 3px; }
        .version { color: #888; font-size: 14px; }
    </style>
</head>
<body>
    <h1>juhuo · 聚活</h1>
    <p class="version">v1.3.0 - 最后更新: 2026-04-16</p>
    
    <div class="info">
        <h2>✅ 运行成功！</h2>
        <p>程序正在运行...</p>
        
        <h3>项目核心功能：</h3>
        <div class="feature">
            <span class="tag">判断系统</span> 十维判断分析两难问题
        </div>
        <div class="feature">
            <span class="tag">因果记忆</span> 追踪判断与结果的因果关系
        </div>
        <div class="feature">
            <span class="tag">Fitness反馈</span> 自我进化的评分机制
        </div>
        <div class="feature">
            <span class="tag">安全钩子</span> PreToolUse/PostToolUse危险命令检测
        </div>
        
        <h3>命令行判断：</h3>
        <p><code>python cli.py "我应该接受这个offer吗"</code></p>
        
        <h3>项目地址：</h3>
        <p><a href="https://github.com/taxatombt/guyong-juhuo">https://github.com/taxatombt/guyong-juhuo</a></p>
    </div>
    
    <p style="margin-top:30px; color:#666;">
        铁律：模拟特定具体个体，最终在判断力上超越人类整体。
    </p>
    
    <p style="margin-top:20px; color:#999; font-size:12px;">
        按 Ctrl+C 停止服务器
    </p>
</body>
</html>
'''
    
    # 启动HTTP服务器
    os.chdir(ROOT)
    
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=ROOT, **kwargs)
        
        def do_GET(self):
            if self.path == '/' or self.path == '/index.html':
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
            else:
                super().do_GET()
        
        def log_message(self, format, *args):
            pass  # 静默日志
    
    try:
        with socketserver.TCPServer(("", port), Handler) as httpd:
            print(f"[juhuo] Server running at http://localhost:{port}")
            print()
            
            # 自动打开浏览器
            time.sleep(0.5)
            try:
                webbrowser.open(f"http://localhost:{port}")
            except:
                pass
            
            print("  Press Ctrl+C to stop")
            print("=" * 50)
            print()
            
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[juhuo] Stopped!")
    except Exception as e:
        print(f"[ERROR] {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
