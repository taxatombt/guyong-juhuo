@echo off
chcp 65001 >nul 2>&1
title juhuo - Personal AI Agent

; ============================================================
; juhuo launcher
; Usage:
;   launcher.bat              Start web console (default)
;   launcher.bat --init       Initialize environment
;   launcher.bat --tui        TUI terminal interface
;   launcher.bat --help       Show help
; ============================================================

setlocal enabledelayedexpansion

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"
set "PYTHON=python"

; Parse arguments
if "%~1"=="--init" goto :do_init
if "%~1"=="--tui" goto :do_tui
if "%~1"=="--console" goto :do_console
if "%~1"=="--help" goto :show_help
if "%~1"=="" goto :do_console
goto :do_console

; ── Check Python ───────────────────────────────────────────
:check_python
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

; ── Init ──────────────────────────────────────────────────
:do_init
    echo [juhuo] Initializing environment...
    echo.
    echo [1/4] Upgrading pip...
    %PYTHON% -m pip install --upgrade pip -q 2>nul

    echo [2/4] Installing dependencies...
    if exist "requirements.txt" (
        %PYTHON% -m pip install -r requirements.txt -q
    )

    echo [3/4] Checking installed packages...
    %PYTHON% -c "import flask; import fastapi; import uvicorn" 2>nul
    if errorlevel 1 (
        echo [INFO] Installing missing packages...
        %PYTHON% -m pip install flask fastapi uvicorn -q
    )

    echo [4/4] Verifying installation...
    %PYTHON% -c "from judgment import JudgmentSystem; print('[OK] juhuo ready')" 2>nul
    if errorlevel 1 (
        echo [WARNING] Some modules may have issues, but core should work.
    )

    echo.
    echo ========================================
    echo  juhuo initialized successfully!
    echo ========================================
    echo.
    echo Usage:
    echo   launcher.bat           Start web console
    echo   launcher.bat --tui    TUI terminal
    echo.
    pause
    exit /b 0

; ── TUI ───────────────────────────────────────────────────
:do_tui
    echo [juhuo] Starting TUI mode...
    %PYTHON% tui_console.py
    exit /b

; ── Console ───────────────────────────────────────────────
:do_console
    echo [juhuo] Starting web console...
    echo.
    echo Opening: http://localhost:9876
    echo Press Ctrl+C to stop
    echo.
    %PYTHON% web_console.py
    exit /b

; ── Help ──────────────────────────────────────────────────
:show_help
    echo juhuo - Personal AI Agent
    echo.
    echo Usage:
    echo   launcher.bat           Start web console (default)
    echo   launcher.bat --init    Initialize environment
    echo   launcher.bat --tui    TUI terminal interface
    echo   launcher.bat --help    Show this help
    echo.
    echo Web Console: http://localhost:9876
    exit /b 0