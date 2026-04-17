#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi_agent.py — Juhuo 多 Agent 编排

借鉴 Hermes 多 Agent：判断 + 记忆 + 进化 分工

Agent 角色：
- Judge Agent: 负责十维判断
- Memory Agent: 负责因果记忆存储和检索
- Evolution Agent: 负责 Self-Evolver 进化
- Coordinator: 总协调者
"""

from __future__ import annotations
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from judgment.logging_config import get_logger
log = get_logger("juhuo.multi_agent")


# Agent 角色
class AgentRole(Enum):
    JUDGE = "judge"           # 判断
    MEMORY = "memory"         # 记忆
    EVOLUTION = "evolution"   # 进化
    COORDINATOR = "coordinator"  # 协调


# 配置
AGENT_TIMEOUT = 30  # Agent 执行超时（秒）


@dataclass
class AgentMessage:
    """Agent 消息"""
    from_agent: str
    to_agent: str
    role: AgentRole
    content: Any
    timestamp: str
    reply_to: str = ""  # 回复的消息ID


@dataclass
class AgentResponse:
    """Agent 响应"""
    agent: str
    role: AgentRole
    success: bool
    result: Any
    error: str = ""
    execution_time: float = 0.0


class JuhuoAgent:
    """单个 Agent"""
    
    def __init__(self, name: str, role: AgentRole):
        self.name = name
        self.role = role
        self.inbox: List[AgentMessage] = []
        self.state: Dict = {}
    
    def receive(self, message: AgentMessage) -> None:
        """接收消息"""
        self.inbox.append(message)
        log.debug(f"{self.name} received message from {message.from_agent}")
    
    def process(self) -> Optional[AgentResponse]:
        """处理消息"""
        if not self.inbox:
            return None
        
        message = self.inbox.pop(0)
        start = datetime.now()
        
        try:
            if self.role == AgentRole.JUDGE:
                result = self._process_judgment(message)
            elif self.role == AgentRole.MEMORY:
                result = self._process_memory(message)
            elif self.role == AgentRole.EVOLUTION:
                result = self._process_evolution(message)
            else:
                result = {"status": "unknown role"}
            
            elapsed = (datetime.now() - start).total_seconds()
            return AgentResponse(
                agent=self.name,
                role=self.role,
                success=True,
                result=result,
                execution_time=elapsed
            )
        except Exception as e:
            log.error(f"{self.name} error: {e}")
            return AgentResponse(
                agent=self.name,
                role=self.role,
                success=False,
                result=None,
                error=str(e)
            )
    
    def _process_judgment(self, message: AgentMessage) -> Dict:
        """Judge Agent: 处理判断请求"""
        from judgment.judgment_engine import check10d
        return check10d(message.content.get("task", ""))
    
    def _process_memory(self, message: AgentMessage) -> Dict:
        """Memory Agent: 处理记忆请求"""
        from causal_memory.causal_memory import add_event, search_events
        
        action = message.content.get("action")
        if action == "add":
            return add_event(message.content.get("event", {}))
        elif action == "search":
            return search_events(message.content.get("query", ""))
        return {"status": "unknown action"}
    
    def _process_evolution(self, message: AgentMessage) -> Dict:
        """Evolution Agent: 处理进化请求"""
        from judgment.self_evolover import run_evolution_cycle, check_trigger
        
        action = message.content.get("action")
        if action == "check":
            return check_trigger()
        elif action == "run":
            return run_evolution_cycle()
        return {"status": "unknown action"}


class MultiAgentOrchestrator:
    """
    多 Agent 编排器
    
    协调多个 Agent 协同工作：
    1. 接收请求
    2. 分发给对应 Agent
    3. 收集响应
    4. 返回结果
    """
    
    def __init__(self):
        self.agents: Dict[str, JuhuoAgent] = {}
        self.message_log: List[AgentMessage] = []
        self._init_agents()
    
    def _init_agents(self) -> None:
        """初始化 Agent"""
        # Judge Agent
        judge = JuhuoAgent("judge", AgentRole.JUDGE)
        self.agents["judge"] = judge
        
        # Memory Agent
        memory = JuhuoAgent("memory", AgentRole.MEMORY)
        self.agents["memory"] = memory
        
        # Evolution Agent
        evolution = JuhuoAgent("evolution", AgentRole.EVOLUTION)
        self.agents["evolution"] = evolution
        
        log.info(f"Initialized {len(self.agents)} agents")
    
    def dispatch(self, role: AgentRole, content: Any) -> AgentResponse:
        """分发任务给指定角色的 Agent"""
        for agent in self.agents.values():
            if agent.role == role:
                message = AgentMessage(
                    from_agent="coordinator",
                    to_agent=agent.name,
                    role=role,
                    content=content,
                    timestamp=datetime.now().isoformat()
                )
                agent.receive(message)
                return agent.process()
        
        return AgentResponse(
            agent="coordinator",
            role=AgentRole.COORDINATOR,
            success=False,
            result=None,
            error=f"No agent found for role {role}"
        )
    
    def run_pipeline(self, task: str) -> Dict:
        """
        运行完整流水线
        
        1. Judge Agent 判断
        2. Memory Agent 存储
        3. Evolution Agent 检查是否需要进化
        """
        log.info(f"Running pipeline for: {task[:50]}...")
        
        results = {}
        
        # Step 1: 判断
        judge_resp = self.dispatch(AgentRole.JUDGE, {"task": task})
        results["judgment"] = judge_resp.result if judge_resp.success else None
        
        # Step 2: 存储记忆
        if judge_resp.success and judge_resp.result:
            self.dispatch(AgentRole.MEMORY, {
                "action": "add",
                "event": {
                    "task": task,
                    "result": results["judgment"]
                }
            })
        
        # Step 3: 检查进化
        evolution_resp = self.dispatch(AgentRole.EVOLUTION, {"action": "check"})
        results["evolution"] = evolution_resp.result if evolution_resp.success else None
        
        return results
    
    def get_status(self) -> Dict:
        """获取所有 Agent 状态"""
        return {
            "total_agents": len(self.agents),
            "agents": {
                name: {
                    "role": agent.role.value,
                    "inbox_size": len(agent.inbox),
                    "state": agent.state
                }
                for name, agent in self.agents.items()
            }
        }


# 全局编排器
_orchestrator: Optional[MultiAgentOrchestrator] = None


def get_orchestrator() -> MultiAgentOrchestrator:
    """获取全局编排器"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiAgentOrchestrator()
    return _orchestrator


def run_judgment(task: str) -> Dict:
    """运行判断（通过编排器）"""
    orch = get_orchestrator()
    return orch.dispatch(AgentRole.JUDGE, {"task": task})


if __name__ == "__main__":
    orch = MultiAgentOrchestrator()
    print(orch.get_status())
