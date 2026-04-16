@echo off
chcp 65001 >nul
echo.
echo ========================================
echo          聚活 (juhuo) 卸载程序
echo ========================================
echo.

:: 检查权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [警告] 需要管理员权限，请右键选择"以管理员身份运行"
    pause
    exit /b 1
)

:: 搜索安装目录
set "INSTALL_DIR="
set "USER_DATA_DIR="

:: 检查默认安装位置
if exist "C:\Program Files\聚活" (
    set "INSTALL_DIR=C:\Program Files\聚活"
) else if exist "E:\juhuo" (
    set "INSTALL_DIR=E:\juhuo"
)

:: 检查用户数据目录
if exist "%USERPROFILE%\.juhuo" (
    set "USER_DATA_DIR=%USERPROFILE%\.juhuo"
)

:: 显示找到的目录
echo 已找到以下安装：
if defined INSTALL_DIR (
    echo   - 安装目录: %INSTALL_DIR%
) else (
    echo   - 安装目录: 未找到
)
if defined USER_DATA_DIR (
    echo   - 用户数据: %USER_DATA_DIR%
)
echo.

:: 确认卸载
set /p confirm="确定要卸载聚活吗？(y/N): "
if /i not "%confirm%"=="y" (
    echo 取消卸载
    exit /b 0
)

echo.
echo 正在卸载...
echo.

:: 删除安装目录
if defined INSTALL_DIR (
    echo [删除] %INSTALL_DIR%
    rmdir /s /q "%INSTALL_DIR%" 2>nul
    if exist "%INSTALLALL_DIR%" (
        echo   [失败] 请手动关闭程序后重试
    ) else (
        echo   [完成]
    )
)

:: 删除桌面快捷方式
if exist "%USERPROFILE%\Desktop\聚活.lnk" (
    echo [删除] 桌面快捷方式
    del /f /q "%USERPROFILE%\Desktop\聚活.lnk" 2>nul
    echo   [完成]
)

:: 删除开始菜单
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\聚活.lnk" (
    echo [删除] 开始菜单
    del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\聚活.lnk" 2>nul
    echo   [完成]
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\聚活" (
    rmdir /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\聚活" 2>nul
)

:: 删除用户数据（可选）
set /p clean_data="是否删除用户数据？(y/N): "
if /i "%clean_data%"=="y" (
    if defined USER_DATA_DIR (
        echo [删除] %USER_DATA_DIR%
        rmdir /s /q "%USER_DATA_DIR%" 2>nul
        echo   [完成]
    )
)

:: 删除环境变量（如果有）
reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v JUHUO_HOME >nul 2>&1
if %errorLevel% equ 0 (
    echo [删除] 环境变量 JUHUO_HOME
    reg delete "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v JUHUO_HOME /f >nul 2>&1
    echo   [完成]
)

echo.
echo ========================================
echo          卸载完成
echo ========================================
echo.
echo 按任意键退出...
pause >nul