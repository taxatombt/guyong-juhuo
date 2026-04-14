#!/usr/bin/env python3
"""
installer/build_installer.py
===========================
无 Inno Setup 时的替代打包工具。
将聚活打包为单个目录的绿色版或 ZIP 压缩包。

用法:
    python build_installer.py              # 生成绿色版 + ZIP
    python build_installer.py --dir        # 只生成目录
    python build_installer.py --zip        # 只生成 ZIP
    python build_installer.py --deep-check # 深度依赖检测
"""

import sys
import os
import shutil
import zipfile
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
OUT_DIR = ROOT / "dist"
STAGING_DIR = ROOT / "dist" / "guyong-juhuo"
EXCLUDES = {".git", "__pycache__", ".github", "node_modules",
            ".venv", ".env", "*.pyc", "*.pyo", "*.db", "*.log",
            "*.egg-info", ".pytest_cache", "dist", "build", ".vscode"}


def copytree_filter(src: Path, dst: Path, excludes: set):
    """带过滤的目录复制"""
    src = Path(src)
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)

    for item in src.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src)
        # 检查是否排除
        parts = set(rel.parts)
        if any(ex in parts or str(item).endswith(ex.lstrip("*"))
               for ex in excludes):
            continue
        # 跳过二进制/大文件（但保留 .py）
        size = item.stat().st_size
        if size > 50 * 1024 * 1024:  # > 50MB 跳过
            continue
        dest_file = dst / rel
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest_file)


def check_python_deps():
    """检查关键依赖是否可导入"""
    critical = [
        "flask", "werkzeug", "jinja2", "markdown",
        "feedparser", "imap_tools"
    ]
    missing = []
    for pkg in critical:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    return missing


def check_pyinstaller():
    """检查 PyInstaller 是否可用"""
    try:
        subprocess.run(["pyinstaller", "--version"],
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def build_staging():
    """构建临时目录"""
    print("[1/3] 复制项目文件...")
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    copytree_filter(ROOT, STAGING_DIR, EXCLUDES)
    print(f"      → {STAGING_DIR}")
    return STAGING_DIR


def build_zip():
    """生成 ZIP 压缩包"""
    print("[2/3] 打包 ZIP...")
    zip_path = OUT_DIR / f"guyong-juhuo-1.0.0-portable.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in STAGING_DIR.rglob("*"):
            if item.is_file():
                arcname = item.relative_to(STAGING_DIR)
                zf.write(item, arcname)
    print(f"      → {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return zip_path


def build_pyinstaller_exe():
    """用 PyInstaller 打包 launcher 为 exe"""
    print("[3/3] 编译为 EXE（可选）...")
    launcher_src = ROOT / "installer" / "launcher.bat"
    exe_path = STAGING_DIR / "聚活.exe"

    # 简单方案：复制 bat，重命名为 exe
    # 真实 exe 需要 PyInstaller 或 C 编译
    shutil.copy2(launcher_src, exe_path)

    if check_pyinstaller():
        print("      [提示] PyInstaller 可用，可将 launcher.bat 编译为独立 exe")
        print("      pyinstaller --onefile --name guyong-juhuo launcher.bat")
    return exe_path


def check_deps_deep():
    """深度依赖检测"""
    print("\n=== 深度依赖检测 ===")
    missing = check_python_deps()
    if not missing:
        print("[OK] 所有核心依赖已安装")
    else:
        print(f"[缺失] {', '.join(missing)}")
        print(f"       运行: pip install -r requirements.txt")

    # 检查 Python 版本
    v = sys.version_info
    print(f"[Python] {v.major}.{v.minor}.{v.micro}")
    if v < (3, 8):
        print("[警告] Python 3.8+ 推荐")

    # 检查关键文件
    key_files = ["hub.py", "web_console.py", "requirements.txt"]
    for f in key_files:
        status = "[OK]" if (ROOT / f).exists() else "[缺失]"
        print(f"  {status} {f}")


def main():
    parser = argparse.ArgumentParser(description="聚活安装包构建工具")
    parser.add_argument("--dir", action="store_true", help="只生成目录")
    parser.add_argument("--zip", action="store_true", help="只生成 ZIP")
    parser.add_argument("--deep-check", action="store_true", help="深度依赖检测")
    args = parser.parse_args()

    if args.deep_check:
        check_deps_deep()
        return

    OUT_DIR.mkdir(exist_ok=True)

    print("聚活 (guyong-juhuo) 打包工具")
    print(f"输出目录: {OUT_DIR}")
    print()

    build_staging()

    if not args.dir:
        build_zip()

    build_pyinstaller_exe()

    print()
    print("=== 打包完成 ===")
    print(f"  绿色版目录: {STAGING_DIR}")
    if not args.dir:
        print(f"  ZIP 压缩包: {OUT_DIR / 'guyong-juhuo-1.0.0-portable.zip'}")
    print()
    print("  使用方式:")
    print("  1. 绿色版：解压后双击 installer\\launcher.bat --init 初始化")
    print("  2. ZIP：解压后双击 launcher.bat --init 初始化")
    print("  3. Inno Setup：有 setup.iss 可以编译为标准 Windows 安装程序")


if __name__ == "__main__":
    main()
