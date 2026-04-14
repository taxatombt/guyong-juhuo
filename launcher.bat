@echo off
chcp 65001 >nul 2>&1
title 聚活 (guyong-juhuo)

; ============================================================
; 聚活 launcher — 双模式入口
; 用法:
;   launcher.bat              启动网页控制台（默认）
;   launcher.bat --init       初始化环境（安装依赖）
;   launcher.bat --console    命令行模式
;   launcher.bat --tui        TUI 终端界面
; ============================================================

setlocal enabledelayedexpansion

set "APP_DIR=%~dp0"
set "PYTHON=python"
set "MODE=console"

; 解析参数
if "%~1"=="--init" set "MODE=init" & goto :do_init
if "%~1"=="--console" set "MODE=console"
if "%~1"=="--tui" set "MODE=tui"
if "%~1"=="--help" goto :show_help

; ── 检查 Python ───────────────────────────────────────────
:check_python
!PYTHON! --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    echo 或运行: installer\setup.exe（重新安装）
    pause
    exit /b 1
)

; 检查 pip
!PYTHON! -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [警告] pip 未安装，正在安装...
    !PYTHON! -m ensurepip --default-pip
)

; ── 模式派发 ──────────────────────────────────────────────
if "%MODE%"=="init" goto :do_init
if "%MODE%"=="tui" goto :do_tui
goto :do_console

:do_init
    echo [聚活] 正在初始化环境...
    echo.
    echo [1/3] 检查 pip...
    !PYTHON! -m pip install --upgrade pip -q

    echo [2/3] 安装依赖...
    if exist "%APP_DIR%requirements.txt" (
        !PYTHON! -m pip install -r "%APP_DIR%requirements.txt" -q
        if errorlevel 1 (
            echo [警告] 部分依赖安装失败，尝试安装核心依赖...
            !PYTHON! -m pip install -r "%APP_DIR%requirements.txt"
        )
    ) else (
        echo [跳过] 未找到 requirements.txt
    )

    echo [3/3] 验证安装...
    !PYTHON! -c "import hub" 2>nul
    if errorlevel 1 (
        echo [错误] hub 模块导入失败，请检查安装
        echo 尝试手动运行: !PYTHON! test_all_imports.py
        pause
        exit /b 1
    )

    echo.
    echo ========================================
    echo  初始化完成！聚活已准备就绪
    echo ========================================
    echo.
    echo 运行方式:
    echo   launcher.bat          启动网页控制台
    echo   launcher.bat --tui    TUI 终端界面
    echo.
    pause
    exit /b 0

:do_tui
    !PYTHON! "%APP_DIR%tui.py"
    exit /b

:do_console
    !PYTHON! "%APP_DIR%web_console.py"
    exit /b

:show_help
    echo 聚活 (guyong-juhuo) — 你的个人数字分身
    echo.
    echo 用法:
    echo   launcher.bat           启动网页控制台
    echo   launcher.bat --init   初始化/重装依赖
    echo   launcher.bat --tui    TUI 终端界面
    echo   launcher.bat --help   显示此帮助
    echo.
    echo 安装程序位置: installer\setup.exe
    exit /b 0
