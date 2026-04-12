"""
Hermes-Agent 主动闭环学习 — RL from Experience 核心实现

结合聚活个人数字分身目标：
- Reward signal = 个人一致性得分（符合用户就是正奖励）
- Trajectory = 用户对话 → 系统决策 → 用户反馈 → 奖励
- 每日自动从收集的经验生成进化建议 → OpenSpace 三级进化整合
"""

import json
import math
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sys
from pathlib import Path
# Add parent directory to path for imports
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

# Direct import from the files since they are at package root
from openspace_evolution import (
    load_skill_db,
    record_skill_execution,
)
from execution_analyzer import ExecutionAnalyzer
from feedback_system.feedback_system import Feedback
# CausalMemory module doesn't have a class CausalMemory, use module-level functions
from causal_memory import find_similar_events


@dataclass
class Experience:
    """单次执行经验 — 对应 RL 中的一个 step"""
    experience_id: str
    timestamp: str
    input_text: str
    decision_output: Dict[str, Any]
    user_feedback: Optional[str]
    consistency_score: float  # 个人一致性得分（reward）
    skill_id: Optional[str]   # 使用的技能
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experience":
        return cls(**data)


@dataclass
class Trajectory:
    """连续经验轨迹 — 对应 RL 中的一个 episode"""
    trajectory_id: str
    session_id: str
    start_time: str
    end_time: Optional[str]
    experiences: List[Experience]
    total_reward: float
    avg_consistency: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trajectory":
        return cls(**data)
    
    def add_experience(self, exp: Experience) -> None:
        self.experiences.append(exp)
        self.total_reward = sum(e.consistency_score for e in self.experiences)
        self.avg_consistency = self.total_reward / len(self.experiences)
        self.end_time = datetime.now().isoformat()


