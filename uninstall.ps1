# uninstall.ps1 - 聚活卸载程序
# 需要管理员权限运行

param(
    [switch]$Force,      # 跳过确认
    [switch]$KeepData    # 保留用户数据
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================"
Write-Host "         聚活 (juhuo) 卸载程序"
Write-Host "========================================"
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[错误] 需要管理员权限" -ForegroundColor Red
    Write-Host "请右键选择'以管理员身份运行'"
    Read-Host "按Enter退出"
    exit 1
}

# 搜索安装目录
$installDirs = @(
    "C:\Program Files\聚活",
    "C:\Program Files (x86)\聚活",
    "E:\juhuo",
    "$PSScriptRoot"
)

$INSTALL_DIR = $null
foreach ($dir in $installDirs) {
    if (Test-Path $dir) {
        $INSTALL_DIR = $dir
        break
    }
}

# 用户数据目录
$USER_DATA_DIR = "$env:USERPROFILE\.juhuo"
if (-not (Test-Path $USER_DATA_DIR)) {
    $USER_DATA_DIR = "$env:APPDATA\juhuo"
}

# 显示找到的内容
Write-Host "找到以下安装内容:" -ForegroundColor Cyan
if ($INSTALL_DIR) {
    Write-Host "  [+] 安装目录: $INSTALL_DIR" -ForegroundColor Green
} else {
    Write-Host "  [-] 安装目录: 未找到" -ForegroundColor Yellow
}
if (Test-Path $USER_DATA_DIR) {
    Write-Host "  [+] 用户数据: $USER_DATA_DIR" -ForegroundColor Green
}
Write-Host ""

# 确认
$confirm = $Force
if (-not $confirm) {
    $response = Read-Host "确定要卸载聚活吗？(y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host "取消卸载" -ForegroundColor Yellow
        exit 0
    }
    $confirm = $true
}

Write-Host "正在卸载..." -ForegroundColor Cyan
Write-Host ""

# 删除安装目录
if ($INSTALL_DIR) {
    Write-Host "[删除] 安装目录: $INSTALL_DIR" -ForegroundColor Yellow
    try {
        Remove-Item -Path $INSTALL_DIR -Recurse -Force -ErrorAction Stop
        Write-Host "      [完成]" -ForegroundColor Green
    } catch {
        Write-Host "      [失败] $_" -ForegroundColor Red
        Write-Host "      请先关闭聚活程序后重试" -ForegroundColor Yellow
    }
}

# 删除桌面快捷方式
$desktopLink = "$env:USERPROFILE\Desktop\聚活.lnk"
if (Test-Path $desktopLink) {
    Write-Host "[删除] 桌面快捷方式" -ForegroundColor Yellow
    Remove-Item -Path $desktopLink -Force -ErrorAction SilentlyContinue
    Write-Host "      [完成]" -ForegroundColor Green
}

# 删除开始菜单
$startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\聚活.lnk"
if (Test-Path $startMenu) {
    Write-Host "[删除] 开始菜单快捷方式" -ForegroundColor Yellow
    Remove-Item -Path $startMenu -Force -ErrorAction SilentlyContinue
    Write-Host "      [完成]" -ForegroundColor Green
}

$startMenuDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\聚活"
if (Test-Path $startMenuDir) {
    Remove-Item -Path $startMenuDir -Recurse -Force -ErrorAction SilentlyContinue
}

# 删除用户数据
if (-not $KeepData -and (Test-Path $USER_DATA_DIR)) {
    Write-Host "[删除] 用户数据: $USER_DATA_DIR" -ForegroundColor Yellow
    Remove-Item -Path $USER_DATA_DIR -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "      [完成]" -ForegroundColor Green
}

# 删除环境变量
$envPath = [Environment]::GetEnvironmentVariable("JUHUO_HOME", "Machine")
if ($envPath) {
    Write-Host "[删除] 环境变量 JUHUO_HOME" -ForegroundColor Yellow
    [Environment]::SetEnvironmentVariable("JUHUO_HOME", $null, "Machine")
    Write-Host "      [完成]" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "         卸载完成" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "如果安装目录仍有残留，请手动删除" -ForegroundColor Yellow
Write-Host "按Enter退出..." -ForegroundColor Gray
Read-Host