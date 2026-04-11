#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tui_console.py — 聚活 终端图形界面控制台
使用 curses 实现，在终端里就能交互，不需要浏览器

Usage:
    python tui_console.py
"""

import sys
import os
import curses
from datetime import datetime
from typing import List, Tuple

# 添加根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chat_system import load_chat_system, get_current_session
from chat_system.chat_system import ChatMessage


class TUIConsoles:
    """聚活 终端图形界面控制台"""
    
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.cs = load_chat_system()
        self.messages: List[ChatMessage] = []
        self.input_buffer = ""
        self.scroll_offset = 0
        
        # 初始化颜色
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, -1)    # 默认文本
        curses.init_pair(2, curses.COLOR_GREEN, -1)    # 聚活回复
        curses.init_pair(3, curses.COLOR_CYAN, -1)     # 用户消息
        curses.init_pair(4, curses.COLOR_YELLOW, -1)   # 标题/提示
        
        # 获取屏幕尺寸
        self.height, self.width = stdscr.getmaxyx()
        self.chat_height = self.height - 3  # 底部留一行输入
        self.chat_width = self.width
        
    def add_message(self, msg: ChatMessage):
        """添加消息"""
        self.messages.append(msg)
        # 自动滚动到底部
        self.scroll_offset = max(0, len(self.messages) - (self.chat_height - 4))
        
    def render(self):
        """渲染整个界面"""
        self.stdscr.clear()
        self.height, self.width = self.stdscr.getmaxyx()
        self.chat_height = self.height - 3
        self.chat_width = self.width
        
        # 渲染聊天区域
        self._render_chat()
        
        # 渲染输入框
        prompt = ">>> "
        self.stdscr.move(self.height - 1, 0)
        self.stdscr.addstr(prompt, curses.color_pair(4))
        self.stdscr.addstr(self.input_buffer[:self.width - len(prompt) - 1], 
                          curses.color_pair(1))
        
        # 状态行提示
        status = " [Q] 退出 | [Enter] 发送 | ↑↓ 滚动 "
        status_y = self.height - 2
        if status_y >= 0:
            self.stdscr.move(status_y, 0)
            self.stdscr.addstr(status, curses.color_pair(4))
        
        self.stdscr.refresh()
        
    def _render_chat(self):
        """渲染聊天区域"""
        y = 0
        visible_start = self.scroll_offset
        visible_end = min(len(self.messages), visible_start + self.chat_height)
        
        for i in range(visible_start, visible_end):
            msg = self.messages[i]
            color = curses.color_pair(3) if msg.role == "user" else curses.color_pair(2)
            prefix = "你: " if msg.role == "user" else "聚活: "
            
            lines = self._wrap_text(prefix + msg.content, self.chat_width)
            for line in lines:
                if y >= self.chat_height:
                    break
                self.stdscr.move(y, 0)
                self.stdscr.addstr(line, color)
                y += 1
                
    def _wrap_text(self, text: str, width: int) -> List[str]:
        """自动换行"""
        lines = []
        current = ""
        for word in text.split('\n'):
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
            if word:
                lines.append(word)
        return lines
        
    def handle_input(self) -> bool:
        """处理输入，返回 False 表示退出"""
        c = self.stdscr.getch()
        
        if c == curses.KEY_ENTER or c == 10 or c == 13:
            # 回车发送
            if self.input_buffer.strip():
                self._send_message(self.input_buffer.strip())
                self.input_buffer = ""
            return True
            
        elif c == curses.KEY_BACKSPACE or c == 127 or c == 8:
            # 退格
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
            return True
            
        elif c == curses.KEY_UP:
            # 向上滚动
            if self.scroll_offset > 0:
                self.scroll_offset -= 1
            return True
            
        elif c == curses.KEY_DOWN:
            # 向下滚动
            max_offset = max(0, len(self.messages) - (self.chat_height - 4))
            if self.scroll_offset < max_offset:
                self.scroll_offset += 1
            return True
            
        elif c == ord('q') or c == ord('Q'):
            # q 退出
            return False
            
        elif 32 <= c <= 126:
            # 可打印字符
            self.input_buffer += chr(c)
            return True
            
        return True
        
    def _send_message(self, content: str):
        """发送消息处理"""
        # 添加用户消息
        user_msg = ChatMessage(
            message_id="",
            role="user",
            content=content,
            timestamp=datetime.now().isoformat(),
        )
        self.add_message(user_msg)
        
        # 聊天系统处理
        response, result = self.cs.process_user_message(content, auto_trigger=True)
        
        # 添加助手回复
        assistant_msg = ChatMessage(
            message_id="",
            role="assistant",
            content=response,
            timestamp=datetime.now().isoformat(),
            metadata=result,
        )
        self.add_message(assistant_msg)
        
    def run(self):
        """主循环"""
        # 欢迎消息
        welcome = ChatMessage(
            message_id="",
            role="assistant",
            content=(
                "👋 欢迎来到聚活 终端控制台！\n"
                "这是你的个人数字分身，记住你的一切，代替你永远活下去。\n"
                "直接输入问题，按回车发送。输入 q 退出。\n"
                "↑↓ 滚动聊天记录。\n"
            ),
            timestamp=datetime.now().isoformat(),
        )
        self.add_message(welcome)
        
        # 加载现有会话消息
        current = get_current_session(self.cs)
        if current:
            for msg in current.messages:
                if len(self.messages) < 100:  # 不加载太多，避免刷屏
                    self.add_message(msg)
        
        # 主循环
        while True:
            self.render()
            if not self.handle_input():
                break


def main():
    """入口"""
    try:
        curses.wrapper(TUIConsoles).run()
    except KeyboardInterrupt:
        print("\n再见 👋")
        sys.exit(0)


if __name__ == "__main__":
    main()
