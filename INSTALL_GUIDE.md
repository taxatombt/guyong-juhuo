# guyong-juhuo 使用指南

> 下载 → 双击 → 开始用。就这么简单。

---

## 方式一：直接运行（推荐，最快）

### 1. 下载

👉 https://github.com/taxatombt/guyong-juhuo/releases/latest

下载 `guyong-juhuo.exe`（约 103 MB）

### 2. 双击运行

就一个 exe，双击直接启动。关闭即退出，无需安装。

---

## 方式二：源码运行

### 1. 下载代码

```bash
git clone https://github.com/taxatombt/guyong-juhuo.git
cd guyong-juhuo
```

### 2. 运行

```bash
python cli.py status          # 查看状态
python cli.py "要不要辞职创业"  # 判断一个问题
python cli.py web             # 打开网页控制台（默认 port 18768）
```

---

## 常见用法

### 判断一个问题
```
python cli.py "要不要辞职创业"
```

### 查看判断历史
```
python cli.py verdict list
```

### 查看状态
```
python cli.py status
```

### 查看用户画像（需要先添加）
```
python cli.py bio add "我30岁程序员已婚"
python cli.py bio show
```

### 查看行为统计
```
python cli.py behavior stats
```

### 网页控制台
```
python cli.py web
# 浏览器打开 http://localhost:18768
```

---

## 首次使用

**需要配置 MiniMax API Key（才能获得完整判断结果）：**

1. 打开 `cli.py web` 网页控制台
2. 或手动创建 `~/.juhuo/.env` 文件，写入：
   ```
   MINIMAX_API_KEY=你的API密钥
   ```

不配置也能用，但只能返回 fallback 回答。

---

## Life OS 任务排序（独立功能，不需要 API Key）

```bash
python life_os.py 写报告 健身 见客户 --energy 80 --emotion P=0.5,A=0.6,D=0.7
```

---

## 卸载

- **方式一**：直接删除 `guyong-juhuo.exe`
- **方式二**（安装版）：控制面板 → 程序和功能 → 卸载

---

_最后更新：2026-04-21 v2.0_
