# -*- mode: python ; coding: utf-8 -*-
import sys, os
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.getcwd()

# ── 所有需要打包的目录 ──────────────────────────────
ALL_DIRS = [
    # Shim 层（judgment/ 是从 subsystems/ 重导出的 shim）
    'judgment',
    # 真实代码层
    'subsystems',
    # 各子系统
    'causal_memory',
    'curiosity',
    'self_model',
    'emotion_system',
    'feedback_system',
    'goal_system',
    'perception',
    'output_system',
    'action_system',
    'openspace',
    'llm_adapter',
    'evolver',
    # Web + 配置
    'web',
    'docs',
    'config',
    # 数据目录（运行时生成的内容，只需结构模板）
    'data',
]

datas = []

for d in ALL_DIRS:
    src = os.path.join(ROOT, d)
    if os.path.isdir(src):
        datas.append((src, d))

# HTML 模板
html_file = os.path.join(ROOT, 'web_console.html')
if os.path.exists(html_file):
    datas.append((html_file, '.'))

# CLI 入口文件
cli_file = os.path.join(ROOT, 'cli.py')
if os.path.exists(cli_file):
    datas.append((cli_file, '.'))

# ── 隐藏 import（动态导入的模块）─────────────────────
hiddenimports = [
    # Flask 及相关（web_console.py 用，但环境中可能未安装，按需添加）
    # 'flask', 'werkzeug', 'jinja2', 'markupsafe', 'itsdangerous', 'click',
    # judgment 动态加载的模块（通过 __getattr__）
    'subsystems.judgment',
    'subsystems.judgment.closed_loop',
    'subsystems.judgment.judgment_db',
    'subsystems.judgment.self_evolover',
    'subsystems.judgment.pipeline',
    'subsystems.judgment.benchmark',
    'subsystems.judgment.dimensions',
    'subsystems.judgment.confidence',
    'subsystems.judgment.dynamic_weights',
    'subsystems.judgment.emotion_adapter',
    'subsystems.judgment.context_fence',
    'subsystems.judgment.verifier',
    'subsystems.judgment.insight_tracker',
    'subsystems.judgment.life_cycle_hooks',
    'subsystems.judgment.stop_hook',
    'subsystems.judgment.pre_tool_hook',
    'subsystems.judgment.self_review',
    'subsystems.judgment.matcher',
    'subsystems.judgment.protocol',
    'subsystems.judgment.metacognitive',
    'subsystems.judgment.fitness_evolution',
    # 因果记忆 + 各子系统
    'causal_memory',
    'self_model',
    'curiosity',
    'emotion_system',
    'feedback_system',
    'goal_system',
    'perception',
    'action_system',
    'openspace',
    'llm_adapter',
    'evolver',
    'output_system',
    # 通用
    'sqlite3', 'threading', 'pathlib', 'datetime', 'json', 're',
    'urllib', 'http.client', 'ssl',
    # CLI 直接 import
    'judgment.pipeline',
    'judgment.self_model',
    'judgment.verdict_collector',
    'judgment.benchmark',
    'judgment.logging_config',
    'judgment.self_evolover',
    'config.env_loader',
    # CLI
    'cli',
]

# DLL 收集（conda Library/bin 目录）
DLL_DIR = r'E:\qwenpaw\Library\bin'
binaries = []
if os.path.exists(DLL_DIR):
    import glob
    for dll in glob.glob(os.path.join(DLL_DIR, '*.dll')):
        binaries.append((dll, '.'))

a = Analysis(
    ['__main__.py'],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    console=True,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='guyong-juhuo',
    console=True,
)
