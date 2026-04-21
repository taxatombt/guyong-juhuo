"""
context.py — Judgment Pipeline 上下文对象

所有注入器共享的上下文容器。
避免在 router.py 里用大量局部变量传递状态。
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class JudgmentContext:
    """判断 pipeline 的上下文容器"""
    
    # 原始输入
    task_text: str
    original_task: str
    
    # 可选配置
    agent_profile: Optional[Dict] = None
    complexity: str = "auto"
    emotion_state: Optional[Dict] = None
    user_id: str = "default"
    
    # 注入器填充的上下文
    bio_context: str = ""           # 途径1：生平事实
    history_context: str = ""       # 途径2：历史相似判断
    causal_context: str = ""        # 途径3：因果记忆摘要
    emotion_hint: str = ""          # 情绪调制提示
    hook_context: str = ""          # Hook召回上下文
    
    # 内部状态（injector之间共享）
    emotion_detection: Any = None   # 情绪检测结果
    emotion_modulation: Any = None  # PAD调制
    prior_adjustments: Dict = field(default_factory=dict)  # 动态权重
    causal_result: Dict = field(default_factory=dict)      # 因果召回结果
    bio_facts: List[Dict] = field(default_factory=list)   # 抽取的生平事实
    
    # 元数据
    complexity_detected: Optional[str] = None
    skipped_dimensions: List[str] = field(default_factory=list)
    
    def merge_prompt_context(self) -> str:
        """把所有上下文合并到 prompt 中"""
        parts = [self.task_text]
        
        if self.emotion_hint:
            parts.append(f"\n{self.emotion_hint}")
        if self.hook_context:
            parts.append(f"\n{self.hook_context}")
        if self.causal_context:
            parts.append(f"\n{self.causal_context}")
        if self.history_context:
            parts.append(f"\n{self.history_context}")
        if self.bio_context:
            parts.append(f"\n{self.bio_context}")
            
        return "\n".join(parts)
