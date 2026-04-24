# guyong-juhuo 安装指南

> 下载 → 安装 → 开始用。就这么简单。

---

## 下载

👉 https://github.com/taxatombt/guyong-juhuo/releases/latest

下载 `guyong-juhuo-setup.exe`（约 100 MB）

---

## 安装

1. 双击 `guyong-juhuo-setup.exe`
2. 选择安装位置（默认 `C:\Program Files\guyong-juhuo`）
3. 点击"安装"，等待完成
4. 点击"完成"启动程序

安装完成后桌面上会有快捷方式。

---

## 卸载

- **方式一**：开始菜单 → guyong-juhuo → 卸载
- **方式二**：控制面板 → 程序和功能 → guyong-juhuo → 卸载
- **方式三**：运行安装程序 → 选择"卸载"

---

## 安装后完全独立运行

安装版**不依赖**任何项目文件或下载包。安装目录包含全部内容，可直接运行：

```
# 安装目录结构（示例）
C:\Program Files\guyong-juhuo\
├── guyong-juhuo.exe      ← 主程序，双击运行
├── uninstall.exe         ← 卸载程序
├── README.md
└── ...

# 数据文件（用户数据，不在安装包里）
C:\Users\<用户名>\.juhuo\
├── .env                  ← API Key 配置（需手动创建）
├── config.json
└── data\
```

---

## 首次使用

### 配置 API Key（可选，获得完整功能）

安装后运行程序会自动打开网页控制台。如需完整判断能力，创建配置文件：

在 `C:\Users\<用户名>\.juhuo\.env`（新建文件）写入：
```
MINIMAX_API_KEY=你的API密钥
```

不配置也能用，但只能返回 fallback 回答。

### 查看帮助

```
安装目录\guyong-juhuo.exe --help
```

### 网页控制台

安装后自动打开 http://localhost:18768

---

## 常见问题

**Q: 安装后打不开？**
检查控制面板 → 程序和功能，确认安装成功。如有问题，先卸载再重装。

**Q: 端口 18768 被占用？**
程序端口可在 `C:\Users\<用户名>\.juhuo\config.json` 中修改。

**Q: 如何更新？**
下载新版安装程序，运行后会自动升级或提示卸载旧版。

---

## 源码运行（开发者）

```bash
git clone https://github.com/taxatombt/guyong-juhuo.git
cd guyong-juhuo
pip install -r requirements.txt
python cli.py status
```

---

_最后更新：2026-04-21 v2.0_
