# -*- mode: python ; coding: utf-8 -*-
# ============================================================
# PyInstaller spec for guyong-juhuo
# ============================================================

import sys
import os
from pathlib import Path

# 项目根目录 = spec 文件所在目录（通过 argv[0] 推断）
import os
_script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
ROOT = Path(_script_dir)
print(f"[PyInstaller] 项目根目录: {ROOT}")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # judgment/（整个目录及其内容）
        (str(ROOT / "judgment"), "judgment"),
        (str(ROOT / "curiosity"), "curiosity"),
        (str(ROOT / "emotion_system"), "emotion_system"),
        (str(ROOT / "causal_memory"), "causal_memory"),
        (str(ROOT / "action_system"), "action_system"),
        (str(ROOT / "output_system"), "output_system"),
        (str(ROOT / "self_model"), "self_model"),
        (str(ROOT / "goal_system"), "goal_system"),
        (str(ROOT / "perception"), "perception"),
        (str(ROOT / "chat_system"), "chat_system"),
        (str(ROOT / "llm_adapter"), "llm_adapter"),
        (str(ROOT / "feedback_system"), "feedback_system"),
        (str(ROOT / "openspace"), "openspace"),
        (str(ROOT / "evolver"), "evolver"),
        (str(ROOT / "data"), "data"),
        (str(ROOT / "templates"), "templates"),
        (str(ROOT / "web"), "web"),
        (str(ROOT / "gstack_integration"), "gstack_integration"),
        (str(ROOT / "gstack_virtual_team"), "gstack_virtual_team"),
        (str(ROOT / "hermes_integration"), "hermes_integration"),
        (str(ROOT / "hermes_evolution"), "hermes_evolution"),
        (str(ROOT / "_legacy"), "_legacy"),
        (str(ROOT / "test_snapshots"), "test_snapshots"),
        (str(ROOT / "docs"), "docs"),
        # 单文件
        (str(ROOT / "hub.py"), "."),
        (str(ROOT / "web_console.py"), "."),
        (str(ROOT / "tui_console.py"), "."),
        (str(ROOT / "cli.py"), "."),
        (str(ROOT / "judgment_cli.py"), "."),
        (str(ROOT / "judgment_web.py"), "."),
        (str(ROOT / "profile.py"), "."),
        (str(ROOT / "config.py"), "."),
        (str(ROOT / "requirements.txt"), "."),
    ],
    hiddenimports=[
        "hub", "judgment", "judgment.router", "judgment.dimensions",
        "judgment.dynamic_weights", "judgment.priority_output",
        "judgment.self_review", "judgment.error_classifier",
        "judgment.fitness_baseline", "judgment.confidence",
        "judgment.metacognitive", "judgment.insight_tracker",
        "curiosity", "curiosity.curiosity_engine", "curiosity.ralph_loop",
        "emotion_system", "emotion_system.emotion_system",
        "causal_memory", "causal_memory.causal_memory", "causal_memory.causal_chain",
        "action_system", "action_system.action_system", "action_system.security_hook",
        "output_system", "output_system.output_system", "output_system.formatter",
        "self_model", "self_model.self_model",
        "goal_system", "goal_system.goal_system",
        "perception", "perception.attention_filter",
        "chat_system", "chat_system.chat_system",
        "llm_adapter", "llm_adapter.base",
        "feedback_system", "openspace", "evolver",
        "flask", "werkzeug", "jinja2", "markdown",
        "uvicorn", "uvicorn.loops", "uvicorn.loops.auto",
        "uvicorn.protocols", "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto", "uvicorn.logging",
        "uvicorn.config", "fastapi", "pydantic", "jinja2",
        "starlette", "anyio", "httptools", "websockets",
        "python_multipart", "python_dotenv",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "pandas",
        "PIL", "cv2", "torch", "tensorflow",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="guyong-juhuo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
