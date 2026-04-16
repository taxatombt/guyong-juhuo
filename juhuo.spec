# -*- mode: python ; coding: utf-8 -*-
import sys, os

ROOT = os.getcwd()
SSL_DLL = r'E:\qwenpaw\Library\bin\libssl-3-x64.dll'

# 收集子目录数据
datas = []
dirs = ['judgment', 'causal_memory', 'curiosity', 'self_model', 
        'emotion_system', 'feedback_system', 'goal_system', 
        'perception', 'output_system', 'action_system', 
        'openspace', 'llm_adapter', 'web', 'docs']

for d in dirs:
    src = os.path.join(ROOT, d)
    if os.path.isdir(src):
        datas.append((src, d))

# 添加SSL DLL到binaries
binaries = []
if os.path.exists(SSL_DLL):
    binaries.append((SSL_DLL, '.'))

a = Analysis(
    ['juhuo.py'],
    pathex=[ROOT],
    binaries=binaries,
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