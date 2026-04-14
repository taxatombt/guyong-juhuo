#!/usr/bin/env python3
"""
聚活 (guyong-juhuo) 启动器
PyInstaller 打包入口，打包后生成单文件 exe，双击即运行。
"""

import sys
import os
import subprocess
import webbrowser
from pathlib import Path

# PyInstaller bundle 路径：_MEIPASS 是打包后的临时解压目录
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(sys.executable).parent
    # 把打包的 extra/ 模块目录加入 Python 路径
    for subdir in ["judgment", "curiosity", "emotion_system", "causal_memory",
                   "action_system", "output_system", "self_model", "goal_system",
                   "perception", "chat_system", "llm_adapter", "feedback_system",
                   "openspace", "harness", "workspace_modules", "data"]:
        d = BUNDLE_DIR / subdir
        if d.exists() and str(d) not in sys.path:
            sys.path.insert(0, str(d))
else:
    BUNDLE_DIR = Path(__file__).parent.resolve()
    APP_DIR = BUNDLE_DIR


def run_python(*args, capture=False):
    """用系统 Python 执行命令"""
    cmd = [sys.executable, *args]
    if capture:
        result = subprocess.run(cmd, cwd=str(APP_DIR),
                                capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    else:
        return subprocess.run(cmd, cwd=str(APP_DIR)).returncode


def check_python():
    """检查 Python 环境"""
    return sys.version_info >= (3, 8)


def check_pip():
    """检查 pip"""
    try:
        import pip
        return True
    except Exception:
        return False


def do_init():
    """初始化环境"""
    print("=" * 50)
    print("  聚活 — 正在初始化环境...")
    print("=" * 50)

    # 升级 pip
    print("\n[1/4] 升级 pip...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"],
        cwd=str(APP_DIR)
    )

    # 安装依赖
    req = APP_DIR / "requirements.txt"
    if req.exists():
        print("[2/4] 安装依赖（requirements.txt）...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
            cwd=str(APP_DIR), capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[警告] 部分依赖安装失败:\n{result.stderr[-300:]}")
        else:
            print("[OK] 依赖安装完成")
    else:
        print("[跳过] 未找到 requirements.txt")

    # 验证 hub
    print("[3/4] 验证 hub 模块...")
    try:
        import hub
        print("[OK] hub 模块验证通过")
    except Exception as e:
        print(f"[错误] hub 模块导入失败: {e}")

    # 验证 web_console
    print("[4/4] 验证网页控制台...")
    try:
        import web_console
        print("[OK] web_console 验证通过")
    except Exception as e:
        print(f"[警告] web_console 导入失败: {e}")

    print()
    print("=" * 50)
    print("  初始化完成！")
    print("=" * 50)
    print()
    print("下一步：双击 launcher.exe 启动聚活")
    print()
    input("按回车键退出...")


def do_console():
    """启动网页控制台"""
    print("=" * 50)
    print("  聚活 — 启动网页控制台")
    print("=" * 50)
    print()
    print("启动中... 浏览器即将打开")
    print("访问地址: http://127.0.0.1:9876")
    print("(按 Ctrl+C 停止服务)")
    print()
    print("=" * 50)
    print()

    frozen = getattr(sys, 'frozen', False)
    if frozen:
        # exe 打包模式：直接 import web_console 并运行 uvicorn
        import importlib.util
        import threading

        spec = importlib.util.find_spec("web_console")
        if spec is None:
            # 尝试从 BUNDLE_DIR 加载
            wc_path = BUNDLE_DIR / "web_console.py"
            if not wc_path.exists():
                print(f"[错误] 未找到 web_console.py")
                return 1
            spec = importlib.util.spec_from_file_location("web_console", wc_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["web_console"] = mod
            spec.loader.exec_module(mod)
        else:
            mod = importlib.import_module("web_console")

        # 在后台线程运行 uvicorn
        import uvicorn
        import time as time_mod
        def run_server():
            uvicorn.run(mod.app, host="127.0.0.1", port=9876,
                       log_level="warning")
        thread = threading(target=run_server, daemon=True)
        thread.start()
        time_mod.sleep(2)
    else:
        # 开发模式：启动独立进程
        ws_path = APP_DIR / "web_console.py"
        if not ws_path.exists():
            print(f"[错误] 未找到 web_console.py")
            return 1
        proc = subprocess.Popen(
            [sys.executable, str(ws_path)],
            cwd=str(APP_DIR)
        )
        import time
        time.sleep(3)

    # 自动打开浏览器
    webbrowser.open("http://127.0.0.1:9876")

    try:
        while True:
            import time as time_mod
            time_mod.sleep(1)
    except KeyboardInterrupt:
        print("\n停止服务...")

    return 0


def do_tui():
    """启动 TUI 终端界面"""
    tui_path = APP_DIR / "tui_console.py"
    if not tui_path.exists():
        print(f"[错误] 未找到 tui_console.py")
        return 1

    frozen = getattr(sys, 'frozen', False)
    if frozen:
        # exe 打包模式：CREATE_NEW_CONSOLE 打开新窗口运行
        CREATE_NEW_CONSOLE = 0x00000010
        subprocess.Popen(
            [str(sys.executable), str(tui_path)],
            cwd=str(APP_DIR),
            creationflags=CREATE_NEW_CONSOLE
        )
        return 0
    else:
        return subprocess.Popen(
            [sys.executable, str(tui_path)],
            cwd=str(APP_DIR)
        ).wait()


def do_precheck():
    """安装前环境检测"""
    print("=" * 50)
    print("  聚活 — 安装前环境检测")
    print("=" * 50)
    print()

    ok = True

    # Python
    try:
        print(f"[OK] Python: {sys.version.split()[0]}")
    except Exception:
        print("[错误] Python 未安装")
        ok = False

    # pip
    if check_pip():
        print("[OK] pip: 可用")
    else:
        print("[警告] pip 不可用")

    # hub 模块
    try:
        import hub
        print("[OK] hub 模块: 可导入")
    except Exception:
        print("[提示] hub 模块: 需要先运行 --init")

    print()
    if ok:
        print("[结论] 环境就绪，可以安装")
        print("  双击 setup.exe 或运行 install.ps1")
    else:
        print("[结论] 环境异常，请先安装 Python 3.8+")

    print()
    try:
        input("按回车键退出...")
    except (EOFError, OSError):
        pass  # 非交互模式直接退出


def show_help():
    print("聚活 (guyong-juhuo) — 你的个人数字分身")
    print()
    print("用法:")
    print("  launcher.exe              启动网页控制台")
    print("  launcher.exe --init      初始化/重装依赖")
    print("  launcher.exe --tui       TUI 终端界面")
    print("  launcher.exe --check     安装前环境检测")
    print("  launcher.exe --help      显示此帮助")
    print()
    print("快捷方式已创建在桌面和开始菜单")


def main():
    args = sys.argv[1:]

    if not args:
        # 无参数：检查环境
        if check_pip():
            do_console()
        else:
            do_precheck()
        return

    cmd = args[0].lower()

    if cmd in ("--help", "-h", "/?"):
        show_help()
    elif cmd in ("--init", "-i"):
        do_init()
    elif cmd in ("--console", "--web", "-w"):
        do_console()
    elif cmd in ("--tui", "-t"):
        do_tui()
    elif cmd in ("--check", "--precheck"):
        do_precheck()
    else:
        print(f"未知参数: {cmd}")
        show_help()


if __name__ == "__main__":
    main()
