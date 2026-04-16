#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
juhuo.py - 聚活完整打包版
PyInstaller --onefile --add-data 打包
双击直接运行，无需安装
"""

import sys
import os
import subprocess
import webbrowser

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(__file__))

def main():
    print("=" * 50)
    print("  juhuo - Personal AI Agent")
    print("=" * 50)
    print()
    
    # 添加项目路径
    sys.path.insert(0, ROOT)
    
    # 检查依赖
    print("[1/3] Checking dependencies...")
    deps = ["fastapi", "uvicorn"]
    for dep in deps:
        try:
            __import__(dep.replace("-", "_"))
        except ImportError:
            print(f"   Installing {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", dep, "-q"])
    
    # 启动
    print("[2/3] Starting web console...")
    web_console = os.path.join(ROOT, "web_console.py")
    
    print("[3/3] Opening browser...")
    print()
    print("  http://localhost:9876")
    print()
    
    try:
        webbrowser.open("http://localhost:9876")
    except:
        pass
    
    # 运行web_console
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    print()
    
    try:
        # 导入并运行web_console
        from web_console import app
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=9876, log_level="warning")
    except KeyboardInterrupt:
        print("\n[juhuo] Stopped!")
    except Exception as e:
        print(f"[ERROR] {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()