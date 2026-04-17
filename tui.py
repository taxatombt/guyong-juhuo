#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tui.py — Juhuo 终端用户界面

借鉴 Codex TUI：简洁的终端交互界面
"""

import sys
from pathlib import Path

# 检查 urwid 是否可用
try:
    import urwid
    HAS_URWID = True
except ImportError:
    HAS_URWID = False

from judgment.logging_config import get_logger
log = get_logger("juhuo.tui")


class JuhuoTUI:
    """
    Juhuo 终端界面
    
    功能：
    - 显示判断结果
    - 交互式输入
    - 历史记录
    """
    
    PALETTE = [
        ('title', 'dark red', 'black'),
        ('body', 'white', 'black'),
        ('prompt', 'light green', 'black'),
        ('result', 'light blue', 'black'),
        ('error', 'light red', 'black'),
    ]
    
    def __init__(self):
        if not HAS_URWID:
            print("⚠️ urwid 未安装，请运行: pip install urwid")
            print("使用 fallback 模式...")
            self.use_fallback = True
        else:
            self.use_fallback = False
            self.loop = None
            self.input_edit = None
            self.output_text = None
    
    def run(self) -> None:
        """运行 TUI"""
        if self.use_fallback:
            self.run_fallback()
        else:
            self.run_urwid()
    
    def run_fallback(self) -> None:
        """Fallback 简单界面"""
        print("\n" + "="*50)
        print("  聚活 Juhuo TUI")
        print("="*50)
        print("\n输入问题，回车获取十维判断。输入 quit 退出。\n")
        
        while True:
            try:
                task = input("❓ > ").strip()
                if not task:
                    continue
                if task.lower() in ["quit", "exit", "q"]:
                    print("再见！")
                    break
                
                print("\n🔄 分析中...\n")
                result = self._judge(task)
                self._print_result(result)
                
            except KeyboardInterrupt:
                print("\n再见！")
                break
            except Exception as e:
                print(f"❌ 错误: {e}")
    
    def run_urwid(self) -> None:
        """urwid 界面"""
        import urwid
        
        # 头部
        header = urwid.Text(" 聚活 Juhuo TUI", align='center')
        header = urwid.AttrWrap(header, 'title')
        
        # 输出区
        self.output_text = urwid.Text("")
        output_box = urwid.ScrollingHill(urwid.Filler(self.output_text))
        
        # 输入区
        self.input_edit = urwid.Edit("❓ > ", "")
        input_line = urwid.AttrMap(self.input_edit, 'prompt')
        
        # 按钮
        btn_submit = urwid.Button("判断", on_press=self._on_submit)
        btn_quit = urwid.Button("退出", on_press=self._on_quit)
        buttons = urwid.Columns([btn_submit, btn_quit])
        
        # 布局
        pile = urwid.Pile([
            ('weight', 1, output_box),
            urwid.Divider(),
            input_line,
            buttons,
        ])
        
        frame = urwid.Frame(pile, header=header)
        
        self.loop = urwid.MainLoop(frame, self.PALETTE)
        self.loop.run()
    
    def _on_submit(self, button) -> None:
        """提交判断"""
        if self.input_edit:
            task = self.input_edit.get_text()[0].strip()
            if task:
                self._append_output(f"\n❓ {task}\n")
                self.input_edit.set_edit_text("")
                
                result = self._judge(task)
                self._print_result(result)
    
    def _on_quit(self, button) -> None:
        """退出"""
        raise urwid.ExitMainLoop()
    
    def _append_output(self, text: str) -> None:
        """添加输出"""
        if self.output_text:
            current = self.output_text.get_text()[0]
            self.output_text.set_text(current + text)
    
    def _judge(self, task: str) -> Dict:
        """执行判断"""
        try:
            from judgment.judgment_engine import check10d
            return check10d(task)
        except Exception as e:
            log.error(f"Judge error: {e}")
            return {"error": str(e)}
    
    def _print_result(self, result: Dict) -> None:
        """打印结果"""
        if self.use_fallback:
            if "error" in result:
                print(f"❌ {result['error']}\n")
                return
            
            print("📊 十维分析结果：")
            for dim in result.get("must_check", []) + result.get("important", []):
                print(f"  • {dim}")
            
            if result.get("recommendation"):
                print(f"\n💡 建议: {result['recommendation']}")
            print()
        else:
            if "error" in result:
                self._append_output(f"❌ {result['error']}\n")
                return
            
            lines = ["📊 十维分析结果："]
            for dim in result.get("must_check", []) + result.get("important", []):
                lines.append(f"  • {dim}")
            
            if result.get("recommendation"):
                lines.append(f"\n💡 建议: {result['recommendation']}")
            
            self._append_output("\n".join(lines) + "\n")


def run_tui() -> None:
    """运行 TUI"""
    tui = JuhuoTUI()
    tui.run()


if __name__ == "__main__":
    run_tui()
