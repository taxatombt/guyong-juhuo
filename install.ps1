<#
.SYNOPSIS
    聚活 (guyong-juhuo) 一键安装脚本 — Windows 版本
.DESCRIPTION
    自动克隆项目、安装依赖、准备运行环境
#>

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 聚活 (guyong-juhuo) 一键安装" -ForegroundColor Cyan
Write-Host "  打造你自己的个人数字分身" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] 检测到 Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误] 未检测到 Python，请先安装 Python 3.8 或更高版本" -ForegroundColor Red
    Write-Host " 下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# 检查 Git
try {
    $gitVersion = git --version 2>&1
    Write-Host "[OK] 检测到 Git: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误] 未检测到 Git，请先安装 Git" -ForegroundColor Red
    Write-Host " 下载地址: https://git-scm.com/downloads" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[1/4] 克隆项目..." -ForegroundColor Blue

if (Test-Path "guyong-juhuo") {
    Write-Host "[INFO] 项目目录已存在，跳过克隆" -ForegroundColor Yellow
} else {
    git clone https://github.com/taxatombt/guyong-juhuo.git
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 克隆失败，请检查网络" -ForegroundColor Red
        exit 1
    }
}

cd guyong-juhuo

Write-Host ""
Write-Host "[2/4] 升级 pip..." -ForegroundColor Blue
python -m pip install --upgrade pip

Write-Host ""
Write-Host "[3/4] 安装依赖..." -ForegroundColor Blue
pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "[警告] 部分依赖安装失败，请检查网络后重试" -ForegroundColor Yellow
} else {
    Write-Host "[OK] 依赖安装完成" -ForegroundColor Green
}

Write-Host ""
Write-Host "[4/4] 验证安装..." -ForegroundColor Blue
python test_all_imports.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[警告] 部分模块验证失败，但不影响基础使用" -ForegroundColor Yellow
} else {
    Write-Host "[OK] 所有模块验证通过" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " 安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "启动网页控制台:" -ForegroundColor Cyan
Write-Host "  cd guyong-juhuo" -ForegroundColor White
Write-Host "  python web_console.py" -ForegroundColor White
Write-Host ""
Write-Host "然后打开浏览器访问: http://127.0.0.1:9876" -ForegroundColor Cyan
Write-Host ""
Write-Host "祝你使用愉快！🎯 聚活 — 记住你的一切，代替你永远活下去" -ForegroundColor Cyan
