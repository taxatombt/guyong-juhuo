"""
openspace_evolution.py —— 聚活 (guyong-juhuo) OpenSpace 三级进化整合

基于 HKUDS/OpenSpace AI Agent 自我进化引擎，针对**模拟个体数字永生**目标定制适配：

## 聚活专属进化设计（和原生 OpenSpace 的差异）：

1. **Fitness 目标对准个人一致性**：不是"任务做对了吗"，而是"这符合谷翔宇会有的思考和决策吗"
   - 哪怕决策按通用标准是错的，只要符合个人特质，进化也保留它
   - 核心是"像你"，不是"正确"

2. **因果记忆优先级高于技能进化**：个人独有的经历因果链是模拟个体的核心
   - 慢路径推理优先召回个人因果，而非通用因果
   - 保留你踩过坑、吃过亏总结出来的独一无二的经验

3. **好奇心锁定个人兴趣**：不泛泛探索，永远优先探索用户真正感兴趣的方向
   - 随机探索也限定在个人兴趣领域，不会跑偏

4. **自我模型进化优先级最高**：自我认识变化 → 整个判断系统跟着变化
   - 准确跟踪你对自己的新认识，这才是"你是谁"的核心

5. **身份锁机制**：核心身份特质（价值观/底线/根本偏好）锁死
   - 自动进化只碰知识/技能/判断规则，不碰核心身份
   - 明确说改才改，保证进化后还是你

6. **完整人生轨迹保留**：不只是技能版本，整个系统每个阶段都保留
   - 2024 年是什么世界观、2025 变了什么，全部存档
   - 后人能看到你完整的成长过程，这才是真的数字永生

## 三级进化模式保持 OpenSpace 语义：
  - CAPTURED: 捕获全新知识单元（根节点）
  - DERIVED: 从现有提炼场景专用规则 → generation + 1
  - FIX: 原地修正错误 → fix_version + 1，generation 不变
  - version DAG: 保留完整血缘，所有版本都不删除，随时回溯
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class EvolutionType(str, Enum):
    """OpenSpace 三级进化类型"""
    CAPTURED = "CAPTURED"   # 捕获全新知识单元（根节点）
    DERIVED = "DERIVED"     # 从父知识衍生特定场景规则
    FIX = "FIX"             # 就地修正错误/低质量


class KnowledgeCategory(str, Enum):
    """聚活知识分类 —— 决定进化权限"""
    CORE_IDENTITY = "CORE_IDENTITY"   # 核心身份特质（价值观/底线/根本偏好）→ 身份锁：只有明确指令才允许修改
    SELF_MODEL = "SELF_MODEL"         # 自我认识 → 高优先级自动进化
    CAUSAL_MEMORY = "CAUSAL_MEMORY"   # 个人因果记忆 → 核心优先级，保留个人经验
    JUDGMENT_RULE = "JUDGMENT_RULE"   # 判断维度规则 → 允许自动进化
    GENERAL_SKILL = "GENERAL_SKILL"   # 通用技能 → 标准OpenSpace进化
    CURIOSITY = "CURIOSITY"           # 好奇心探索 → 锁定个人兴趣领域


@dataclass
class SkillMetrics:
    """聚活知识单元质量监控指标

    适配个人模拟目标：fitness = 个人一致性分数，不是通用任务成功率
    """
    # 基础使用统计（保持 OpenSpace 兼容）
    applied_count: int = 0
    success_count: int = 0       # 这里的"成功"定义 = 符合个人决策一致性，不是任务客观成功
    failed_count: int = 0         # 这里的"失败"定义 = 偏离了个人一贯决策风格
    needs_revalidation: bool = False
    dependent_ids: List[str] = None
    last_used: str = None

    # 聚活专属：知识分类决定进化权限
    knowledge_category: KnowledgeCategory = KnowledgeCategory.GENERAL_SKILL

    # 聚活专属：个人一致性 fitness
    personal_consistency_score: float = 1.0  # 0.0 ~ 1.0，越高越符合个人特质

    # 聚活专属：是否锁定（核心身份锁）
    is_locked: bool = False

    def __post_init__(self):
        if self.dependent_ids is None:
            self.dependent_ids = []
        if self.last_used is None:
            self.last_used = datetime.now().isoformat()
        # 核心身份默认锁定
        if self.knowledge_category == KnowledgeCategory.CORE_IDENTITY:
            self.is_locked = True

    @property
    def consistency_rate(self) -> float:
        """聚活专属：个人一致性比率 — 这才是我们的 fitness 函数"""
        if self.applied_count == 0:
            return 0.0
        return self.success_count / self.applied_count

    @property
    def success_rate(self) -> float:
        """保持 OpenSpace 兼容：实际就是一致性比率"""
        return self.consistency_rate

    def mark_used(self, is_consistent: bool):
        """聚活：标记使用，参数是"是否符合个人一致性"而非任务成功"""
        self.applied_count += 1
        if is_consistent:
            self.success_count += 1
        else:
            self.failed_count += 1
        self.last_used = datetime.now().isoformat()

    def mark_needs_revalidation(self):
        self.needs_revalidation = True

    def clear_needs_revalidation(self):
        self.needs_revalidation = False

    def can_auto_evolve(self) -> bool:
        """聚活：检查该知识单元是否允许自动进化"""
        if self.is_locked:
            return False
        return True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'SkillMetrics':
        # 兼容旧数据没有知识分类
        if 'knowledge_category' not in data:
            data['knowledge_category'] = KnowledgeCategory.GENERAL_SKILL
        if 'personal_consistency_score' not in data:
            data['personal_consistency_score'] = 1.0
        if 'is_locked' not in data:
            data['is_locked'] = False
        return cls(**data)


@dataclass
class SkillLineage:
    """OpenSpace Version DAG 节点：单个技能版本谱系"""
    skill_id: str
    skill_name: str
    content_hash: str
    evolution_type: EvolutionType
    generation: int          # DERIVED 派生深度（只有派生才+1）
    fix_version: int         # FIX 修正次数（只有修正才+1）
    parent_id: Optional[str]
    child_ids: List[str]
    is_active: bool
    metrics: SkillMetrics
    created_at: str

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "content_hash": self.content_hash,
            "evolution_type": self.evolution_type.value,
            "generation": self.generation,
            "fix_version": self.fix_version,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "is_active": self.is_active,
            "metrics": self.metrics.to_dict(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SkillLineage':
        return cls(
            skill_id=data["skill_id"],
            skill_name=data["skill_name"],
            content_hash=data["content_hash"],
            evolution_type=EvolutionType(data["evolution_type"]),
            generation=data["generation"],
            fix_version=data["fix_version"],
            parent_id=data["parent_id"],
            child_ids=data["child_ids"],
            is_active=data["is_active"],
            metrics=SkillMetrics.from_dict(data["metrics"]),
            created_at=data["created_at"],
        )


def create_captured(
    skill_name: str,
    content_hash: str,
    knowledge_category: KnowledgeCategory = KnowledgeCategory.GENERAL_SKILL,
    is_locked: Optional[bool] = None,
) -> SkillLineage:
    """聚活：创建新 CAPTURED 根节点（捕获全新知识单元）

    Args:
        skill_name: 知识单元名称
        content_hash: 内容哈希
        knowledge_category: 知识分类（决定进化权限）
        is_locked: 是否锁定，CORE_IDENTITY 默认自动锁定
    """
    from openspace_utils import generate_skill_id
    skill_id = generate_skill_id(skill_name, 0, content_hash)
    metrics = SkillMetrics(knowledge_category=knowledge_category)
    if is_locked is not None:
        metrics.is_locked = is_locked
    return SkillLineage(
        skill_id=skill_id,
        skill_name=skill_name,
        content_hash=content_hash,
        evolution_type=EvolutionType.CAPTURED,
        generation=0,
        fix_version=0,
        parent_id=None,
        child_ids=[],
        is_active=True,
        metrics=metrics,
        created_at=datetime.now().isoformat(),
    )


def create_derived(parent: SkillLineage, new_skill_name: str, content_hash: str) -> SkillLineage:
    """聚活：创建 DERIVED 派生节点（从父知识衍生场景专用变种）

    - generation = parent.generation + 1
    - fix_version = 0 (派生视为新变种重新开始)
    - parent remains active
    - 知识分类继承父节点，锁定状态也继承（身份锁延续）
    """
    from openspace_utils import generate_skill_id
    skill_id = generate_skill_id(new_skill_name, 0, content_hash)
    # 继承父节点的知识分类和锁定状态
    metrics = SkillMetrics(
        knowledge_category=parent.metrics.knowledge_category,
        is_locked=parent.metrics.is_locked,
    )
    derived = SkillLineage(
        skill_id=skill_id,
        skill_name=new_skill_name,
        content_hash=content_hash,
        evolution_type=EvolutionType.DERIVED,
        generation=parent.generation + 1,
        fix_version=0,
        parent_id=parent.skill_id,
        child_ids=[],
        is_active=True,
        metrics=metrics,
        created_at=datetime.now().isoformat(),
    )
    # Add to parent's children
    if derived.skill_id not in parent.child_ids:
        parent.child_ids.append(derived.skill_id)
    return derived


def create_fix(parent: SkillLineage, content_hash: str) -> SkillLineage:
    """聚活：创建 FIX 修正节点（原地修正父节点）

    - generation = same as parent
    - fix_version = parent.fix_version + 1
    - parent becomes inactive
    - children of parent stay (they get cascade revalidation)
    - 聚活规则：如果父节点锁定（核心身份），**不允许自动FIX**，调用者检查权限
    - 知识分类和锁定状态继承父节点
    """
    # 聚活：身份锁检查 — 锁定的节点不允许自动修正
    if parent.metrics.is_locked:
        raise ValueError(f"[聚活身份锁] Cannot auto-FIX locked knowledge: {parent.skill_id} ({parent.metrics.knowledge_category})")

    from openspace_utils import generate_skill_id
    new_fix_version = parent.fix_version + 1
    skill_id = generate_skill_id(parent.skill_name, new_fix_version, content_hash)
    # 继承父节点的知识分类和锁定状态
    metrics = SkillMetrics(
        knowledge_category=parent.metrics.knowledge_category,
        is_locked=parent.metrics.is_locked,
    )
    fixed = SkillLineage(
        skill_id=skill_id,
        skill_name=parent.skill_name,
        content_hash=content_hash,
        evolution_type=EvolutionType.FIX,
        generation=parent.generation,
        fix_version=new_fix_version,
        parent_id=parent.skill_id,
        child_ids=[],
        is_active=True,
        metrics=metrics,
        created_at=datetime.now().isoformat(),
    )
    # Deactivate parent
    parent.is_active = False
    # Add to parent's children
    if fixed.skill_id not in parent.child_ids:
        parent.child_ids.append(fixed.skill_id)
    # Inherit dependencies from parent
    fixed.metrics.dependent_ids = parent.metrics.dependent_ids.copy()
    # Inherit consistency score (adjusted incrementally)
    fixed.metrics.personal_consistency_score = parent.metrics.personal_consistency_score
    return fixed


# ─── Skill DB persistence ──────────────────────────────────────────

SKILL_DB_PATH = Path(__file__).parent / "openspace_skill_db.json"


def load_skill_db(db_path: Path = SKILL_DB_PATH) -> Dict[str, SkillLineage]:
    """Load all skills from DB"""
    if not db_path.exists():
        return {}
    with open(db_path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        sid: SkillLineage.from_dict(item)
        for sid, item in (data.get("skills", {})).items()
    }


def save_skill_db(db_path: Path = SKILL_DB_PATH, db: Dict[str, SkillLineage] = None):
    """Save all skills to DB"""
    data = {
        "last_updated": datetime.now().isoformat(),
        "skills": {
            sid: node.to_dict()
            for sid, node in db.items()
        }
    }
    db_path.parent.mkdir(exist_ok=True, parents=True)
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def mark_cascade_revalidation(skill_id: str, db: Dict[str, SkillLineage]) -> None:
    """OpenSpace: Cascade mark needs revalidation for all descendants"""
    if skill_id not in db:
        return
    # Mark self
    lineage = db[skill_id]
    if not lineage.metrics.needs_revalidation:
        lineage.metrics.mark_needs_revalidation()
    # Recursively mark all children
    for child_id in lineage.child_ids:
        if child_id in db:
            mark_cascade_revalidation(child_id, db)


def format_dag_ascii(lineages: Dict[str, SkillLineage]) -> str:
    """Format Version DAG as ASCII tree"""
    # Find root nodes (no parent or parent not in db)
    roots = [l for l in lineages.values() if l.parent_id is None or l.parent_id not in lineages]
    roots.sort(key=lambda l: l.skill_id)

    if not roots:
        return "(empty DAG)"

    lines = []

    def print_node(
        node: SkillLineage,
        prefix: str = "",
        is_last: bool = True,
    ):
        status = " [A]" if node.is_active else " [X]"
        line = f"{prefix}{'└── ' if is_last else '├── '}{node.skill_id} (gen={node.generation}, v={node.fix_version}){status}"
        lines.append(line)
        children = [lineages[cid] for cid in node.child_ids if cid in lineages]
        children.sort(key=lambda l: l.skill_id)
        new_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(children):
            print_node(child, new_prefix, i == len(children) - 1)

    for i, root in enumerate(roots):
        print_node(root, "", i == len(roots) - 1)

    return "\n".join(lines)


def get_stats(lineages: Dict[str, SkillLineage]) -> dict:
    """Get DAG statistics"""
    total_nodes = len(lineages)
    active = sum(1 for n in lineages.values() if n.is_active)
    by_evolution = {}
    need_reval = []

    total_applied = 0
    total_success = 0

    for node in lineages.values():
        et = node.evolution_type.value
        by_evolution[et] = by_evolution.get(et, 0) + 1
        if node.metrics.needs_revalidation:
            need_reval.append(node.skill_id)
        total_applied += node.metrics.applied_count
        total_success += node.metrics.success_count

    avg_success = total_success / total_applied if total_applied > 0 else 0.0

    return {
        "total_nodes": total_nodes,
        "active_nodes": active,
        "by_evolution_type": by_evolution,
        "needs_revalidation": need_reval,
        "avg_success_rate": avg_success,
    }


def suggest_evolution(lineages: Dict[str, SkillLineage]) -> List[dict]:
    """聚活：基于质量指标建议进化

    聚活进化触发优先级：
    1. SELF_MODEL > CAUSAL_MEMORY > JUDGMENT_RULE > GENERAL_SKILL
    2. 锁定的 CORE_IDENTITY 永远不建议自动进化
    3. 触发条件：
       - needs_revalidation = True → 级联更新
       - applied_count >= 3 AND 一致性 < 0.5 → FIX
       - 自我模型一致性低优先级更高

    Fitness 定义：成功 = 符合个人决策一致性，不是任务客观成功
    """
    suggestions = []

    for node in lineages.values():
        if not node.is_active:
            continue

        metrics = node.metrics

        # 聚活：锁定的核心身份永远不建议自动进化
        if metrics.is_locked:
            continue

        if metrics.needs_revalidation:
            suggestions.append({
                "skill_id": node.skill_id,
                "skill_name": node.skill_name,
                "knowledge_category": metrics.knowledge_category,
                "evolution_type": EvolutionType.FIX,
                "reason": "标记为需要重新验证（级联更新）",
                "current_consistency": metrics.consistency_rate,
                "depends_on_changed": True,
                "generation": node.generation,
                "fix_version": node.fix_version,
                "priority": _get_priority(metrics.knowledge_category),
            })
            continue

        if metrics.applied_count >= 3 and metrics.consistency_rate < 0.5:
            suggestions.append({
                "skill_id": node.skill_id,
                "skill_name": node.skill_name,
                "knowledge_category": metrics.knowledge_category,
                "evolution_type": EvolutionType.FIX,
                "reason": f"低个人一致性 ({metrics.consistency_rate:.1%}), {metrics.failed_count}/{metrics.applied_count} 次偏离个人风格",
                "current_consistency": metrics.consistency_rate,
                "depends_on_changed": False,
                "generation": node.generation,
                "fix_version": node.fix_version,
                "priority": _get_priority(metrics.knowledge_category),
            })

    # 聚活：按优先级排序 → 自我模型先处理
    suggestions.sort(key=lambda x: x["priority"], reverse=True)
    return suggestions


def _get_priority(category: KnowledgeCategory) -> int:
    """聚活：进化建议优先级，数字越大越优先"""
    PRIORITY = {
        KnowledgeCategory.SELF_MODEL: 100,
        KnowledgeCategory.CAUSAL_MEMORY: 90,
        KnowledgeCategory.CURIOSITY: 80,
        KnowledgeCategory.JUDGMENT_RULE: 70,
        KnowledgeCategory.GENERAL_SKILL: 60,
        KnowledgeCategory.CORE_IDENTITY: 0,  # 锁定不进化
    }
    return PRIORITY.get(category, 50)


def generate_evolution_report(lineages: Dict[str, SkillLineage]) -> str:
    """Generate human-readable evolution report"""
    stats = get_stats(lineages)
    suggestions = suggest_evolution(lineages)

    lines = ["# OpenSpace 进化报告", ""]
    lines.append(f"总计技能节点: {stats['total_nodes']}")
    lines.append(f"激活节点: {stats['active_nodes']}")
    lines.append(f"平均成功率: {stats['avg_success_rate']:.1%}")
    if stats["by_evolution_type"]:
        lines.append("按进化类型:")
        for et, count in stats["by_evolution_type"].items():
            lines.append(f"  {et}: {count}")
    lines.append("")

    if suggestions:
        lines.append("## 待进化技能")
        lines.append("")
        for s in suggestions:
            et = s["evolution_type"].value
            lines.append(f"### {s['skill_id']} [{et}]")
            lines.append(f"  原因: {s['reason']}")
            lines.append(f"  当前成功率: {s['current_success_rate']:.1%}")
            if s["depends_on_changed"]:
                lines.append("  ⚠️ 依赖的基础技能已改变，需要完全重新验证")
            lines.append("")
    else:
        lines.append("没有待进化技能，当前状态良好。")
        lines.append("")

    lines.append("## Version DAG 结构")
    lines.append("")
    lines.append("```")
    lines.append(format_dag_ascii(lineages))
    lines.append("```")

    return "\n".join(lines)


# ─── guyong-juhuo integration ───────────────────────────────────────

def record_skill_execution(
    skill_id: str,
    success: bool,
    db_path: Path = SKILL_DB_PATH
) -> Optional[SkillLineage]:
    """Record skill execution result for metrics"""
    db = load_skill_db(db_path)
    if skill_id not in db:
        return None
    node = db[skill_id]
    node.metrics.mark_used(success)
    save_skill_db(db_path, db)
    return node


def create_and_save_captured(
    skill_name: str,
    content: str,
    db_path: Path = SKILL_DB_PATH
) -> SkillLineage:
    """Capture a new root skill and save to DB"""
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    captured = create_captured(skill_name, content_hash)
    db = load_skill_db(db_path)
    db[captured.skill_id] = captured
    save_skill_db(db_path, db)
    return captured


def create_and_save_derived(
    parent_id: str,
    new_skill_name: str,
    content: str,
    db_path: Path = SKILL_DB_PATH
) -> Optional[SkillLineage]:
    """Derive a new skill from parent and save to DB"""
    db = load_skill_db(db_path)
    if parent_id not in db:
        return None
    parent = db[parent_id]
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    derived = create_derived(parent, new_skill_name, content_hash)
    db[derived.skill_id] = derived
    # Parent is modified (added child)
    db[parent_id] = parent
    save_skill_db(db_path, db)
    return derived


def create_and_save_fix(
    parent_id: str,
    content: str,
    db_path: Path = SKILL_DB_PATH
) -> Optional[SkillLineage]:
    """Create a FIX for existing skill and save to DB

    - parent deactivated
    - cascade revalidation triggered for all descendants
    """
    db = load_skill_db(db_path)
    if parent_id not in db:
        return None
    parent = db[parent_id]
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    fixed = create_fix(parent, content_hash)
    db[fixed.skill_id] = fixed
    # Parent is modified (deactivated + added child)
    db[parent_id] = parent
    # Trigger cascade revalidation
    mark_cascade_revalidation(fixed.skill_id, db)
    save_skill_db(db_path, db)
    return fixed


# ─── discovery from SKILL directories ──────────────────────────────

def discover_skills_from_dirs(
    base_dirs: List[Path],
    db_path: Path = SKILL_DB_PATH
) -> List[Tuple[Path, SkillLineage]]:
    """
    Discover skills from directories with SKILL.md:
    - Look for .skill_id sidecar
    - Create/Update lineage entry
    """
    from .openspace_utils import get_or_generate_skill_id

    discovered = []
    db = load_skill_db(db_path)
    modified = False

    for base_dir in base_dirs:
        if not base_dir.exists():
            continue
        for skill_dir in base_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            # Get or generate skill_id
            skill_name = skill_dir.name
            skill_id = get_or_generate_skill_id(skill_dir, skill_name)
            content = skill_md.read_text(encoding="utf-8")

            if skill_id in db:
                # Already exists, update content hash if changed
                existing = db[skill_id]
                new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
                if new_hash != existing.content_hash:
                    # Content changed → this is a FIX
                    # FIX keeps generation, increments fix_version
                    content_hash = new_hash
                    new_fix_version = existing.fix_version + 1
                    from openspace_utils import generate_skill_id
                    new_skill_id = generate_skill_id(skill_name, new_fix_version, content_hash)
                    fixed = SkillLineage(
                        skill_id=new_skill_id,
                        skill_name=skill_name,
                        content_hash=content_hash,
                        evolution_type=EvolutionType.FIX,
                        generation=existing.generation,
                        fix_version=new_fix_version,
                        parent_id=existing.skill_id,
                        child_ids=[],
                        is_active=True,
                        metrics=SkillMetrics(),
                        created_at=datetime.now().isoformat(),
                    )
                    existing.is_active = False
                    if fixed.skill_id not in existing.child_ids:
                        existing.child_ids.append(fixed.skill_id)
                    db[new_skill_id] = fixed
                    db[existing.skill_id] = existing
                    mark_cascade_revalidation(new_skill_id, db)
                    modified = True
                    discovered.append((skill_dir, fixed))
                else:
                    discovered.append((skill_dir, existing))
            else:
                # New captured skill
                parts = skill_id.split("__")
                if len(parts) >= 2:
                    # Parse from existing .skill_id
                    import re
                    match = re.match(r"(.+)__v(\d+)_([0-9a-f]{8})", skill_id)
                    if match:
                        fix_v = int(match.group(2))
                        content_hash = match.group(3)
                        captured = SkillLineage(
                            skill_id=skill_id,
                            skill_name=skill_name,
                            content_hash=content_hash,
                            evolution_type=EvolutionType.CAPTURED,
                            generation=0,
                            fix_version=fix_v,
                            parent_id=None,
                            child_ids=[],
                            is_active=True,
                            metrics=SkillMetrics(),
                            created_at=datetime.now().isoformat(),
                        )
                        db[skill_id] = captured
                        modified = True
                        discovered.append((skill_dir, captured))
                else:
                    # New captured
                    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
                    captured = create_captured(skill_name, content_hash)
                    # write sidecar if not exists
                    if not (skill_dir / ".skill_id").exists():
                        from .openspace_utils import write_skill_id
                        write_skill_id(skill_dir, captured.skill_id)
                    db[captured.skill_id] = captured
                    modified = True
                    discovered.append((skill_dir, captured))

    if modified:
        save_skill_db(db_path, db)

    return discovered


# ─── compatibility with existing profile evolution ─────────────────

def migrate_from_profile_evolution(old_db_path: Path):
    """Migrate existing profile evolution data to OpenSpace format"""
    if not old_db_path.exists():
        return 0

    with open(old_db_path, encoding="utf-8") as f:
        old_data = json.load(f)

    migrated = 0
    db = load_skill_db()

    for profile_name, profile_data in old_data.get("profiles", {}).items():
        for blind_spot_id, bs in profile_data.get("blind_spots", {}).items():
            # Convert each blind spot to a FIX suggestion
            skill_name = f"{profile_name}-blind-{blind_spot_id}"
            content = json.dumps(bs, ensure_ascii=False, indent=2)
            if skill_name not in [n.skill_name for n in db.values()]:
                captured = create_and_save_captured(skill_name, content)
                migrated += 1

    if migrated > 0:
        save_skill_db(SKILL_DB_PATH, db)

    return migrated


# ── 聚活全系统版本快照 — 保留完整人生轨迹 ─────────────────────────────

def save_system_snapshot(lineages: Dict[str, SkillLineage], snapshot_dir: str = "snapshots") -> str:
    """聚活：保存全系统版本快照 —— 保留整个人生轨迹

    每次重大进化后保存快照，后人可以回溯任意时间点的完整世界观
    文件名格式: snapshots/snapshot-YYYYMMDD-HHMMSS.json
    """
    snapshot_path = Path(snapshot_dir)
    snapshot_path.mkdir(exist_ok=True, parents=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"snapshot-{timestamp}.json"
    filepath = snapshot_path / filename

    snapshot_data = {
        "timestamp": datetime.now().isoformat(),
        "total_nodes": len(lineages),
        "active_nodes": sum(1 for n in lineages.values() if n.is_active),
        "by_category": {
            cat.value: sum(1 for n in lineages.values()
                          if n.metrics.knowledge_category == cat)
            for cat in KnowledgeCategory
        },
        "avg_consistency": sum(n.metrics.consistency_rate for n in lineages.values() if n.is_active) / max(1, sum(1 for n in lineages.values() if n.is_active)),
        "lineages": {
            sid: node.to_dict() for sid, node in lineages.items()
        },
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, ensure_ascii=False, indent=2)

    return str(filepath)


def list_system_snapshots(snapshot_dir: str = "snapshots") -> List[str]:
    """聚活：列出所有全系统快照，按时间排序"""
    snapshot_path = Path(snapshot_dir)
    if not snapshot_path.exists():
        return []
    snapshots = list(snapshot_path.glob("snapshot-*.json"))
    snapshots.sort()
    return [str(p) for p in snapshots]


def load_system_snapshot(filepath: str) -> Dict[str, SkillLineage]:
    """聚活：从快照加载全系统版本"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    lineages = {}
    for sid, node_dict in data["lineages"].items():
        # 兼容旧数据
        if isinstance(node_dict["evolution_type"], str):
            node_dict["evolution_type"] = EvolutionType(node_dict["evolution_type"])
        lineages[sid] = SkillLineage.from_dict(node_dict)

    return lineages


