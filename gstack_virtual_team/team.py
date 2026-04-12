"""
VirtualTeam - manages the virtual team of experts
"""

from typing import List, Optional, Dict
from .types import Role, RoleType, Task, ReviewResult, WorkflowState, WorkflowStatus, ReviewFinding
from .roles import ALL_ROLES, get_role


class VirtualTeam:
    """Manages a virtual team of expert roles"""

    def __init__(self):
        self._roles: Dict[RoleType, Role] = {r.role_type: r for r in ALL_ROLES}

    def list_roles(self) -> List[Role]:
        """List all available roles"""
        return sorted(self._roles.values(), key=lambda r: r.name)

    def get_role(self, role_type: RoleType) -> Optional[Role]:
        """Get a role by type"""
        return self._roles.get(role_type)

    def enable_role(self, role_type: RoleType) -> bool:
        """Enable a role"""
        role = self._roles.get(role_type)
        if role:
            role.enabled = True
            return True
        return False

    def disable_role(self, role_type: RoleType) -> bool:
        """Disable a role"""
        role = self._roles.get(role_type)
        if role:
            role.enabled = False
            return True
        return False

    def get_enabled_roles(self) -> List[Role]:
        """Get all enabled roles"""
        return [r for r in self._roles.values() if r.enabled]

    def create_standard_workflow(self, project_name: str) -> WorkflowState:
        """Create a standard full workflow with all enabled roles"""

        # Standard workflow order
        standard_tasks = [
            ("ceo_review", "CEO-level strategy and scope review", RoleType.CEO),
            ("product_backlog", "Create prioritized product backlog with user stories", RoleType.PRODUCT),
            ("architecture_review", "Architecture review and design", RoleType.ARCHITECT),
            ("design_review", "UI/UX design review", RoleType.DESIGN),
            ("frontend_implementation", "Frontend implementation", RoleType.FRONTEND),
            ("backend_implementation", "Backend implementation", RoleType.BACKEND),
            ("security_audit", "Security audit (OWASP Top 10 + STRIDE)", RoleType.SECURITY),
            ("qa_testing", "QA testing and bug finding", RoleType.QA),
            ("devex_review", "Developer experience review", RoleType.DEVEX),
            ("documentation", "Update documentation", RoleType.DOCS),
        ]

        tasks = []
        dependencies = []

        for i, (task_id, title, role) in enumerate(standard_tasks):
            if self.get_role(role) and self.get_role(role).enabled:
                deps = dependencies.copy() if i > 0 else []
                task = Task(
                    task_id=task_id,
                    title=title,
                    description=title,
                    assigned_role=role,
                    dependencies=deps,
                )
                tasks.append(task)
                dependencies.append(task_id)

        return WorkflowState(
            project_name=project_name,
            status=WorkflowStatus.PLANNING,
            tasks=tasks,
        )

    def create_minimal_workflow(self, project_name: str) -> WorkflowState:
        """Create a minimal workflow (CEO + Architect + QA + Docs)"""

        minimal_tasks = [
            ("ceo_review", "CEO-level strategy and scope review", RoleType.CEO),
            ("architecture_review", "Architecture review and design", RoleType.ARCHITECT),
            ("security_audit", "Security audit", RoleType.SECURITY),
            ("qa_testing", "QA testing", RoleType.QA),
            ("documentation", "Update documentation", RoleType.DOCS),
        ]

        tasks = []
        dependencies = []

        for task_id, title, role in minimal_tasks:
            if self.get_role(role) and self.get_role(role).enabled:
                deps = dependencies.copy() if dependencies else []
                task = Task(
                    task_id=task_id,
                    title=title,
                    description=title,
                    assigned_role=role,
                    dependencies=deps,
                )
                tasks.append(task)
                dependencies.append(task_id)

        return WorkflowState(
            project_name=project_name,
            status=WorkflowStatus.PLANNING,
            tasks=tasks,
        )

    def format_review_summary(self, review: ReviewResult) -> str:
        """Format a review result for human reading"""
        lines = [f"## {review.role_type.value.title()} Review"]
        lines.append("")

        if review.passed:
            lines.append("✅ **PASSED**")
        else:
            lines.append("❌ **FAILED** - issues found")
        lines.append("")

        if review.findings:
            # Group by severity
            critical = review.critical_findings
            major = review.major_findings
            other = [f for f in review.findings if f.severity not in ("critical", "major")]

            if critical:
                lines.append("### 🔴 Critical Issues")
                lines.append("")
                for i, finding in enumerate(critical, 1):
                    lines.append(f"{i}. **{finding.category}**: {finding.description}")
                    if finding.recommendation:
                        lines.append(f"   - Recommendation: {finding.recommendation}")
                    if finding.location:
                        lines.append(f"   - Location: {finding.location}")
                    lines.append("")

            if major:
                lines.append("### 🟠 Major Issues")
                lines.append("")
                for i, finding in enumerate(major, 1):
                    lines.append(f"{i}. **{finding.category}**: {finding.description}")
                    if finding.recommendation:
                        lines.append(f"   - Recommendation: {finding.recommendation}")
                    lines.append("")

            if other:
                lines.append("### 🟡 Other Findings")
                lines.append("")
                for i, finding in enumerate(other, 1):
                    lines.append(f"{i}. **{finding.category}**: {finding.description}")
                    if finding.recommendation:
                        lines.append(f"   - {finding.recommendation}")
                lines.append("")

        if review.summary:
            lines.append("### Summary")
            lines.append("")
            lines.append(review.summary)
            lines.append("")

        return "\n".join(lines)

    def get_full_summary(self, state: WorkflowState) -> str:
        """Get full workflow summary"""
        summary = state.summary()
        lines = [f"# Virtual Team Workflow: {summary['project_name']}"]
        lines.append("")
        lines.append(f"Status: **{summary['status']}**")
        lines.append(f"Progress: {summary['completed_tasks']}/{summary['total_tasks']} ({summary['progress_pct']}%)")
        lines.append(f"Reviews completed: {summary['reviews_count']}")
        lines.append(f"Critical issues: {summary['critical_issues']}")
        lines.append(f"Major issues: {summary['major_issues']}")
        lines.append("")

        lines.append("## Tasks")
        lines.append("")
        for task in state.tasks:
            status = "✅" if task.completed else "⏳"
            role_name = task.assigned_role.value
            lines.append(f"{status} **{role_name.title()}**: {task.title}")

        lines.append("")

        if state.reviews:
            lines.append("## Review Findings Summary")
            lines.append("")
            total_critical = sum(len(r.critical_findings) for r in state.reviews)
            total_major = sum(len(r.major_findings) for r in state.reviews)
            lines.append(f"Total: {total_critical} critical, {total_major} major")
            lines.append("")

            for review in state.reviews:
                if review.findings:
                    lines.append(f"**{review.role_type.value.title()}**: {len(review.critical_findings)} critical, {len(review.major_findings)} major")

        return "\n".join(lines)
