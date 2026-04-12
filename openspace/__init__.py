"""
openspace —— 聚活 OpenSpace 三级自进化引擎

基于 HKUDS/OpenSpace AI Agent 自我进化引擎，针对**模拟个体数字永生**定制适配：

## 聚活专属进化设计：
1. **Fitness 目标对准个人一致性**：不是"任务做对了吗"，而是"这符合谷翔宇会有的思考和决策吗"
   - 哪怕决策按通用标准是错的，只要符合个人特质，进化也保留它
2. **因果记忆优先级高于技能进化**：个人独有的经历因果链是模拟个体的核心
   - 慢路径推理优先召回个人因果，而非通用因果
3. **好奇心锁定个人兴趣**：不泛泛探索，永远优先探索用户真正感兴趣的方向
4. **自我模型进化优先级最高**：自我认识变化 → 整个判断系统跟着变化
5. **身份锁机制**：核心身份特质（价值观/底线/根本偏好）锁死
   - 自动进化只碰知识/技能/判断规则，不碰核心身份
6. **完整人生轨迹保留**：不只是技能版本，整个系统每个阶段都保留
   - 每次重大进化自动快照，后人能回溯完整成长过程

## 三级进化模式保持 OpenSpace 语义：
  CAPTURED — 捕获全新知识单元（根节点，gen=0）
  DERIVED  — 从父知识衍生场景专用变种（gen+1，v=0）
  FIX      — 就地修正错误（gen不变，v+1）

双维度版本语义：
  generation    → DERIVED 派生深度，仅派生递增
  fix_version   → FIX 修正次数，仅修正递增
  skill_id 格式 → {name}__v{fix_version}_{hash}
"""

import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openspace_evolution import (
    EvolutionType,
    KnowledgeCategory,
    SkillLineage,
    SkillMetrics,
    create_captured,
    create_derived,
    create_fix,
    load_skill_db,
    save_skill_db,
    mark_cascade_revalidation,
    format_dag_ascii,
    get_stats,
    suggest_evolution,
    save_system_snapshot,
    list_system_snapshots,
    load_system_snapshot,
    create_and_save_captured,
    create_and_save_derived,
    create_and_save_fix,
    discover_skills_from_dirs,
    migrate_from_profile_evolution,
    test_version_dag_semantics,
    SKILL_DB_PATH,
)

from openspace_utils import (
    generate_skill_id,
    read_skill_id,
    write_skill_id,
    get_or_generate_skill_id,
    parse_skill_id,
    PriorityLevel,
    PriorityMessage,
    ConversationFormatter,
    PatchType,
    format_action_log,
    detect_patch_type,
    simple_fuzzy_search,
    find_best_match,
    get_implementation_summary,
)

from execution_analyzer import (
    ExecutionAnalyzer,
    ExecutionRecord,
)

from .autonomous_skill_detector import (
    OpportunityScore,
    UsageStats,
    AutonomousSkillTracker,
    score_skill_opportunity,
    trigger_autonomous_improvement,
    format_opportunity_suggestion,
)

__all__ = [
    # Types
    'EvolutionType',
    'KnowledgeCategory',      # 聚活：知识分类（进化权限控制）
    'SkillLineage',
    'SkillMetrics',
    # Creation
    'create_captured',
    'create_derived',
    'create_fix',
    'create_and_save_captured',
    'create_and_save_derived',
    'create_and_save_fix',
    # DB
    'load_skill_db',
    'save_skill_db',
    'mark_cascade_revalidation',
    'print_ascii_dag',
    'get_stats',
    'suggest_evolution',
    # 聚活：全系统快照（保留人生轨迹）
    'save_system_snapshot',
    'list_system_snapshots',
    'load_system_snapshot',
    'generate_evolution_report',
    'record_skill_execution',
    'discover_skills_from_dirs',
    'migrate_from_profile_evolution',
    # Utils
    'generate_skill_id',
    'parse_skill_id',
    'read_skill_id',
    'write_skill_id',
    'get_or_generate_skill_id',
    'PriorityLevel',
    'PriorityMessage',
    'ConversationFormatter',
    'format_action_log',
    'PatchType',
    'detect_patch_type',
    'simple_fuzzy_search',
    'find_best_match',
    'get_implementation_summary',
    # Analysis
    'ExecutionAnalyzer',
    'ExecutionRecord',
    # Autonomous skill creation (from Hermes)
    'OpportunityScore',
    'UsageStats',
    'AutonomousSkillTracker',
    'score_skill_opportunity',
    'trigger_autonomous_improvement',
    'format_opportunity_suggestion',
    # Paths
    'SKILL_DB_PATH',
]
