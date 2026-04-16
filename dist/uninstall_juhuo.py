#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uninstall_juhuo.py - 聚活卸载程序
打包成exe后双击即可运行
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path

def is_admin():
    try:
        return subprocess.check_call(
            "net session", 
            shell=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        ) == 0
    except:
        return False

def find_install_dir():
    """搜索安装目录"""
    candidates = [
        Path(r"C:\Program Files\聚活"),
        Path(r"C:\Program Files (x86)\聚活"),
        Path(r"E:\juhuo"),
        Path(os.getcwd()),
    ]
    for d in candidates:
        if d.exists() and (d / "cli.py").exists():
            return d
    return None

def find_user_data_dir():
    """搜索用户数据目录"""
    candidates = [
        Path(os.path.expanduser("~/.juhuo")),
        Path(os.path.expandvars(r"%APPDATA\juhuo")),
    ]
    for d in candidates:
        if d.exists():
            return d
    return None

def delete_shortcut(path):
    """删除快捷方式"""
    try:
        if Path(path).exists():
            Path(path).unlink()
            return True
    except:
        pass
    return False

def clear_env_var(name):
    """清除环境变量"""
    try:
        subprocess.run(
            f'setx {name} ""',
            shell=True, capture_output=True
        )
        return True
    except:
        return False

def main():
    print()
    print("=" * 45)
    print("         聚活 (juhuo) 卸载程序")
    print("=" * 45)
    print()
    
    # 检查管理员权限
    if not is_admin():
        print("[错误] 需要管理员权限")
        print("请右键选择'以管理员身份运行'")
        input("\n按Enter退出...")
        sys.exit(1)
    
    # 查找安装
    install_dir = find_install_dir()
    user_data_dir = find_user_data_dir()
    
    print("找到以下安装内容:")
    if install_dir:
        print(f"  [+] 安装目录: {install_dir}")
    else:
        print(f"  [-] 安装目录: 未找到")
    
    if user_data_dir:
        print(f"  [+] 用户数据: {user_data_dir}")
    print()
    
    # 确认
    confirm = input("确定要卸载聚活吗？(y/N): ").strip().lower()
    if confirm != 'y':
        print("取消卸载")
        sys.exit(0)
    
    print("\n正在卸载...\n")
    
    # 1. 删除安装目录
    if install_dir:
        print(f"[删除] 安装目录: {install_dir}")
        try:
            shutil.rmtree(install_dir)
            print("      [完成]")
        except Exception as e:
            print(f"      [失败] {e}")
            print("      请先关闭聚活程序后重试")
    
    # 2. 删除桌面快捷方式
    desktop = Path(os.path.expanduser("~/Desktop"))
    for name in ["聚活.lnk", "juhuo.lnk", "聚活.exe.lnk"]:
        if delete_shortcut(desktop / name):
            print("[删除] 桌面快捷方式: " + name)
    
    # 3. 删除开始菜单
    start_menu = Path(os.path.expandvars(r"%APPDATA\Microsoft\Windows\Start Menu\Programs"))
    for name in ["聚活.lnk", "juhuo.lnk"]:
        if delete_shortcut(start_menu / name):
            print("[删除] 开始菜单: " + name)
    
    # 4. 删除用户数据
    if user_data_dir:
        print(f"\n是否删除用户数据? (当前目录: {user_data_dir})")
        clean = input("删除用户数据？(y/N): ").strip().lower()
        if clean == 'y':
            try:
                shutil.rmtree(user_data_dir)
                print("[删除] 用户数据 [完成]")
            except Exception as e:
                print(f"[删除] 用户数据 [失败] {e}")
    
    print()
    print("=" * 45)
    print("         卸载完成")
    print("=" * 45)
    print()
    input("按Enter退出...")

if __name__ == "__main__":
    main()