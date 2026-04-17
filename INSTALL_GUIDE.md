# juhuo 使用指南

> 模拟特定个体的思维方式，在判断力上超越人类整体。

---

## 目录

1. [下载与安装](#1-下载与安装)
2. [首次使用](#2-首次使用)
3. [功能介绍](#3-功能介绍)
4. [命令行使用](#4-命令行使用)
5. [常见问题](#5-常见问题)
6. [卸载](#6-卸载)

---

## 1. 下载与安装

### 1.1 下载安装包

访问 GitHub 下载页面：
```
https://github.com/taxatombt/guyong-juhuo/releases
```

下载 `guyong-juhuo-1.0.0-setup.exe` 或最新版本

### 1.2 安装

1. 双击 `juhuo-1.3.0-setup.exe`
2. 如果弹出安全提示，点击"允许"
3. 选择安装位置（默认 `C:\Program Files\juhuo`）
4. 勾选"Create Desktop Shortcut"（创建桌面快捷方式）
5. 点击"Install"
6. 等待安装完成，点击"Finish"

### 1.3 安装后检查

安装完成后检查：
- 桌面是否有 `juhuo` 图标
- 开始菜单是否有 `juhuo` 程序组
- 安装目录 `C:\Program Files\juhuo` 是否有以下文件：
  - `launcher.bat`（启动程序）
  - `cli.py`（命令行工具）
  - `web_console.py`（网页控制台）
  - `uninstall_juhuo.exe`（卸载程序）

---

## 2. 首次使用

### 2.1 初始化（重要！）

首次运行前需要初始化依赖：

**方法1：从开始菜单**
1. 开始 → 程序 → juhuo
2. 右键点击"juhuo" → 更多 → 以管理员身份运行

**方法2：从命令行**
```cmd
cd "C:\Program Files\juhuo"
launcher.bat --init
```

等待显示 "juhuo initialized successfully!" 表示完成。

### 2.2 启动程序

**方法1：桌面快捷方式**
- 双击桌面上的 `juhuo` 图标

**方法2：开始菜单**
- 开始 → juhuo → 点击程序

**方法3：直接运行**
```cmd
cd "C:\Program Files\juhuo"
launcher.bat
```

### 2.3 打开网页控制台

启动后会自动打开浏览器，如果没有，手动打开：
```
http://localhost:9876
```

---

## 3. 功能介绍

### 3.1 网页控制台

打开 `http://localhost:9876` 可以看到：
- **判断系统**：输入问题，获取十维判断结果
- **记忆系统**：查看因果记忆
- **好奇清单**：查看今日好奇任务
- **Fitness**：查看个人一致性评分

### 3.2 命令行判断

```cmd
cd "C:\Program Files\juhuo"
python cli.py "我应该接受这个offer吗"
```

### 3.3 TUI终端界面

```cmd
cd "C:\Program Files\juhuo"
launcher.bat --tui
```

---

## 4. 命令行使用

### 4.1 查看帮助

```cmd
cd "C:\Program Files\juhuo"
launcher.bat --help
```

### 4.2 判断问题

```cmd
python cli.py "我应该接受这个offer吗"
python cli.py "创业还是打工"
python cli.py "要不要换工作"
```

### 4.3 初始化环境

```cmd
launcher.bat --init
```

---

## 5. 常见问题

### Q1: 提示"Python not found"

**解决方法：**
1. 下载安装 Python：https://www.python.org/downloads/
2. 安装时勾选 "Add Python to PATH"
3. 然后重新运行 `launcher.bat --init`

### Q2: 网页打不开

**解决方法：**
1. 检查程序是否在运行（命令行窗口不要关闭）
2. 确认访问 `http://localhost:9876`
3. 尝试重新启动：`launcher.bat`

### Q3: 程序自动关闭

**解决方法：**
1. 以管理员身份运行
2. 先运行 `launcher.bat --init` 初始化
3. 检查是否缺少依赖，尝试重新安装

### Q4: 端口被占用

如果9876端口被占用，修改 `web_console.py` 中的端口号，然后重新启动。

### Q5: 如何更新

1. 下载新版本
2. 先卸载旧版本
3. 安装新版本

---

## 6. 卸载

### 方法1：从开始菜单
- 开始 → 程序 → juhuo → Uninstall juhuo

### 方法2：从控制面板
- 控制面板 → 程序和功能 → juhuo → 卸载

### 方法3：运行卸载程序
- 双击 `C:\Program Files\juhuo\uninstall_juhuo.exe`

### 方法4：手动删除
1. 删除安装目录 `C:\Program Files\juhuo`
2. 删除桌面快捷方式
3. 删除开始菜单快捷方式

---

## 技术支持

- GitHub: https://github.com/taxatombt/guyong-juhuo
- 问题反馈：GitHub Issues

---

_最后更新：2026-04-17 v1.5_