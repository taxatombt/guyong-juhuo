# Windows 安装程序构建指南

## 快速构建（3步）

### 1. 下载 Inno Setup
下载地址：https://jrsoftware.org/isinfo.php

安装后确保 `iscc.exe` 在 PATH 中（通常在 `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`）

### 2. 安装 Python（如果系统没有）
Windows 10/11 用户可以直接运行（需要管理员权限）：
```powershell
winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements
```

或者手动下载：https://www.python.org/downloads/

### 3. 编译安装程序
```powershell
cd installer
iscc setup.iss
```

输出：`..\dist\guyong-juhuo-1.0.0-setup.exe`

---

## 双模式使用说明

### 普通用户：下载 exe → 双击 → 下一步 → 完成
- 有精美安装向导
- 自动创建桌面快捷方式
- 自动初始化环境

### 高级用户：静默自动安装
```powershell
# 静默模式（无界面，后台自动完成）
.\dist\guyong-juhuo-1.0.0-setup.exe /SILENT /NORESTART

# 超静默（无界面无弹窗）
.\dist\guyong-juhuo-1.0.0-setup.exe /VERYSILENT /NORESTART
```

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `setup.iss` | Inno Setup 打包脚本 |
| `launcher.bat` | 安装后的启动器入口 |
| `precheck.bat` | 安装前环境检测 |
| `README.md` | 本文件 |

---

## 安装程序功能清单

- [x] 自动创建开始菜单
- [x] 创建桌面快捷方式
- [x] 可选开机自启
- [x] 卸载程序（控制面板可见）
- [x] /SILENT 静默安装模式
- [x] /VERYSILENT 超静默模式
- [x] 安装前环境预检
- [x] 安装后自动初始化

---

## 手动构建替代方案（不需要 Inno Setup）

如果没有 Inno Setup，可以直接用 PyInstaller 打包：

```powershell
# 安装 PyInstaller
pip install pyinstaller

# 打包 launcher 为 exe
pyinstaller --onefile --name "guyong-juhuo" --add-data "..;." launcher.bat

# 或者直接分发 launcher.bat + requirements.txt
```

---

## 常见问题

**Q: 安装后双击没反应？**
A: 右键 launcher.bat → 以管理员身份运行，或先运行 `--init` 初始化

**Q: 提示"未检测到 Python"？**
A: 重新运行 setup.exe，选择"修复/重新安装"

**Q: winget 找不到？**
A: Windows 10 1809+ 自带 winget，否则手动下载 Python：https://python.org/downloads/

**Q: 卸载后想干净重装？**
A: 运行 `control appwiz.cpl` 找到"聚活"卸载
