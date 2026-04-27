---
name: scrapling
description: Advanced web scraping with Scrapling - HTTP/JS/Stealth modes + Spider crawl. Integrated into juhuo perception layer.
version: 1.0.0
metadata:
  juhuo:
    subsystem: perception
    layer: L3 intent
    output: perception_intents table
---

# Scrapling — 高级爬虫适配器（juhuo 感知层集成）

## 来源
- GitHub: `D4Vinci/Scrapling` (MIT, anti-bot/stealth/spider framework)
- 啃读自: `E:\ai\资源\...\optional-skills\research\scrapling\SKILL.md`

## 在 juhuo 的位置
- `perception/scraping_adapter.py` — 懒加载，零依赖（无 scrapling 时不报错）
- `judgment/user_model.py` → `save_perception_result()` — 爬取结果→L3意图

## 三种抓取模式

| 模式 | 类 | 速度 | 用途 |
|------|-----|------|------|
| http | Fetcher | 最快 | 静态页面、API |
| dynamic | DynamicFetcher | 慢 | JS渲染/SPA |
| stealth | StealthyFetcher | 最慢 | Cloudflare/反爬 |

## 核心函数

### scrape(url, mode="http", **kw)
统一入口，自动降级。

```python
from perception.scraping_adapter import scrape

r = scrape("https://quotes.toscrape.com/")           # HTTP (最快)
r = scrape("https://spa.example.com/", mode="dynamic", css_selector="article")
r = scrape("https://protected.com/", mode="stealth", solve_cloudflare=True)
```

### save_to_intents(topic, content, url, source, priority)
爬取结果存入 perception_intents 表（UnifiedProfile L3）。

```python
from perception.scraping_adapter import scrape, save_to_intents

r = scrape("https://news.example.com/tech", mode="http")
if not r.error:
    save_to_intents(topic=r.title or "web content", content=r.text[:2000], url=r.url, source="scrapling", priority=3)
```

## 安装

```bash
pip install "scrapling[all]"
scrapling install   # 安装浏览器（dynamic/stealth 必需）
```

## Scraper vs browser_use

| 场景 | 工具 |
|------|------|
| 静态页面快速提取 | scrape(mode="http") |
| JS 渲染/SPA | scrape(mode="dynamic") |
| Cloudflare 反爬 | scrape(mode="stealth") |
| 多页跟随爬取 | spider_crawl() |
| 需要截图/交互/填表 | browser_use |
| 普通内容阅读 | browser_use (headless) |

## Pitfalls
- 浏览器必需: scrapling install 后 dynamic/stealth 才工作
- timeout: Dynamic/Stealth 用毫秒 (default 30000ms)，Fetcher 用秒
- Cloudflare: solve_cloudflare=True 增加 5-15s 延迟
