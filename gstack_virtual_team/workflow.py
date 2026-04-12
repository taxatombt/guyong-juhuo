"""
GStackWorkflow - orchestrates the virtual team workflow
"""

from typing import List, Optional, Callable, Any
from datetime import datetime
from .types import (
    Role,
    RoleType,
    Task,
    WorkflowState,
    WorkflowStatus,
    ReviewResult,
    ReviewFinding,
)
from .team import VirtualTeam
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm_adapter import LLMAdapter


class GStackWorkflow:
    """Orchestrates the gstack virtual team workflow"""

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        virtual_team: Optional[VirtualTeam] = None,
    ):
        self.llm = llm_adapter
        self.team = virtual_team or VirtualTeam()
        self.state: Optional[WorkflowState] = None

    def start_standard_workflow(self, project_name: str, project_context: str) -> str:
        """Start a new standard full workflow"""
        self.state = self.team.create_standard_workflow(project_name)
        self.state.metadata["context"] = project_context
        return self.get_next_step_description()

    def start_minimal_workflow(self, project_name: str, project_context: str) -> str:
        """Start a new minimal workflow (faster)"""
        self.state = self.team.create_minimal_workflow(project_name)
        self.state.metadata["context"] = project_context
        return self.get_next_step_description()

    def get_next_step_description(self) -> str:
        """Get description of the next step"""
        if not self.state:
            return "No workflow started. Call start_standard_workflow() or start_minimal_workflow() first."

        next_task = self.state.get_next_task()
        if not next_task:
            self.state.status = WorkflowStatus.COMPLETED
            return self.team.get_full_summary(self.state)

        self.state.status = WorkflowStatus.EXECUTING
        self.state.current_task = next_task
        self.state.current_role = next_task.assigned_role
        role = self.team.get_role(next_task.assigned_role)

        return f"""Next step: {next_task.title}
Assigned to: {role.name}
Role: {role.description}

Running review...
"""

    async def run_current_task(self) -> ReviewResult:
        """Run the current task with the assigned expert role"""
        if not self.state or not self.state.current_task:
            raise ValueError("No current task to run")

        role_type = self.state.current_task.assigned_role
        role = self.team.get_role(role_type)
        if not role:
            raise ValueError(f"Role {role_type} not found")

        context = self.state.metadata.get("context", "")
        system_prompt = role.get_system_prompt(context)

        # Add additional context about current workflow
        full_prompt = f"""{system_prompt}

---
Current workflow progress:
{self.team.get_full_summary(self.state)}

Please provide your review. Format your response with clear findings grouped by severity.
For each finding include:
- severity (critical/major/minor/info)
- category
- description
- recommendation
- location (if applicable)

End with a summary and whether you approve (passed = true/false).
"""

        # Call LLM with the role's system prompt
        response = await self.llm.complete(
            system_prompt=system_prompt,
            user_prompt=full_prompt,
        )

        # Parse response into ReviewResult
        review_result = self._parse_llm_response(response, role_type)
        self.state.add_review(review_result)

        # Check if there are critical issues that block progress
        if review_result.has_critical():
            self.state.status = WorkflowStatus.BLOCKED

        return review_result

    def _parse_llm_response(self, response: str, role_type: RoleType) -> ReviewResult:
        """Parse LLM response into structured ReviewResult"""
        findings: List[ReviewFinding] = []
        passed = True
        summary = ""

        # Simple parsing - look for patterns
        lines = response.split("\n")
        in_summary = False
        current_finding: dict = {}

        for line in lines:
            line = line.strip()
            if not line:
                if in_summary and current_finding:
                    # End of finding
                    if all(k in current_finding for k in ["severity", "category", "description"]):
                        findings.append(ReviewFinding(**current_finding))
                        current_finding = {}
                    in_summary = False
                continue

            # Look for severity markers
            lower_line = line.lower()
            if "critical" in lower_line or "🔴" in line:
                if current_finding:
                    findings.append(ReviewFinding(**current_finding))
                    current_finding = {}
                current_finding["severity"] = "critical"
                if "critical" in lower_line:
                    passed = False
                in_summary = True
            elif "major" in lower_line or "🟠" in line:
                if current_finding:
                    findings.append(ReviewFinding(**current_finding))
                    current_finding = {}
                current_finding["severity"] = "major"
                if "major" in lower_line:
                    passed = False
                in_summary = True
            elif "minor" in lower_line or "🟡" in line:
                if current_finding:
                    findings.append(ReviewFinding(**current_finding))
                    current_finding = {}
                current_finding["severity"] = "minor"
                in_summary = True
            elif "info" in lower_line or "🔵" in line:
                if current_finding:
                    findings.append(ReviewFinding(**current_finding))
                    current_finding = {}
                current_finding["severity"] = "info"
                in_summary = True
            elif line.lower().startswith("summary:") or "### summary" in line.lower():
                if current_finding:
                    findings.append(ReviewFinding(**current_finding))
                    current_finding = {}
                in_summary = False
                summary = line.split(":", 1)[1].strip() if ":" in line else ""
            elif in_summary:
                if "category:" in line.lower():
                    current_finding["category"] = line.split(":", 1)[1].strip()
                elif "description:" in line.lower():
                    current_finding["description"] = line.split(":", 1)[1].strip()
                elif "recommendation:" in line.lower():
                    current_finding["recommendation"] = line.split(":", 1)[1].strip()
                elif "location:" in line.lower():
                    current_finding["location"] = line.split(":", 1)[1].strip()
                elif "category" not in current_finding and ":" in line:
                    # First part after severity is usually category
                    cat, desc = line.split(":", 1)
                    current_finding["category"] = cat.strip().strip(":")
                    current_finding["description"] = desc.strip()
                elif "description" in current_finding and "description" not in current_finding:
                    current_finding["description"] += " " + line
                elif "recommendation" in current_finding and "recommendation" not in current_finding:
                    current_finding["recommendation"] += " " + line

        # Add the last finding if any
        if current_finding and all(k in current_finding for k in ["severity", "category", "description"]):
            findings.append(ReviewFinding(**current_finding))

        # Look for passed/failed in summary
        lower_response = response.lower()
        if "passed: true" in lower_response or "approve" in lower_response or "approve\n" in lower_response:
            passed = True
        elif "passed: false" in lower_response or "fail" in lower_response or "do not approve" in lower_response:
            passed = False
            if not findings:
                # If no findings but failed, add a generic finding
                findings.append(ReviewFinding(
                    severity="critical",
                    category="Approval",
                    description="Review did not approve",
                    recommendation="Address the issues mentioned before proceeding",
                ))

        # If there are critical findings, it's automatically not passed
        if any(f.severity == "critical" for f in findings):
            passed = False

        return ReviewResult(
            role_type=role_type,
            passed=passed,
            findings=findings,
            summary=summary,
        )

    def mark_current_completed(self) -> None:
        """Mark current task as completed"""
        if not self.state or not self.state.current_task:
            return
        self.state.mark_task_completed(self.state.current_task.task_id)
        self.state.current_task = None
        self.state.current_role = None

    def is_completed(self) -> bool:
        """Check if workflow is completed"""
        if not self.state:
            return False
        if self.state.status == WorkflowStatus.COMPLETED:
            return True
        if self.state.status == WorkflowStatus.BLOCKED:
            return False
        next_task = self.state.get_next_task()
        return next_task is None

    def is_blocked(self) -> bool:
        """Check if workflow is blocked by critical issues"""
        return self.state and self.state.status == WorkflowStatus.BLOCKED

    def get_current_review_result(self) -> Optional[ReviewResult]:
        """Get the most recent review result"""
        if not self.state or not self.state.reviews:
            return None
        return self.state.reviews[-1]

    def get_full_summary_text(self) -> str:
        """Get full workflow summary"""
        if not self.state:
            return "No workflow started"
        return self.team.get_full_summary(self.state)

    def save_state_to_file(self, filepath: str) -> None:
        """Save workflow state to JSON file"""
        import json
        from dataclasses import asdict

        if not self.state:
            raise ValueError("No workflow state to save")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(self.state), f, indent=2, default=str)

    def get_state(self) -> Optional[WorkflowState]:
        """Get current workflow state"""
        return self.state
