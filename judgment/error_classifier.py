#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
error_classifier.py — API 错误5分类 + 恢复策略

集成来源：ECC Codex error_classifier → judgment/
设计原则：
- 遇到 API 错误时，5分类判断 + 对应恢复策略
- 分类：rate_limit / auth_error / server_error / network_error / parse_error
- 不只是记录错误，是驱动后续行为

使用方式：
    from judgment.error_classifier import ErrorClassifier, ErrorType, RecoveryStrategy

    classifier = ErrorClassifier()
    result = classifier.classify(error_response)
    print(f"类型: {result.error_type.name}, 策略: {result.strategy.name}")
    if result.strategy == RecoveryStrategy.RETRY_WITH_BACKOFF:
        await asyncio.sleep(result.retry_after)
"""
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Dict, Any
import asyncio


class ErrorType(Enum):
    RATE_LIMIT = auto()      # 限速：429 / 限流
    AUTH_ERROR = auto()      # 认证失败：401 / 403
    SERVER_ERROR = auto()    # 服务端错误：500-599
    NETWORK_ERROR = auto()  # 网络错误：超时/连接失败
    PARSE_ERROR = auto()     # 解析错误：JSON decode 失败


class RecoveryStrategy(Enum):
    RETRY_WITH_BACKOFF = auto()   # 指数退避重试
    REFRESH_TOKEN = auto()        # 刷新 token 后重试
    SWITCH_ENDPOINT = auto()      # 切换端点
    ABORT = auto()                # 直接放弃
    FALLBACK = auto()             # 降级处理


@dataclass
class ErrorClassifyResult:
    error_type: ErrorType
    strategy: RecoveryStrategy
    retry_after: Optional[float] = None  # 秒
    detail: Optional[str] = None
    original_error: Optional[Dict[str, Any]] = None


class ErrorClassifier:
    """API 错误5分类器 + 恢复策略"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def classify(self, error: Any) -> ErrorClassifyResult:
        """
        入口：根据错误对象判断类型和策略
        error 可以是：requests.Response / Exception / dict / str
        """
        # 1. 从 Response 对象提取
        if hasattr(error, "status_code"):
            return self._from_response(error)
        # 2. 从 Exception 提取
        if isinstance(error, Exception):
            return self._from_exception(error)
        # 3. 从 dict 提取
        if isinstance(error, dict):
            return self._from_dict(error)
        # 4. fallback
        return ErrorClassifyResult(
            error_type=ErrorType.SERVER_ERROR,
            strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
            detail="未知错误类型"
        )

    def _from_response(self, resp) -> ErrorClassifyResult:
        status = getattr(resp, "status_code", 0)
        body = {}
        try:
            body = resp.json() if hasattr(resp, "json") else {}
        except Exception:
            pass

        # 429 Rate Limit
        if status == 429:
            retry_after = float(resp.headers.get("Retry-After", 60))
            return ErrorClassifyResult(
                error_type=ErrorType.RATE_LIMIT,
                strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
                retry_after=retry_after,
                detail=body.get("error", "Rate limited"),
                original_error={"status": status, "body": body}
            )

        # 401 / 403 Auth
        if status in (401, 403):
            return ErrorClassifyResult(
                error_type=ErrorType.AUTH_ERROR,
                strategy=RecoveryStrategy.REFRESH_TOKEN,
                detail=body.get("error", "Auth failed"),
                original_error={"status": status, "body": body}
            )

        # 500-599 Server Error
        if 500 <= status < 600:
            return ErrorClassifyResult(
                error_type=ErrorType.SERVER_ERROR,
                strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
                retry_after=5.0,
                detail=body.get("error", f"Server error {status}"),
                original_error={"status": status, "body": body}
            )

        # 4xx others
        if 400 <= status < 500:
            return ErrorClassifyResult(
                error_type=ErrorType.PARSE_ERROR,
                strategy=RecoveryStrategy.ABORT,
                detail=body.get("error", f"Client error {status}"),
                original_error={"status": status, "body": body}
            )

        return ErrorClassifyResult(
            error_type=ErrorType.SERVER_ERROR,
            strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
            original_error={"status": status}
        )

    def _from_exception(self, exc: Exception) -> ErrorClassifyResult:
        name = type(exc).__name__.lower()

        if "timeout" in name or "connect" in name or "connection" in name:
            return ErrorClassifyResult(
                error_type=ErrorType.NETWORK_ERROR,
                strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
                retry_after=3.0,
                detail=str(exc),
                original_error={"exception": name}
            )

        if "json" in name or "decode" in name or "parse" in name:
            return ErrorClassifyResult(
                error_type=ErrorType.PARSE_ERROR,
                strategy=RecoveryStrategy.ABORT,
                detail=str(exc),
                original_error={"exception": name}
            )

        if "auth" in name or "credential" in name or "token" in name:
            return ErrorClassifyResult(
                error_type=ErrorType.AUTH_ERROR,
                strategy=RecoveryStrategy.REFRESH_TOKEN,
                detail=str(exc),
                original_error={"exception": name}
            )

        return ErrorClassifyResult(
            error_type=ErrorType.SERVER_ERROR,
            strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
            detail=str(exc),
            original_error={"exception": name}
        )

    def _from_dict(self, d: Dict) -> ErrorClassifyResult:
        # {"error": "...", "type": "rate_limit"} 之类的结构
        err_type = d.get("type", "").lower()
        if err_type == "rate_limit":
            return ErrorClassifyResult(
                error_type=ErrorType.RATE_LIMIT,
                strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
                retry_after=d.get("retry_after", 60),
                detail=d.get("error", "Rate limited")
            )
        if err_type == "auth":
            return ErrorClassifyResult(
                error_type=ErrorType.AUTH_ERROR,
                strategy=RecoveryStrategy.REFRESH_TOKEN,
                detail=d.get("error", "Auth error")
            )
        return ErrorClassifyResult(
            error_type=ErrorType.SERVER_ERROR,
            strategy=RecoveryStrategy.RETRY_WITH_BACKOFF,
            detail=d.get("error", str(d))
        )


# 独立使用函数
def classify(error: Any) -> ErrorClassifyResult:
    return ErrorClassifier().classify(error)
