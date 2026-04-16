# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
import sys, os

# 获取项目根目录
ROOT = os.getcwd()

# 收集所有子目录的数据
datas = []
dirs = ['judgment', 'causal_memory', 'curiosity', 'self_model', 
        'emotion_system', 'feedback_system', 'goal_system', 
        'perception', 'output_system', 'action_system', 
        'openspace', 'llm_adapter', 'web', 'docs']

for d in dirs:
    src = os.path.join(ROOT, d)
    if os.path.isdir(src):
        datas.append((src, d))

a = Analysis(
    ['juhuo.py'],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=['fastapi', 'uvicorn', 'pydantic', 'python_multipart'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
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
    name='juhuo',
    console=True,
)