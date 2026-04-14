<#
.SYNOPSIS
    聚活 (guyong-juhuo) 一键安装脚本 — Windows 版本
.DESCRIPTION
    自动克隆项目、安装依赖、创建快捷方式、初始化运行环境
#>

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  聚活 (guyong-juhuo) 一键安装" -ForegroundColor Cyan
Write-Host "  打造你自己的个人数字分身" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 环境检测 ──────────────────────────────────────────────
Write-Host "[检查] 正在检测环境..." -ForegroundColor Blue

$pythonOk = $false
$gitOk = $false

# Python
try {
    $pyVer = python --version 2>&1
    Write-Host "  [OK] Python: $pyVer" -ForegroundColor Green
    $pythonOk = $true
} catch {
    Write-Host "  [错误] 未检测到 Python" -ForegroundColor Red
    Write-Host "         下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
}

# pip
try {
    $pipVer = pip --version 2>&1 | Out-String
    if ($pipVer -match "pip") {
        Write-Host "  [OK] pip: 已安装" -ForegroundColor Green
    }
} catch {
    Write-Host "  [警告] pip 未正常工作" -ForegroundColor Yellow
}

# Git
try {
    $gitVer = git --version 2>&1
    Write-Host "  [OK] Git: $gitVer" -ForegroundColor Green
    $gitOk = $true
} catch {
    Write-Host "  [警告] Git 未安装" -ForegroundColor Yellow
}

if (-not $pythonOk) {
    Write-Host ""
    Write-Host "请先安装 Python 后重新运行本脚本" -ForegroundColor Red
    Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# ── 克隆或更新项目 ─────────────────────────────────────────
Write-Host ""
Write-Host "[安装] 正在准备项目..." -ForegroundColor Blue

$PROJECT_DIR = $PSScriptRoot

if (-not (Test-Path "$PROJECT_DIR\hub.py")) {
    Write-Host "  [提示] 请将本脚本放在项目根目录运行" -ForegroundColor Yellow
    Write-Host "         或者手动指定项目路径" -ForegroundColor Yellow
    exit 1
}

Write-Host "  [OK] 项目目录: $PROJECT_DIR" -ForegroundColor Green

# ── 安装依赖 ──────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] 安装依赖..." -ForegroundColor Blue

python -m pip install --upgrade pip -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [警告] pip 升级失败，继续尝试..." -ForegroundColor Yellow
}

if (Test-Path "$PROJECT_DIR\requirements.txt") {
    pip install -r "$PROJECT_DIR\requirements.txt" -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [警告] 部分依赖安装失败" -ForegroundColor Yellow
    } else {
        Write-Host "  [OK] 依赖安装完成" -ForegroundColor Green
    }
} else {
    Write-Host "  [跳过] 未找到 requirements.txt" -ForegroundColor Yellow
}

# ── 初始化 ──────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] 初始化环境..." -ForegroundColor Blue

# 用 launcher.bat 初始化
if (Test-Path "$PROJECT_DIR\launcher.bat") {
    & "$PROJECT_DIR\launcher.bat" --init
} else {
    # 降级：直接 pip install
    python -m pip install -r "$PROJECT_DIR\requirements.txt" -q
}

# ── 验证 ──────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] 验证安装..." -ForegroundColor Blue

$importOk = $true
try {
    python -c "import hub" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] hub 模块验证通过" -ForegroundColor Green
    } else {
        $importOk = $false
    }
} catch {
    $importOk = $false
}

if (-not $importOk) {
    Write-Host "  [警告] hub 模块导入失败，尝试运行 pip install -r requirements.txt" -ForegroundColor Yellow
}

# ── 创建快捷方式 ──────────────────────────────────────────
Write-Host ""
Write-Host "[完成] 创建快捷方式..." -ForegroundColor Blue

$Desktop = [Environment]::GetFolderPath("Desktop")
$WshShell = New-Object -ComObject WScript.Shell

# 桌面快捷方式
$Shortcut = $WshShell.CreateShortcut("$Desktop\聚活.lnk")
$Shortcut.TargetPath = "$PROJECT_DIR\launcher.bat"
$Shortcut.WorkingDirectory = $PROJECT_DIR
$Shortcut.Description = "聚活 - 个人数字分身"
$Shortcut.Save()

Write-Host "  [OK] 桌面快捷方式: $Desktop\聚活.lnk" -ForegroundColor Green

# 开始菜单
$StartMenu = [Environment]::GetFolderPath("StartMenu")
$Programs = "$StartMenu\Programs"
if (-not (Test-Path $Programs)) {
    New-Item -ItemType Directory -Path $Programs -Force | Out-Null
}
$Shortcut2 = $WshShell.CreateShortcut("$Programs\聚活.lnk")
$Shortcut2.TargetPath = "$PROJECT_DIR\launcher.bat"
$Shortcut2.WorkingDirectory = $PROJECT_DIR
$Shortcut2.Description = "聚活 - 个人数字分身"
$Shortcut2.Save()
Write-Host "  [OK] 开始菜单: $Programs\聚活.lnk" -ForegroundColor Green

# ── 完成 ──────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "启动方式 1（快捷方式，已创建）:" -ForegroundColor Cyan
Write-Host "  双击桌面【聚活】图标" -ForegroundColor White
Write-Host ""
Write-Host "启动方式 2（命令行）:" -ForegroundColor Cyan
Write-Host "  cd $PROJECT_DIR" -ForegroundColor White
Write-Host "  launcher.bat" -ForegroundColor White
Write-Host ""
Write-Host "启动方式 3（静默/自动化安装用户）:" -ForegroundColor Cyan
Write-Host "  双击 dist\guyong-juhuo-1.0.0-setup.exe" -ForegroundColor White
Write-Host ""
Write-Host "祝你使用愉快！" -ForegroundColor Cyan
Write-Host "聚活 — 记住你的一切，代替你永远活下去" -ForegroundColor Cyan
