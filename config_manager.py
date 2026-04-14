"""
config_manager.py — juhuo 两级配置系统

参考 Hermes Agent 的 ~/.hermes/ 配置模式：

用户级（优先）：
    ~/.juhuo/.env         — API keys（永久保存，不提交git）
    ~/.juhuo/config.yaml  — 用户设置

项目级（回退）：
    {项目根}/.env.example — 配置模板（可提交git）

加载顺序（override=False 保证用户级优先）：
    1. 加载 ~/.juhuo/.env（override=True，用户值覆盖一切）
    2. 加载 {项目根}/.env（override=False，仅填充缺失值）

Setup Wizard（首次运行时）：
    检测 ~/.juhuo/.env 不存在 → 引导用户输入 API key
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Optional

import yaml


# ─── 路径常量 ─────────────────────────────────────────────────────────────────

_IS_WINDOWS = platform.system() == "Windows"

# 用户级配置目录：~/.juhuo/
USER_HOME = Path(os.path.expanduser("~"))
JUHuo_USER_DIR = USER_HOME / ".juhuo"
JUHuo_USER_ENV = JUHuo_USER_DIR / ".env"
JUHuo_USER_CONFIG = JUHuo_USER_DIR / "config.yaml"

# 项目级配置：{项目根}/.env.example
# 注意：不直接读 .env（那是用户可能放置个人配置的地方，只读 .env.example）
PROJECT_ROOT = Path(__file__).parent.resolve()
PROJECT_ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


# ─── dotenv 加载 ─────────────────────────────────────────────────────────────

def _load_dotenv(path: Path, *, override: bool) -> bool:
    """加载单个 .env 文件。成功返回 True。"""
    if not path.exists():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key, val = key.strip(), val.strip()
                    if override:
                        os.environ[key] = val
                    else:
                        os.environ.setdefault(key, val)
        return True
    except Exception:
        return False


def load_dotenv_files() -> list[Path]:
    """
    加载所有 .env 文件，用户级优先。

    Returns:
        已加载的 .env 文件路径列表
    """
    loaded: list[Path] = []

    # 1. 用户级 .env（override=True，用户值覆盖 shell 导出的旧值）
    if _load_dotenv(JUHuo_USER_ENV, override=True):
        loaded.append(JUHuo_USER_ENV)

    # 2. 项目级 .env.example（override=False，仅填充缺失值）
    if _load_dotenv(PROJECT_ENV_EXAMPLE, override=False):
        loaded.append(PROJECT_ENV_EXAMPLE)

    return loaded


# ─── 配置读写 ─────────────────────────────────────────────────────────────────

def ensure_user_dir() -> None:
    """确保用户配置目录存在。"""
    JUHuo_USER_DIR.mkdir(parents=True, exist_ok=True)


def load_user_config() -> dict:
    """加载用户 config.yaml（如果存在）。"""
    if JUHuo_USER_CONFIG.exists():
        try:
            with open(JUHuo_USER_CONFIG, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def save_user_config(cfg: dict) -> None:
    """保存用户 config.yaml。"""
    ensure_user_dir()
    with open(JUHuo_USER_CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


def get_api_key() -> Optional[str]:
    """获取当前配置的 API key（优先环境变量，其次用户 .env）。"""
    return os.environ.get("MINIMAX_API_KEY") or None


def write_api_key(api_key: str) -> None:
    """将 API key 写入用户级 .env 文件。"""
    ensure_user_dir()
    with open(JUHuo_USER_ENV, "w", encoding="utf-8") as f:
        f.write(f"MINIMAX_API_KEY={api_key}\n")
    # 立即更新当前进程的环境变量
    os.environ["MINIMAX_API_KEY"] = api_key


def is_configured() -> bool:
    """检查是否已完成首次配置（有 API key）。"""
    return bool(get_api_key())


# ─── Setup Wizard ─────────────────────────────────────────────────────────────

def run_setup_wizard() -> bool:
    """
    引导用户完成首次配置。

    Returns:
        True = 配置成功；False = 用户取消
    """
    ensure_user_dir()

    print()
    print("=" * 60)
    print("  举火 (juhuo) 首次运行设置")
    print("=" * 60)
    print()
    print("请前往以下网址获取 MiniMax API Key：")
    print("  https://www.minimaxi.com/user-center/basic-information/interface-key")
    print()
    api_key = input("请输入您的 MiniMax API Key（或直接回车取消）: ").strip()

    if not api_key:
        print("取消设置。")
        print("后续可通过以下方式配置：")
        print(f"  1. 创建文件：{JUHuo_USER_ENV}")
        print(f"  2. 在其中写入：MINIMAX_API_KEY=your_key_here")
        print()
        return False

    # 保存到用户级 .env
    with open(JUHuo_USER_ENV, "w", encoding="utf-8") as f:
        f.write(f"MINIMAX_API_KEY={api_key}\n")

    print()
    print(f"✅ API Key 已保存到：{JUHuo_USER_ENV}")
    print()

    # 初始化默认 config.yaml
    default_cfg = {
        "llm_provider": "minimax",
        "llm_model": "MiniMax-M2.7",
        "max_token": 4096,
        "temperature": 0.7,
        "confidence_threshold": 0.5,
        "lesson_recording": True,
    }
    save_user_config(default_cfg)
    print(f"✅ 默认配置已保存到：{JUHuo_USER_CONFIG}")
    print()

    # 初始化数据库
    from database import init_database
    init_database()
    print("✅ 数据库初始化完成。")
    print()
    print("=" * 60)
    print("  设置完成！现在可以开始使用 juhuo")
    print("=" * 60)
    print()

    return True


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def main():
    """CLI 入口：juhuo config"""
    import argparse
    parser = argparse.ArgumentParser(description="juhuo 配置管理")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("show", help="显示当前配置")
    sub.add_parser("wizard", help="运行首次设置向导")

    p = sub.add_parser("set", help="设置配置项")
    p.add_argument("key", help="配置项名称")
    p.add_argument("value", help="配置值")

    p = sub.add_parser("get", help="读取配置项")
    p.add_argument("key", help="配置项名称")

    args = parser.parse_args()

    if args.cmd == "show":
        print(f"用户配置目录：{JUHuo_USER_DIR}")
        print(f"  .env：{JUHuo_USER_ENV}")
        print(f"  config.yaml：{JUHuo_USER_CONFIG}")
        print()
        if is_configured():
            print("✅ API Key：已配置")
        else:
            print("❌ API Key：未配置（运行 'juhuo config wizard' 进行设置）")
        print()
        cfg = load_user_config()
        if cfg:
            print("用户配置项：")
            for k, v in cfg.items():
                print(f"  {k}={v}")
        else:
            print("用户配置项：无（使用默认值）")

    elif args.cmd == "wizard":
        run_setup_wizard()

    elif args.cmd == "get":
        cfg = load_user_config()
        val = cfg.get(args.key)
        if val is not None:
            print(val)
        else:
            print(f"配置项 '{args.key}' 不存在", file=__import__('sys').stderr)
            exit(1)

    elif args.cmd == "set":
        cfg = load_user_config()
        cfg[args.key] = args.value
        save_user_config(cfg)
        print(f"✅ 已保存：{args.key}={args.value}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
