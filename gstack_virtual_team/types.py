"""
Type definitions for gstack virtual team
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class RoleType(Enum):
    """Expert role types in virtual team"""
    CEO = "ceo"
    PRODUCT = "product"
    ARCHITECT = "architect"
    FRONTEND = "frontend"
    BACKEND = "backend"
    QA = "qa"
    SECURITY = "security"
    DESIGN = "design"
    DEVEX = "devex"
    DOCS = "docs"


class WorkflowStatus(Enum):
    """Workflow execution status"""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class Role:
    """Definition of an expert role"""
    role_type: RoleType
    name: str
    description: str
    responsibilities: List[str]
    prompt_template: str
    enabled: bool = True

    def get_system_prompt(self, context: str) -> str:
        """Get formatted system prompt for this role"""
        return self.prompt_template.format(context=context)


@dataclass
class Task:
    """A task in the workflow"""
    task_id: str
    title: str
    description: str
    assigned_role: RoleType
    dependencies: List[str] = field(default_factory=list)
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class ReviewFinding:
    """A single finding from a review"""
    severity: str  # "critical", "major", "minor", "info"
    category: str
    description: str
    recommendation: str
    location: Optional[str] = None  # file/path/line


@dataclass
class ReviewResult:
    """Result from a role's review"""
    role_type: RoleType
    passed: bool
    findings: List[ReviewFinding] = field(default_factory=list)
    summary: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def critical_findings(self) -> List[ReviewFinding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def major_findings(self) -> List[ReviewFinding]:
        return [f for f in self.findings if f.severity == "major"]

    def has_critical(self) -> bool:
        return len(self.critical_findings) > 0


@dataclass
class WorkflowState:
    """Current state of the workflow"""
    project_name: str
    status: WorkflowStatus = WorkflowStatus.IDLE
    tasks: List[Task] = field(default_factory=list)
    reviews: List[ReviewResult] = field(default_factory=list)
    current_task: Optional[Task] = None
    current_role: Optional[RoleType] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_next_task(self) -> Optional[Task]:
        """Get next incomplete task with satisfied dependencies"""
        completed_task_ids = {t.task_id for t in self.tasks if t.completed}
        for task in self.tasks:
            if not task.completed:
                if all(dep in completed_task_ids for dep in task.dependencies):
                    return task
        return None

    def mark_task_completed(self, task_id: str) -> None:
        """Mark a task as completed"""
        for task in self.tasks:
            if task.task_id == task_id:
                task.completed = True
                task.completed_at = datetime.now()
                break
        self.updated_at = datetime.now()

    def add_review(self, review: ReviewResult) -> None:
        """Add a review result"""
        self.reviews.append(review)
        self.updated_at = datetime.now()

    def get_reviews_by_role(self, role: RoleType) -> List[ReviewResult]:
        """Get all reviews from a specific role"""
        return [r for r in self.reviews if r.role_type == role]

    def summary(self) -> Dict[str, Any]:
        """Get workflow summary"""
        total_tasks = len(self.tasks)
        completed_tasks = sum(1 for t in self.tasks if t.completed)
        critical_issues = sum(
            len(r.critical_findings) for r in self.reviews
        )
        major_issues = sum(
            len(r.major_findings) for r in self.reviews
        )
        return {
            "project_name": self.project_name,
            "status": self.status.value,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "progress_pct": round(completed_tasks / total_tasks * 100 if total_tasks > 0 else 0, 1),
            "reviews_count": len(self.reviews),
            "critical_issues": critical_issues,
            "major_issues": major_issues,
        }
