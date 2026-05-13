#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cache_strategy.py — 三层缓存降级策略

来源：koala73/worldmonitor（54k★）

核心理念：
- 数据请求不只靠实时，还应有 L1→L2→L3 三层降级兜底
- 任一层命中则返回，不继续往下走
- 三层全 miss 才走实时，并在返回后回填缓存

三层设计（从快到慢）：
  L1: 内存缓存         → 极快，TTL 短（秒级）
  L2: 本地磁盘文件     → 快，TTL 中等（分钟级）
  L3: 实时请求         → 慢，可靠

降级顺序：L1 → L2 → L3 → raise（全部失败）
回填：L3 命中后自动回填 L2 和 L1
"""

import os
import json
import time
import hashlib
import threading
import shutil
from pathlib import Path
from typing import Optional, Any, Callable, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta

try:
    from paths import PATHS
except ImportError:
    PATHS = {"DATA": os.path.join(os.path.dirname(__file__), "..", "data")}


CACHE_DIR = Path(PATHS["DATA"]) / "perception_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── 缓存配置 ─────────────────────────────────────────────────────────

@dataclass
class CacheConfig:
    """三层缓存配置"""
    # L1: 内存缓存
    l1_enabled: bool = True
    l1_max_size: int = 200          # 最大条目数
    l1_ttl_seconds: float = 30.0     # TTL（秒）

    # L2: 磁盘缓存
    l2_enabled: bool = True
    l2_dir: Path = None              # 默认在 CACHE_DIR / "l2"
    l2_ttl_seconds: float = 300.0   # 5分钟 TTL

    # L3: 实时请求（无缓存）
    l3_timeout_seconds: float = 10.0

    def __post_init__(self):
        if self.l2_dir is None:
            self.l2_dir = CACHE_DIR / "l2"


# ── L1: 内存缓存（LRU） ────────────────────────────────────────────────

class L1Cache:
    """内存缓存，线程安全，LRU 驱逐"""

    def __init__(self, max_size: int = 200, ttl: float = 30.0):
        self.max_size = max_size
        self.ttl = ttl
        self._store: Dict[str, Dict] = {}  # key → {value, timestamp}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time.time() - entry["ts"] > self.ttl:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            # 移到末尾（recent）
            self._store[key] = self._store.pop(key)
            return entry["value"]

    def set(self, key: str, value: Any):
        with self._lock:
            if len(self._store) >= self.max_size:
                # 驱逐最老的 N 个
                to_evict = max(1, self.max_size // 10)
                for _ in range(to_evict):
                    self._store.pop(next(iter(self._store)))
            self._store[key] = {"value": value, "ts": time.time()}

    def invalidate(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()

    def stats(self) -> Dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total > 0 else 0,
                "size": len(self._store),
            }


# ── L2: 磁盘缓存 ──────────────────────────────────────────────────────

class L2Cache:
    """磁盘文件缓存，JSONL 格式，TTL 控制"""

    def __init__(self, cache_dir: Path, ttl: float = 300.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl

    def _key_to_path(self, key: str) -> Path:
        h = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{h}.json"

    def get(self, key: str) -> Optional[Any]:
        path = self._key_to_path(key)
        if not path.exists():
            return None
        try:
            age = time.time() - path.stat().st_mtime
            if age > self.ttl:
                path.unlink(missing_ok=True)
                return None
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("value")
        except Exception:
            return None

    def set(self, key: str, value: Any):
        path = self._key_to_path(key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"key": key, "value": value, "ts": time.time()}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 磁盘满等情况下静默失败

    def invalidate(self, key: str):
        path = self._key_to_path(key)
        path.unlink(missing_ok=True)

    def clear_expired(self):
        """清理过期文件"""
        now = time.time()
        removed = 0
        for f in self.cache_dir.glob("*.json"):
            if now - f.stat().st_mtime > self.ttl:
                f.unlink(missing_ok=True)
                removed += 1
        return removed


# ── 核心：三层缓存上下文管理器 ──────────────────────────────────────────

_global_l1: Optional[L1Cache] = None
_global_l2: Optional[L2Cache] = None


def get_l1() -> L1Cache:
    global _global_l1
    if _global_l1 is None:
        _global_l1 = L1Cache()
    return _global_l1


def get_l2() -> L2Cache:
    global _global_l2
    if _global_l2 is None:
        _global_l2 = L2Cache(CACHE_DIR / "l2")
    return _global_l2


def cached_fetch(
    cache_key: str,
    fetch_fn: Callable[[], Any],
    config: Optional[CacheConfig] = None,
    skip_l1: bool = False,
    skip_l2: bool = False,
) -> Any:
    """
    三层缓存统一入口。

    用法示例：
        data = cached_fetch(
            cache_key="btc_price_1m",
            fetch_fn=lambda: requests.get("https://api...").json(),
        )

    参数：
        cache_key   — 缓存的唯一 key（会做 MD5 散列）
        fetch_fn    — L3 实时获取函数（无缓存时调用）
        config      — 缓存配置（默认用全局配置）
        skip_l1/skip_l2 — 跳过指定层（用于强制刷新）

    返回：fetch_fn() 的返回值
    异常：只有三层全 fail 才 raise
    """
    if config is None:
        config = CacheConfig()

    # L1: 内存
    if not skip_l1 and config.l1_enabled:
        l1 = get_l1()
        val = l1.get(cache_key)
        if val is not None:
            return val

    # L2: 磁盘
    if not skip_l2 and config.l2_enabled:
        l2 = get_l2()
        val = l2.get(cache_key)
        if val is not None:
            # 回填 L1
            if config.l1_enabled:
                get_l1().set(cache_key, val)
            return val

    # L3: 实时
    try:
        result = fetch_fn()
        # 回填 L2 和 L1
        if config.l2_enabled:
            get_l2().set(cache_key, result)
        if config.l1_enabled:
            get_l1().set(cache_key, result)
        return result
    except Exception as e:
        # 三层全 fail
        raise CachedFetchError(f"All cache layers failed for '{cache_key}': {e}") from e


class CachedFetchError(Exception):
    """三层缓存全部失败的异常"""
    pass


# ── 便捷装饰器 ─────────────────────────────────────────────────────────

def perception_cache(
    key: str,
    ttl_seconds: float = 30.0,
    config: Optional[CacheConfig] = None,
):
    """
    装饰器：为 perception 函数加三层缓存。

    示例：
        @perception_cache("search_趋势_24h", ttl_seconds=300)
        def fetch_trend(keyword: str) -> dict:
            return remote_api(keyword)
    """
    def decorator(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            # 动态构建 cache_key（函数名 + 参数）
            import pickle
            param_key = f"{fn.__name__}:{pickle.dumps((args, kwargs))}"
            full_key = f"{key}:{hashlib.md5(param_key.encode()).hexdigest()}"
            return cached_fetch(full_key, lambda: fn(*args, **kwargs), config)
        return wrapper
    return decorator


# ── 管理工具 ────────────────────────────────────────────────────────────

def cache_stats() -> Dict[str, Any]:
    """返回各层缓存统计"""
    l1 = get_l1()
    l2 = get_l2()
    l2_files = len(list((CACHE_DIR / "l2").glob("*.json"))) if (CACHE_DIR / "l2").exists() else 0
    return {
        "l1_memory": l1.stats(),
        "l2_disk_files": l2_files,
        "l2_dir": str(CACHE_DIR / "l2"),
    }


def cache_clear(layer: str = "all"):
    """清理指定层缓存"""
    if layer in ("all", "l1"):
        get_l1().clear()
    if layer in ("all", "l2"):
        shutil.rmtree(CACHE_DIR / "l2", ignore_errors=True)
        (CACHE_DIR / "l2").mkdir(parents=True, exist_ok=True)
    if layer in ("all",):
        # 也清理 L2 根目录
        for f in CACHE_DIR.glob("*.json"):
            f.unlink(missing_ok=True)


def cache_invalidate(key: str, layer: str = "all"):
    """让某个 key 在指定层失效"""
    if layer in ("all", "l1"):
        get_l1().invalidate(key)
    if layer in ("all", "l2"):
        get_l2().invalidate(key)
