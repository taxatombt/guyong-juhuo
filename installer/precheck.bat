@echo off
chcp 65001 >nul 2>&1
title 聚活 - 安装前检测

echo ========================================
echo   聚活 - 安装前环境检测
echo ========================================
echo.

set "PASS=0"
set "FAIL=0"

; ── 检测 Python ──────────────────────────────────────────
call :check "Python" python --version
if !PASS! == 1 (
    echo    发现: !RESULT!
) else (
    echo    未安装，请先安装 Python 3.8+
    echo    下载: https://python.org/downloads/
)

; ── 检测 pip ─────────────────────────────────────────────
call :check "pip" pip --version
if !PASS! == 1 (
    echo    发现: !RESULT!
) else (
    echo    pip 未正常工作，可能需要重新安装 Python
)

; ── 检测 Git ─────────────────────────────────────────────
call :check "Git" git --version
if !PASS! == 1 (
    echo    发现: !RESULT!
) else (
    echo    [警告] Git 未安装（可选，但推荐安装）
)

; ── 检测网络 ──────────────────────────────────────────────
echo.
echo [网络检测] 正在测试 GitHub 连接...
curl -s --connect-timeout 5 https://github.com >nul 2>&1
if errorlevel 1 (
    echo    [警告] 无法连接 GitHub，依赖安装可能失败
) else (
    echo    [OK] GitHub 连接正常
)

; ── 总结 ──────────────────────────────────────────────────
echo.
echo ========================================
if !FAIL! == 0 (
    echo   检测结果：全部通过，可以安装
    echo ========================================
    echo.
    echo 下一步：双击运行 installer\setup.exe
    echo.
) else (
    echo   检测结果：有 !FAIL! 项未通过
    echo ========================================
    echo.
    echo 请先解决上述问题后再运行安装程序
    echo.
)
pause
exit /b

; ── 检测子函数 ────────────────────────────────────────────
:check
set "TOOL=%~1"
set "CMD=%~2"
!CMD! >tmp_check.txt 2>&1
if errorlevel 1 (
    echo [FAIL] !TOOL!
    set /a FAIL+=1
    set "PASS=0"
    set "RESULT="
    exit /b
)
set /a PASS=1
set /p RESULT=    版本: <tmp_check.txt
del tmp_check.txt 2>nul
exit /b
