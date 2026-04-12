"""
Hermes-Agent 自我进化能力落地到聚活(JuHuo)

基于 NousResearch/Hermes-Agent 核心设计：
- 闭环学习循环：对话 → 执行 → 记录 → 改进
- 自动技能创建和自改进
- 全文搜索发现历史技能

Usage:
    from hermes_evolution import HermesEvolution, SkillStorage, TrajectoryRecorder
    
    # Initialize
    evolution = HermesEvolution()
    
    # Search for relevant skills
    skills = evolution.search_skills("github pull request")
    
    # Record task execution
    traj_id = evolution.start_task("Create pull request for feature", skill_name="github-pr-workflow")
    evolution.record_step("checkout main", ..., ..., success=True)
    evolution.end_task(success=True)
    
    # Auto-extract new skill from successful task
    new_skill = evolution.extract_new_skill_from_trajectory(traj_id)
    
    # Improve skill from failure
    improvement = evolution.improve_skill_from_failure("skill-name", traj_id)
"""

from .hermes_evolution import HermesEvolution
from .skill_storage import SkillStorage
from .trajectory_recorder import TrajectoryRecorder

__all__ = [
    "HermesEvolution",
    "SkillStorage",
    "TrajectoryRecorder",
]
