"""配置系统"""

import json
import os
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "user_config.json"


class JudgmentConfig:
    """判断框架配置"""
    
    def __init__(self):
        self.default_profile = ""
        self.custom_weights = {}
        self.confidence_threshold = 0.5
        self.lesson_recording = True
        self.llm_provider = "minimax"
        self.llm_api_key = os.environ.get("MINIMAX_API_KEY", "")
        self.llm_model = "MiniMax-M2.7"
        self.max_token = 4096
        self.temperature = 0.7

    def to_dict(self):
        return {
            "default_profile": self.default_profile,
            "custom_weights": self.custom_weights,
            "confidence_threshold": self.confidence_threshold,
            "lesson_recording": self.lesson_recording,
            "llm_provider": self.llm_provider,
            "llm_api_key": self.llm_api_key,
            "llm_model": self.llm_model,
            "max_token": self.max_token,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, d):
        cfg = cls()
        for k, v in d.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


def _load_config():
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            return JudgmentConfig.from_dict(d)
        except (json.JSONDecodeError, KeyError):
            pass
    return JudgmentConfig()


def update_config(config: JudgmentConfig) -> None:
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)


def reset_config() -> None:
    """重置为默认配置"""
    if _CONFIG_PATH.exists():
        os.remove(_CONFIG_PATH)


# 全局单例
cfg = _load_config()
