"""
openspace —— HKUDS/OpenSpace AI Agent 自我进化引擎整合

三级进化模式：
  CAPTURED — 捕获全新技能（根节点，gen=0）
  DERIVED  — 从父技能衍生变种（gen+1，v=0）
  FIX      — 就地修正错误（gen不变，v+1）

双维度版本语义：
  generation    → DERIVED 派生深度，仅派生递增
  fix_version   → FIX 修正次数，仅修正递增
  skill_id 格式 → {name}__v{fix_version}_{hash}

核心入口：
  from guyong-juhuo.openspace import (
      # Types
      EvolutionType,
      SkillLineage,
      SkillMetrics,
      # Creation
      create_captured,
      create_derived,
      create_fix,
      create_and_save_captured,
      create_and_save_derived,
      create_and_save_fix,
      # DB
      load_skill_db,
      save_skill_db,
      mark_cascade_revalidation,
      format_dag_ascii,
      get_stats,
      suggest_evolution,
      generate_evolution_report,
      record_skill_execution,
      # Utils
      generate_skill_id,
      parse_skill_id,
      read_skill_id,
      write_skill_id,
      get_or_generate_skill_id,
      PriorityLevel,
      ConversationFormatter,
      format_action_log,
      detect_patch_type,
      simple_fuzzy_search,
      find_best_match,
      # Analysis
      ExecutionAnalyzer,
  )
"""

from ..openspace_evolution import (
    EvolutionType,
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
    generate_evolution_report,
    record_skill_execution,
    create_and_save_captured,
    create_and_save_derived,
    create_and_save_fix,
    discover_skills_from_dirs,
    migrate_from_profile_evolution,
    SKILL_DB_PATH,
)

from ..openspace_utils import (
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

from ..execution_analyzer import (
    ExecutionAnalyzer,
    ExecutionRecord,
)

__all__ = [
    # Types
    'EvolutionType',
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
    'format_dag_ascii',
    'get_stats',
    'suggest_evolution',
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
    # Paths
    'SKILL_DB_PATH',
]
