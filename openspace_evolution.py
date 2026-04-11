"""
openspace_evolution.py —— guyong-juhuo OpenSpace 三级进化整合

基于 HKUDS/OpenSpace AI Agent 自我进化引擎，完整落地到 juhuo 系统：

1. 三级进化模式：CAPTURED/DERIVED/FIX
2. Version DAG 双维度版本语义
3. 质量监控 + 级联重新验证
4. 从执行日志自动生成进化建议

OpenSpace 核心设计：
  - generation: 仅在 DERIVED 递增 → 记录派生深度
  - fix_version: 仅在 FIX 递增 → 记录修正次数
  - skill_id: {name}__v{fix_version}_{hash}
  - .skill_id sidecar: 持久化 ID，排除 diff
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
    CAPTURED = "CAPTURED"   # 捕获全新技能（根节点）
    DERIVED = "DERIVED"     # 从父技能衍生特定场景
    FIX = "FIX"             # 就地修正错误/低质量


@dataclass
class SkillMetrics:
    """OpenSpace 技能质量监控指标"""
    applied_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    needs_revalidation: bool = False
    dependent_ids: List[str] = None
    last_used: str = None

    def __post_init__(self):
        if self.dependent_ids is None:
            self.dependent_ids = []
        if self.last_used is None:
            self.last_used = datetime.now().isoformat()

    @property
    def success_rate(self) -> float:
        if self.applied_count == 0:
            return 0.0
        return self.success_count / self.applied_count

    def mark_used(self, success: bool):
        self.applied_count += 1
        if success:
            self.success_count += 1
        else:
            self.failed_count += 1
        self.last_used = datetime.now().isoformat()

    def mark_needs_revalidation(self):
        self.needs_revalidation = True

    def clear_needs_revalidation(self):
        self.needs_revalidation = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'SkillMetrics':
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


def create_captured(skill_name: str, content_hash: str) -> SkillLineage:
    """OpenSpace: 创建新 CAPTURED 根节点（全新技能捕获）"""
    from openspace_utils import generate_skill_id
    skill_id = generate_skill_id(skill_name, 0, content_hash)
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
        metrics=SkillMetrics(),
        created_at=datetime.now().isoformat(),
    )


def create_derived(parent: SkillLineage, new_skill_name: str, content_hash: str) -> SkillLineage:
    """OpenSpace: 创建 DERIVED 派生节点（从父衍生新变种）

    - generation = parent.generation + 1
    - fix_version = 0 (派生视为新变种重新开始)
    - parent remains active
    """
    from openspace_utils import generate_skill_id
    skill_id = generate_skill_id(new_skill_name, 0, content_hash)
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
        metrics=SkillMetrics(),
        created_at=datetime.now().isoformat(),
    )
    # Add to parent's children
    if derived.skill_id not in parent.child_ids:
        parent.child_ids.append(derived.skill_id)
    return derived


def create_fix(parent: SkillLineage, content_hash: str) -> SkillLineage:
    """OpenSpace: 创建 FIX 修正节点（原地修正父节点）

    - generation = same as parent
    - fix_version = parent.fix_version + 1
    - parent becomes inactive
    - children of parent stay (they get cascade revalidation)
    """
    from openspace_utils import generate_skill_id
    new_fix_version = parent.fix_version + 1
    skill_id = generate_skill_id(parent.skill_name, new_fix_version, content_hash)
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
        metrics=SkillMetrics(),
        created_at=datetime.now().isoformat(),
    )
    # Deactivate parent
    parent.is_active = False
    # Add to parent's children
    if fixed.skill_id not in parent.child_ids:
        parent.child_ids.append(fixed.skill_id)
    # Inherit dependencies from parent
    fixed.metrics.dependent_ids = parent.metrics.dependent_ids.copy()
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
    """OpenSpace: Suggest evolution based on quality metrics

    Triggers:
    1. needs_revalidation = True (cascade from parent change)
    2. applied_count >= 3 AND success_rate < 0.5 → FIX
    """
    suggestions = []

    for node in lineages.values():
        if not node.is_active:
            continue

        metrics = node.metrics

        if metrics.needs_revalidation:
            suggestions.append({
                "skill_id": node.skill_id,
                "skill_name": node.skill_name,
                "evolution_type": EvolutionType.FIX,
                "reason": "标记为需要重新验证（级联更新）",
                "current_success_rate": metrics.success_rate,
                "depends_on_changed": True,
                "generation": node.generation,
                "fix_version": node.fix_version,
            })
            continue

        if metrics.applied_count >= 3 and metrics.success_rate < 0.5:
            suggestions.append({
                "skill_id": node.skill_id,
                "skill_name": node.skill_name,
                "evolution_type": EvolutionType.FIX,
                "reason": f"低成功率 ({metrics.success_rate:.1%}), {metrics.failed_count}/{metrics.applied_count} 次失败",
                "current_success_rate": metrics.success_rate,
                "depends_on_changed": False,
                "generation": node.generation,
                "fix_version": node.fix_version,
            })

    return suggestions


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