def test_version_dag_semantics() -> bool:
    """测试 Version DAG 语义是否正确"""
    # 创建根节点
    root = create_captured(
        skill_name="test-root",
        content="root content",
        category=KnowledgeCategory.CORE_IDENTITY,
    )
    assert root.version_generation == 0
    assert root.version_fix == 0
    assert root.evolution_type == EvolutionType.CAPTURED

    # 衍生一个版本 → generation+1, fix保持0
    derived = create_derived(
        parent_skill_id=root.skill_id,
        skill_name="test-derived",
        content="derived content",
        category=KnowledgeCategory.JUDGMENT_RULE,
    )
    assert derived.version_generation == 1
    assert derived.version_fix == 0
    assert derived.evolution_type == EvolutionType.DERIVED

    # FIX这个衍生 → generation不变, fix+1
    fixed = create_fix(
        skill_id=derived.skill_id,
        new_content="fixed derived content",
    )
    assert fixed.version_generation == 1
    assert fixed.version_fix == 1
    assert fixed.evolution_type == EvolutionType.FIX

    print("✓ Version DAG semantics OK")
    print(f"  CAPTURED: gen={root.version_generation}, fix={root.version_fix}")
    print(f"  DERIVED:  gen={derived.version_generation}, fix={derived.version_fix}")
    print(f"  FIX:     gen={fixed.version_generation}, fix={fixed.version_fix}")
    return True
