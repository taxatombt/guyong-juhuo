# juhuo · 聚活

**一个会进化的个人数字分身。**

模拟特定个体的思维方式，在判断力上超越人类整体。

---

## 🚀 快速开始

### 下载地址

点击 **Code** → **Download ZIP**，或从 [Releases](https://github.com/taxatombt/guyong-juhuo/releases) 下载

下载后找到 **`juhuo.exe`**（100MB）

### 使用方法

1. **双击 `juhuo.exe`**
2. 等待自动打开浏览器
3. 访问 **http://localhost:9876**

**完成！不需要Python，不需要安装，不需要任何依赖。**

---

## 📖 使用指南

### 1. 打开网页控制台

运行 `juhuo.exe` 后，浏览器自动打开 `http://localhost:9876`

可以看到：
- **判断系统** - 输入问题，获取十维判断结果
- **记忆系统** - 查看因果记忆
- **好奇清单** - 查看今日好奇任务
- **Fitness** - 查看个人一致性评分

### 2. 命令行判断

```cmd
# 如果在同一目录
python cli.py "我应该接受这个offer吗"
```

### 3. 停止程序

在命令行窗口按 **Ctrl+C**

---

## 🔧 技术规格

| 项目 | 说明 |
|------|------|
| 文件大小 | ~100MB |
| Python依赖 | 无（已打包） |
| 需要安装 | 否 |
| 端口 | 9876 |
| 浏览器 | 自动打开 |

---

## ❓ 常见问题

### Q: 提示"Python not found"
**A**: 不需要Python！`juhuo.exe` 已经包含Python运行环境。

### Q: 防火墙提示
**A**: 点击"允许"即可，这是正常的程序运行提示。

### Q: 端口9876被占用
**A**: 关闭占用9876端口的程序，或联系我们修改端口。

### Q: 无法打开浏览器
**A**: 手动打开浏览器访问 `http://localhost:9876`

### Q: 程序自动关闭
**A**: 确保双击的是 `juhuo.exe`，不是其他文件。

---

## 🗑️ 卸载

删除 `juhuo.exe` 即可，无需其他操作。

---

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `juhuo.exe` | 完整打包版（推荐下载） |
| `setup.iss` | Inno Setup脚本（用于重新打包） |
| `launcher.bat` | 启动脚本（源码版使用） |
| `INSTALL_GUIDE.md` | 详细安装指南 |

---

## 🔧 开发者信息

### 从源码运行

```bash
# 克隆项目
git clone https://github.com/taxatombt/guyong-juhuo.git
cd guyong-juhuo

# 安装依赖
pip install -r requirements.txt

# 运行
python web_console.py
# 或
launcher.bat
```

### 重新打包

用 Inno Setup 打开 `setup.iss`，编译生成新的安装包。

---

## 铁律

> **模拟特定具体个体，最终在判断力上超越人类整体。**

---

## 技术支持

- GitHub: https://github.com/taxatombt/guyong-juhuo
- Issues: https://github.com/taxatombt/guyong-juhuo/issues

---

_最后更新：2026-04-16 v1.3_