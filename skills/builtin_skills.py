#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
builtin_skills.py — Juhuo 内置技能

这些是开箱即用的技能，在系统启动时自动注册。
"""

from typing import Dict, Any


def register_all(registry) -> None:
    """注册所有内置技能"""
    
    # ── 系统技能 ─────────────────────────────────────────────────────────
    
    @registry.register(
        name="help",
        description="获取帮助信息，列出可用技能",
        when_to_use="用户请求帮助或想了解系统能力时",
        argument_hint="[技能名] - 可选，指定要查看帮助的技能",
        tags=["system"]
    )
    def help_skill(args: str, context: Dict) -> Dict:
        """显示帮助信息"""
        if args.strip():
            skill = registry.get(args.strip())
            if skill:
                return {
                    "name": skill.name,
                    "description": skill.description,
                    "when_to_use": skill.when_to_use,
                    "argument_hint": skill.argument_hint,
                }
            return {"error": f"Skill '{args}' not found"}
        
        # 列出所有技能
        skills = registry.list_enabled()
        return {
            "skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "when_to_use": s.when_to_use,
                }
                for s in skills
            ]
        }
    
    # ── 判断技能 ─────────────────────────────────────────────────────────
    
    @registry.register(
        name="judge",
        description="执行十维判断分析",
        when_to_use="需要做复杂决策、分析利弊、权衡取舍时",
        argument_hint="<决策问题> - 要分析的问题或决策",
        tags=["judgment", "decision"]
    )
    def judge_skill(args: str, context: Dict) -> Dict:
        """执行判断"""
        try:
            from judgment import check10d
            result = check10d(args)
            return result
        except ImportError:
            return {"error": "Judgment module not available"}
        except Exception as e:
            return {"error": str(e)}
    
    @registry.register(
        name="judge_full",
        description="执行完整判断分析（含对抗验证）",
        when_to_use="重要决策需要深度分析、验证判断时",
        argument_hint="<决策问题> - 要深度分析的问题",
        tags=["judgment", "decision"]
    )
    def judge_full_skill(args: str, context: Dict) -> Dict:
        """执行完整判断"""
        try:
            from judgment import check10d_full, PipelineConfig, format_full_report
            
            cfg = PipelineConfig(
                enable_adversarial=True,
                enable_qiushi=True,
                confidence_threshold=0.5,
            )
            result = check10d_full(args, config=cfg)
            
            return {
                "report": format_full_report(result),
                "result": result,
            }
        except ImportError:
            return {"error": "Judgment module not available"}
        except Exception as e:
            return {"error": str(e)}
    
    # ── 记忆技能 ─────────────────────────────────────────────────────────
    
    @registry.register(
        name="remember",
        description="保存信息到记忆系统",
        when_to_use="用户说'记住...'、'以后要...'时",
        argument_hint="<内容> - 要记住的信息",
        tags=["memory"]
    )
    def remember_skill(args: str, context: Dict) -> Dict:
        """保存记忆"""
        try:
            from memory_system import save_user_memory
            memory_id = save_user_memory(args)
            return {"success": True, "memory_id": memory_id}
        except ImportError:
            return {"error": "Memory module not available"}
        except Exception as e:
            return {"error": str(e)}
    
    @registry.register(
        name="recall",
        description="从记忆系统召回相关信息",
        when_to_use="需要回忆之前的讨论、偏好、决定时",
        argument_hint="<查询> - 查询相关记忆的关键词",
        tags=["memory"]
    )
    def recall_skill(args: str, context: Dict) -> Dict:
        """召回记忆"""
        try:
            from memory_system import recall_memories
            memories = recall_memories(args, limit=5)
            return {"memories": memories}
        except ImportError:
            return {"error": "Memory module not available"}
        except Exception as e:
            return {"error": str(e)}
    
    # ── 自进化技能 ─────────────────────────────────────────────────────
    
    @registry.register(
        name="evolve",
        description="触发自我进化，检查并应用新规则",
        when_to_use="定期检查、积累足够反馈后需要进化时",
        argument_hint="[dry_run] - 可选，dry_run=只检查不应用",
        tags=["evolution", "self-improve"]
    )
    def evolve_skill(args: str, context: Dict) -> Dict:
        """触发进化"""
        try:
            from judgment.self_evolover import run_evolution_cycle, check_trigger
            
            dry_run = "dry_run" in args.lower()
            
            if dry_run:
                trigger = check_trigger()
                return {"trigger": trigger}
            
            result = run_evolution_cycle()
            return result
        except ImportError:
            return {"error": "Evolver module not available"}
        except Exception as e:
            return {"error": str(e)}
    
    # ── 情绪分析技能 ───────────────────────────────────────────────────
    
    @registry.register(
        name="emotion",
        description="分析情绪状态和信号",
        when_to_use="需要理解情绪信号、焦虑/兴奋指标时",
        argument_hint="<文本> - 要分析的文本",
        tags=["emotion"]
    )
    def emotion_skill(args: str, context: Dict) -> Dict:
        """情绪分析"""
        try:
            from emotion_system.emotion_system import EmotionSystem
            sys = EmotionSystem()
            result = sys.detect_emotion(args)
            return result.to_dict() if hasattr(result, 'to_dict') else result
        except ImportError:
            return {"error": "Emotion module not available"}
        except Exception as e:
            return {"error": str(e)}
    
    # ── 好奇心技能 ─────────────────────────────────────────────────────
    
    @registry.register(
        name="curious",
        description="查询当前好奇心状态和待探索议题",
        when_to_use="查看当前好奇心队列、了解待探索话题时",
        argument_hint="[limit] - 可选，返回数量限制",
        tags=["curiosity"]
    )
    def curious_skill(args: str, context: Dict) -> Dict:
        """好奇心状态"""
        try:
            from curiosity.curiosity_engine import CuriosityEngine
            
            engine = CuriosityEngine()
            limit = 5
            if args.strip().isdigit():
                limit = int(args.strip())
            
            items = engine.get_top_open(limit=limit)
            return {
                "items": [
                    {
                        "id": item.id,
                        "topic": item.topic,
                        "question": item.question,
                        "priority": item.priority,
                        "status": item.status,
                    }
                    for item in items
                ]
            }
        except ImportError:
            return {"error": "Curiosity module not available"}
        except Exception as e:
            return {"error": str(e)}
    
    # ── 目标技能 ───────────────────────────────────────────────────────
    
    @registry.register(
        name="goals",
        description="查看和管理目标系统",
        when_to_use="查看当前目标、设置新目标、检视进度时",
        argument_hint="[list|add|done] - 操作类型",
        tags=["goals"]
    )
    def goals_skill(args: str, context: Dict) -> Dict:
        """目标管理"""
        try:
            from goal_system.goal_manager import GoalManager
            
            manager = GoalManager()
            parts = args.strip().split(None, 1)
            cmd = parts[0] if parts else "list"
            
            if cmd == "list":
                goals = manager.list_goals()
                return {"goals": goals}
            elif cmd == "add" and len(parts) > 1:
                goal_id = manager.add_goal(parts[1])
                return {"success": True, "goal_id": goal_id}
            elif cmd == "done" and len(parts) > 1:
                manager.mark_done(parts[1])
                return {"success": True}
            
            return {"usage": "goals [list|add <text>|done <id>]"}
        except ImportError:
            return {"error": "Goal module not available"}
        except Exception as e:
            return {"error": str(e)}
    
    # ── 搜索技能 ───────────────────────────────────────────────────────
    
    @registry.register(
        name="search",
        description="搜索网络获取信息",
        when_to_use="需要最新信息、实时数据、网上资料时",
        argument_hint="<查询> - 搜索关键词",
        tags=["search", "web"]
    )
    def search_skill(args: str, context: Dict) -> Dict:
        """网络搜索"""
        # 简单的搜索实现，实际可接入真实搜索引擎
        return {
            "query": args,
            "result": f"Search functionality for: {args}",
            "note": "Connect to real search API for production use"
        }
    
    # ── 代码技能 ───────────────────────────────────────────────────────
    
    @registry.register(
        name="code_review",
        description="代码审查",
        when_to_use="需要审查代码、发现潜在问题时",
        argument_hint="<代码> 或 @<文件> - 要审查的代码或文件",
        tags=["code", "review"]
    )
    def code_review_skill(args: str, context: Dict) -> Dict:
        """代码审查"""
        # 简单的审查规则
        issues = []
        
        if "TODO" in args or "FIXME" in args:
            issues.append("发现未完成的任务标记")
        
        if len(args) > 1000:
            issues.append("代码过长，建议拆分成更小的函数")
        
        # 检查常见问题
        dangerous_patterns = [
            ("eval(", "使用 eval 可能导致安全问题"),
            ("exec(", "使用 exec 可能导致安全问题"),
            ("password = ", "硬编码密码"),
            ("api_key = ", "硬编码 API 密钥"),
        ]
        
        for pattern, msg in dangerous_patterns:
            if pattern in args:
                issues.append(msg)
        
        return {
            "issues": issues,
            "has_issues": len(issues) > 0,
        }
