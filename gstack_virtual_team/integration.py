"""
gstack integration with 聚活 (JuHuo) personal digital clone system

This integrates the gstack virtual engineering team methodology with the
聚活 digital clone evolution system, enabling collaborative AI development
of the clone itself.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import json
import os

from .team import VirtualTeam
from .workflow import GStackWorkflow
from .types import WorkflowState
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm_adapter import LLMAdapter, load_config, get_adapter


@dataclass
class JuhuoGStackConfig:
    """Configuration for gstack integration with 聚活"""
    # Which roles to enable by default for聚活 evolution tasks
    enabled_roles: List[str] = None
    # Use minimal workflow for聚活 internal tasks
    use_minimal_workflow: bool = True
    # Auto-save workflow state after each step
    auto_save: bool = True
    # Directory for saving workflow states
    workflow_dir: str = "gstack_workflows"
    # Require user approval after each critical review
    user_approval_required: bool = True

    def __post_init__(self):
        if self.enabled_roles is None:
            # Default: CEO + Architect + Security + QA + Docs for聚活 evolution
            self.enabled_roles = ["ceo", "architect", "security", "qa", "devex", "docs"]


class JuhuoGStackIntegration:
    """
    gstack virtual team integration for聚活 digital clone system.

    Enables the聚活 system to use gstack's multi-expert virtual engineering
    team methodology for self-improvement and evolution.
    """

    def __init__(
        self,
        llm_config_path: Optional[str] = None,
        config: Optional[JuhuoGStackConfig] = None,
    ):
        self.config = config or JuhuoGStackConfig()
        self.team = VirtualTeam()
        self._configure_team()

        # Initialize LLM adapter
        if llm_config_path and os.path.exists(llm_config_path):
            llm_config = load_config(llm_config_path)
            self.llm = get_adapter(llm_config)
        else:
            self.llm = None

        self.workflow: Optional[GStackWorkflow] = None
        self._ensure_workflow_dir()

    def _configure_team(self):
        """Configure team based on enabled roles"""
        from .types import RoleType

        # Disable roles not in enabled_roles
        for role_type in RoleType:
            role = self.team.get_role(role_type)
            if role:
                if role_type.value in self.config.enabled_roles:
                    self.team.enable_role(role_type)
                else:
                    self.team.disable_role(role_type)

    def _ensure_workflow_dir(self):
        """Ensure workflow directory exists"""
        os.makedirs(self.config.workflow_dir, exist_ok=True)

    def _auto_save(self, project_name: str):
        """Auto-save current workflow state"""
        if not self.config.auto_save or not self.workflow or not self.workflow.state:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project_name}_{timestamp}.json"
        filepath = os.path.join(self.config.workflow_dir, filename)
        self.workflow.save_state_to_file(filepath)

    def start_evolution_task(
        self,
        task_description: str,
        project_name: Optional[str] = None,
    ) -> str:
        """
        Start a聚活 self-evolution task using gstack virtual team.

        Args:
            task_description: Description of the evolution task
            project_name: Optional project name (defaults to timestamp)

        Returns:
            Description of the first step
        """
        if not self.llm:
            return "Error: LLM adapter not configured. Please configure a large language model first."

        if not project_name:
            project_name = f"juhuo_evolution_{datetime.now().strftime('%Y%m%d')}"

        # Build full context including聚活 context
        project_context = f"""
Project: 聚活 (JuHuo) - Personal Digital Clone System
Task: {task_description}

聚活 is a personal digital clone system that:
- Clones personal thinking patterns and decision-making
- Uses OpenSpace DAG-based self-evolution
- Goals: remember everything about the individual, let the digital clone live on forever
- Current task: self-evolution and improvement

Please conduct your review based on gstack virtual team methodology:
- Boil the Lake: when AI makes completeness cheap, do the complete thing
- Search Before Building: search first, don't build from scratch if it exists
- User Sovereignty: AI recommends, user decides
- Zero silent failures: every failure mode must be visible
"""

        if self.config.use_minimal_workflow:
            self.workflow = GStackWorkflow(self.llm, self.team)
            result = self.workflow.start_minimal_workflow(project_name, project_context)
        else:
            self.workflow = GStackWorkflow(self.llm, self.team)
            result = self.workflow.start_standard_workflow(project_name, project_context)

        self._auto_save(project_name)
        return result

    async def run_next_step(self) -> Dict[str, Any]:
        """
        Run the next step in the current workflow.

        Returns:
            Dict with review result and status
        """
        if not self.workflow:
            return {
                "success": False,
                "error": "No workflow started. Call start_evolution_task() first.",
            }

        if self.workflow.is_completed():
            return {
                "success": True,
                "completed": True,
                "summary": self.workflow.get_full_summary_text(),
            }

        if self.workflow.is_blocked():
            return {
                "success": False,
                "blocked": True,
                "summary": self.workflow.get_full_summary_text(),
                "error": "Workflow blocked by critical issues. Please address them before proceeding.",
            }

        review_result = await self.workflow.run_current_task()
        self._auto_save(self.workflow.state.project_name)

        has_critical = review_result.has_critical()

        return {
            "success": review_result.passed,
            "completed": False,
            "blocked": has_critical,
            "role": review_result.role_type.value,
            "passed": review_result.passed,
            "critical_count": len(review_result.critical_findings),
            "major_count": len(review_result.major_findings),
            "summary": self.team.format_review_summary(review_result),
            "full_summary": self.workflow.get_full_summary_text(),
        }

    def approve_current_step(self) -> None:
        """Approve current step and mark it completed"""
        if self.workflow:
            self.workflow.mark_current_completed()
            self._auto_save(self.workflow.state.project_name)

    def get_summary(self) -> str:
        """Get full workflow summary"""
        if not self.workflow:
            return "No workflow started"
        return self.workflow.get_full_summary_text()

    def is_workflow_completed(self) -> bool:
        """Check if workflow is completed"""
        return self.workflow and self.workflow.is_completed()

    def is_workflow_blocked(self) -> bool:
        """Check if workflow is blocked"""
        return self.workflow and self.workflow.is_blocked()

    def get_enabled_roles(self) -> List[str]:
        """Get list of enabled role names"""
        return [r.role_type.value for r in self.team.get_enabled_roles()]

    def set_llm_adapter(self, llm: LLMAdapter) -> None:
        """Set the LLM adapter after initialization"""
        self.llm = llm


# ============================================
# Convenience function for creating a workflow
# ============================================
def create_juhuo_virtual_team(
    llm_config_path: Optional[str] = None,
    enabled_roles: Optional[List[str]] = None,
) -> JuhuoGStackIntegration:
    """
    Create a gstack virtual team for聚活 evolution tasks.

    Args:
        llm_config_path: Path to LLM config JSON file
        enabled_roles: List of role types to enable (defaults to minimal set)

    Returns:
        Configured JuhuoGStackIntegration instance
    """
    config = JuhuoGStackConfig()
    if enabled_roles:
        config.enabled_roles = enabled_roles
    return JuhuoGStackIntegration(llm_config_path, config)