class ExperienceCollector:
    """经验收集器 — 主动收集对话轨迹用于后续 RL 训练"""
    
    def __init__(self, data_dir: Path = None):
        from . import get_juhuo_root
        self.data_dir = data_dir or get_juhuo_root() / "data" / "hermes_experience"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.current_trajectory: Optional[Trajectory] = None
    
    def start_trajectory(self, session_id: str) -> Trajectory:
        """开始新的轨迹收集"""
        trajectory_id = f"traj_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session_id[:8]}"
        traj = Trajectory(
            trajectory_id=trajectory_id,
            session_id=session_id,
            start_time=datetime.now().isoformat(),
            end_time=None,
            experiences=[],
            total_reward=0.0,
            avg_consistency=0.0
        )
        self.current_trajectory = traj
        return traj
    
    def collect_experience(
        self,
        input_text: str,
        decision_output: Dict[str, Any],
        consistency_score: float,
        skill_id: Optional[str] = None,
        user_feedback: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Experience:
        """收集单次经验"""
        if self.current_trajectory is None:
            self.start_trajectory("default")
        
        exp_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        exp = Experience(
            experience_id=exp_id,
            timestamp=datetime.now().isoformat(),
            input_text=input_text,
            decision_output=decision_output,
            user_feedback=user_feedback,
            consistency_score=consistency_score,
            skill_id=skill_id,
            metadata=metadata or {}
        )
        
        self.current_trajectory.add_experience(exp)
        return exp
    
    def end_trajectory(self) -> Optional[Trajectory]:
        """结束当前轨迹并保存"""
        if self.current_trajectory is None:
            return None
        
        traj = self.current_trajectory
        self._save_trajectory(traj)
        self.current_trajectory = None
        return traj
    
    def _save_trajectory(self, traj: Trajectory) -> None:
        """保存轨迹到文件"""
        file_path = self.data_dir / f"{traj.trajectory_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(traj.to_dict(), f, ensure_ascii=False, indent=2)
    
    def load_all_trajectories(self) -> List[Trajectory]:
        """加载所有收集的轨迹"""
        trajectories = []
        for file in self.data_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    traj = Trajectory.from_dict(data)
                    trajectories.append(traj)
            except Exception as e:
                continue
        return trajectories
    
    def get_trajectories_since(self, days: int) -> List[Trajectory]:
        """获取最近 N 天内的轨迹"""
        cutoff = datetime.now() - timedelta(days=days)
        all_traj = self.load_all_trajectories()
        result = []
        for traj in all_traj:
            start_dt = datetime.fromisoformat(traj.start_time)
            if start_dt >= cutoff:
                result.append(traj)
        return result


class RewardCalculator:
    """奖励计算器 — 基于聚活个人一致性设计 reward signal
    
    核心设计（适配个人数字分身）：
    - 用户明确认可 → +1.0 奖励
    - 用户明确否定 → -1.0 奖励
    - 沉默/无反馈 → 用个人一致性模型预测 reward
    - 一致性越高 → reward 越高（符合用户就是成功）
    """
    
    def __init__(self):
        pass
    
    def calculate_reward(
        self,
        experience: Experience,
        feedback: Optional[Feedback] = None,
        causal_memory = None
    ) -> float:
        """计算经验的奖励"""
        
        # 情况1：用户明确反馈 → 直接给出奖励
        if feedback is not None:
            if feedback.is_approved:
                return 1.0
            else:
                return -1.0
        
        # 情况2：有一致性预计算得分 → 直接使用归一化到 [-1, 1]
        # 原始得分 [0, 1] → 映射到 [-1, 1]: score * 2 - 1
        if experience.consistency_score >= 0:
            return experience.consistency_score * 2 - 1
        
        # 情况3：预测一致性奖励
        # 如果因果记忆中存在类似输入输出且用户接受 → 正奖励
        if causal_memory is not None:
            similar = find_similar_events(experience.input_text)
            if similar:
                # 类似经验得到正反馈 → 预测正奖励
                avg_accept = sum(1 for s in similar if s.get("accepted", False)) / len(similar)
                return avg_accept * 2 - 1
        
        # 默认：中性奖励
        return 0.0
    
    @staticmethod
    def cumulative_reward(rewards: List[float], gamma: float = 0.99) -> List[float]:
        """计算累积奖励（折扣回报）"""
        discounted = []
        cumulative = 0.0
        for reward in reversed(rewards):
            cumulative = reward + gamma * cumulative
            discounted.insert(0, cumulative)
        return discounted


class ActiveLearningLoop:
    """Hermes 主动闭环学习主循环
    
    整合：
    1. 经验收集 → 2. 奖励计算 → 3. 进化建议 → 4. OpenSpace 进化
    """
    
    def __init__(
        self,
        collector: Optional[ExperienceCollector] = None,
        reward_calc: Optional[RewardCalculator] = None
    ):
        self.collector = collector or ExperienceCollector()
        self.reward_calc = reward_calc or RewardCalculator()
        self._cache_stats = None
    
    def collect_current_session(self, session_id: str) -> None:
        """开始收集当前会话"""
        self.collector.start_trajectory(session_id)
    
    def record_step(
        self,
        input_text: str,
        decision: Dict[str, Any],
        consistency_score: float,
        skill_id: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> Experience:
        """记录一步经验"""
        exp = self.collector.collect_experience(
            input_text=input_text,
            decision_output=decision,
            consistency_score=consistency_score,
            skill_id=skill_id,
            user_feedback=feedback
        )
        
        # 如果有明确反馈，立即记录到 OpenSpace
        if feedback is not None and skill_id is not None:
            success = consistency_score > 0.5  # 一致性 > 0.5 算成功
            record_skill_execution(skill_id, success=success)
        
        return exp
    
    def end_session(self) -> Optional[Trajectory]:
        """结束当前会话收集"""
        return self.collector.end_trajectory()
    
    def daily_evolution(
        self,
        days: int = 1,
        min_experiences: int = 5
    ) -> Dict[str, Any]:
        """每日自动进化：分析最近 N 天经验，生成进化建议
        
        对齐 OpenSpace 三级进化框架：
        - 低成功率技能 → 自动建议 FIX
        - 特定场景高频 → 自动建议 DERIVED 衍生变种
        - 全新领域经验 → 建议 CAPTURE 新技能
        """
        trajectories = self.collector.get_trajectories_since(days)
        
        total_experiences = sum(len(t.experiences) for t in trajectories)
        if total_experiences < min_experiences:
            return {
                "status": "skipped",
                "reason": f"insufficient experiences: {total_experiences} < {min_experiences}",
                "suggestions": []
            }
        
        # 使用 OpenSpace ExecutionAnalyzer 分析
        analyzer = ExecutionAnalyzer()
        suggestions = analyzer.generate_evolution_suggestions()
        
        # 按 reward 排序，优先进化低 reward 技能
        suggestions.sort(key=lambda s: s.get("avg_reward", 0))
        
        return {
            "status": "completed",
            "trajectories_analyzed": len(trajectories),
            "total_experiences": total_experiences,
            "suggestions": suggestions,
            "generated_at": datetime.now().isoformat()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取收集的经验统计"""
        if self._cache_stats is not None:
            return self._cache_stats
        
        trajectories = self.collector.load_all_trajectories()
        total_traj = len(trajectories)
        total_exp = sum(len(t.experiences) for t in trajectories)
        avg_reward = (
            sum(t.avg_consistency for t in trajectories) / total_traj
            if total_traj > 0 else 0
        )
        
        # 按奖励分布统计
        positive = sum(1 for t in trajectories if t.avg_consistency > 0.5)
        negative = sum(1 for t in trajectories if t.avg_consistency < 0.2)
        
        self._cache_stats = {
            "total_trajectories": total_traj,
            "total_experiences": total_exp,
            "average_consistency": avg_reward,
            "positive_trajectories": positive,
            "negative_trajectories": negative,
        }
        return self._cache_stats
    
    def generate_rl_training_config(self) -> Dict[str, Any]:
        """生成 RL 训练配置（用于可选大模型微调）
        
        当有大模型可用时，可以导出轨迹用于策略微调
        聚活核心不依赖，纯规则推理也能工作
        """
        trajectories = self.collector.load_all_trajectories()
        
        # 格式化为对话样本
        training_samples = []
        for traj in trajectories:
            for exp in traj.experiences:
                if exp.consistency_score >= 0.5:  # 只保留高一致性样本
                    training_samples.append({
                        "input": exp.input_text,
                        "output": exp.decision_output.get("conclusion", ""),
                        "reward": exp.consistency_score,
                        "timestamp": exp.timestamp
                    })
        
        # 保存训练数据
        data_dir = self.collector.data_dir.parent / "rl_training"
        data_dir.mkdir(exist_ok=True)
        output_path = data_dir / f"training_data_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        with open(output_path, "w", encoding="utf-8") as f:
            for sample in training_samples:
                json.dump(sample, f, ensure_ascii=False)
                f.write("\n")
        
        return {
            "status": "generated",
            "num_samples": len(training_samples),
            "output_path": str(output_path),
            "config": {
                "reward_signal": "personal_consistency",
                "filter_threshold": 0.5,
                "total_accepted": len(training_samples)
            }
        }
