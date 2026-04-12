"""
gstack Workflow Engine
Adapts garrytan/gstack 23-specialist workflow to Juhuo (聚活) personal digital Doppelgänger
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from llm_adapter import (
    LLMAdapter,
    LLMResponse,
    CompletionRequest,
    load_config,
    get_adapter,
)


class WorkflowStage(str, Enum):
    """Workflow stages in gstack order"""
    THINK = "think"
    PLAN = "plan"
    BUILD = "build"
    REVIEW = "review"
    TEST = "test"
    SHIP = "ship"
    REFLECT = "reflect"
    COMPLETED = "completed"


@dataclass
class RoleTask:
    """A task executed by a specialist role"""
    role: str
    prompt: str
    input_context: Dict[str, Any] = field(default_factory=dict)
    output: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    success: Optional[bool] = None


@dataclass
class GStackWorkflowState:
    """State of a gstack workflow execution"""
    project_name: str
    initial_idea: str
    current_stage: WorkflowStage
    tasks: List[RoleTask] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)  # path -> content
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_task(self, task: RoleTask) -> None:
        """Add a task to the workflow"""
        self.tasks.append(task)
        self.updated_at = datetime.now()

    def add_artifact(self, name: str, content: str) -> None:
        """Add an artifact (design doc, plan, test results, etc.)"""
        self.artifacts[name] = content
        self.updated_at = datetime.now()

    def get_artifact(self, name: str) -> Optional[str]:
        """Get an artifact by name"""
        return self.artifacts.get(name)

    def set_stage(self, stage: WorkflowStage) -> None:
        """Update the current stage"""
        self.current_stage = stage
        self.updated_at = datetime.now()


class GStackWorkflow:
    """
    gstack workflow - 23 specialist roles working through the full pipeline:
    Think → Plan → Build → Review → Test → Ship → Reflect
    """

    def __init__(
        self,
        project_name: str,
        initial_idea: str,
        llm_config: Optional[Dict[str, Any]] = None,
    ):
        self.state = GStackWorkflowState(
            project_name=project_name,
            initial_idea=initial_idea,
            current_stage=WorkflowStage.THINK,
        )
        self.llm_config = llm_config or {}
        self.llm: Optional[LLMAdapter] = None
        self._callbacks: Dict[str, List[Callable]] = {
            "stage_complete": [],
            "task_complete": [],
            "workflow_complete": [],
        }

    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for an event"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _trigger_event(self, event: str, *args, **kwargs) -> None:
        """Trigger an event"""
        for callback in self._callbacks.get(event, []):
            callback(*args, **kwargs)

    def initialize_llm(self) -> None:
        """Initialize the LLM adapter from config"""
        if self.llm is None:
            if self.llm_config:
                self.llm = get_adapter(self.llm_config)
            else:
                # Use default config from disk
                config = load_config()
                self.llm = get_adapter(config)

    def run_office_hours(self) -> RoleTask:
        """Run the office hours (think stage)"""
        from .role_prompts import get_role_prompt, RoleType

        self.initialize_llm()
        prompt_template = get_role_prompt(RoleType.OFFICE_HOURS)
        full_prompt = f"""Initial idea: {self.state.initial_idea}

{prompt_template}"""

        task = RoleTask(
            role=RoleType.OFFICE_HOURS.value,
            prompt=full_prompt,
            started_at=datetime.now(),
        )

        response = self.llm.complete(full_prompt)
        task.output = response
        task.completed_at = datetime.now()
        task.success = True

        self.state.add_task(task)
        self.state.add_artifact("design_doc", response)
        self.state.set_stage(WorkflowStage.PLAN)

        self._trigger_event("task_complete", task)
        self._trigger_event("stage_complete", WorkflowStage.THINK, self.state)

        return task

    def run_ceo_review(self) -> RoleTask:
        """Run CEO review (plan stage)"""
        from .role_prompts import get_role_prompt, RoleType

        self.initialize_llm()
        prompt_template = get_role_prompt(RoleType.CEO_REVIEW)
        design_doc = self.state.get_artifact("design_doc") or ""
        full_prompt = f"""Existing design doc:

{design_doc}

{prompt_template}"""

        task = RoleTask(
            role=RoleType.CEO_REVIEW.value,
            prompt=full_prompt,
            started_at=datetime.now(),
        )

        response = self.llm.complete(full_prompt)
        task.output = response
        task.completed_at = datetime.now()
        task.success = True

        self.state.add_task(task)
        self.state.add_artifact("ceo_review", response)

        self._trigger_event("task_complete", task)

        return task

    def run_eng_review(self) -> RoleTask:
        """Run engineering manager architecture review (plan stage)"""
        from .role_prompts import get_role_prompt, RoleType

        self.initialize_llm()
        prompt_template = get_role_prompt(RoleType.ENG_REVIEW)
        design_doc = self.state.get_artifact("design_doc") or ""
        ceo_review = self.state.get_artifact("ceo_review") or ""
        full_prompt = f"""Design doc:
{design_doc}

CEO review:
{ceo_review}

{prompt_template}"""

        task = RoleTask(
            role=RoleType.ENG_REVIEW.value,
            prompt=full_prompt,
            started_at=datetime.now(),
        )

        response = self.llm.complete(full_prompt)
        task.output = response
        task.completed_at = datetime.now()
        task.success = True

        self.state.add_task(task)
        self.state.add_artifact("eng_review", response)

        self._trigger_event("task_complete", task)

        return task

    def run_design_review(self, is_user_facing: bool = True) -> Optional[RoleTask]:
        """Run design review if user-facing product (plan stage)"""
        if not is_user_facing:
            return None

        from .role_prompts import get_role_prompt, RoleType

        self.initialize_llm()
        prompt_template = get_role_prompt(RoleType.DESIGN_REVIEW)
        design_doc = self.state.get_artifact("design_doc") or ""
        ceo_review = self.state.get_artifact("ceo_review") or ""

        full_prompt = f"""Design doc:
{design_doc}

CEO review:
{ceo_review}

{prompt_template}"""

        task = RoleTask(
            role=RoleType.DESIGN_REVIEW.value,
            prompt=full_prompt,
            started_at=datetime.now(),
        )

        response = self.llm.complete(full_prompt)
        task.output = response
        task.completed_at = datetime.now()
        task.success = True

        self.state.add_task(task)
        self.state.add_artifact("design_review", response)

        self._trigger_event("task_complete", task)

        return task

    def run_devex_review(self, is_developer_facing: bool = False) -> Optional[RoleTask]:
        """Run developer experience review if SDK/API/CLI (plan stage)"""
        if not is_developer_facing:
            return None

        from .role_prompts import get_role_prompt, RoleType

        self.initialize_llm()
        prompt_template = get_role_prompt(RoleType.DEVEX_REVIEW)
        design_doc = self.state.get_artifact("design_doc") or ""
        ceo_review = self.state.get_artifact("ceo_review") or ""

        full_prompt = f"""Design doc:
{design_doc}

CEO review:
{ceo_review}

{prompt_template}"""

        task = RoleTask(
            role=RoleType.DEVEX_REVIEW.value,
            prompt=full_prompt,
            started_at=datetime.now(),
        )

        response = self.llm.complete(full_prompt)
        task.output = response
        task.completed_at = datetime.now()
        task.success = True

        self.state.add_task(task)
        self.state.add_artifact("devex_review", response)

        self._trigger_event("task_complete", task)

        return task

    def run_autoplan(
        self,
        is_user_facing: bool = True,
        is_developer_facing: bool = False,
    ) -> List[RoleTask]:
        """Run the full auto-planning pipeline automatically"""
        tasks = []

        # office hours already done?
        if not any(t.role == RoleType.OFFICE_HOURS.value for t in self.state.tasks):
            task = self.run_office_hours()
            tasks.append(task)

        # CEO review
        if not any(t.role == RoleType.CEO_REVIEW.value for t in self.state.tasks):
            task = self.run_ceo_review()
            tasks.append(task)

        # Design review if user-facing
        if is_user_facing:
            task = self.run_design_review(is_user_facing)
            if task:
                tasks.append(task)

        # DevEx review if developer-facing
        if is_developer_facing:
            task = self.run_devex_review(is_developer_facing)
            if task:
                tasks.append(task)

        # Engineering review
        if not any(t.role == RoleType.ENG_REVIEW.value for t in self.state.tasks):
            task = self.run_eng_review()
            tasks.append(task)

        self.state.set_stage(WorkflowStage.BUILD)
        self._trigger_event("stage_complete", WorkflowStage.PLAN, self.state)

        return tasks

    def run_security_audit(self) -> RoleTask:
        """Run CSO security audit before ship"""
        from .role_prompts import get_role_prompt, RoleType

        self.initialize_llm()
        prompt_template = get_role_prompt(RoleType.CSO)
        full_prompt = prompt_template

        task = RoleTask(
            role=RoleType.CSO.value,
            prompt=full_prompt,
            started_at=datetime.now(),
        )

        response = self.llm.complete(full_prompt)
        task.output = response
        task.completed_at = datetime.now()
        task.success = True

        self.state.add_task(task)
        self.state.add_artifact("security_audit", response)

        self._trigger_event("task_complete", task)

        return task

    def run_retro(self) -> RoleTask:
        """Run weekly retro after ship"""
        from .role_prompts import get_role_prompt, RoleType

        self.initialize_llm()
        prompt_template = get_role_prompt(RoleType.RETRO)

        # Collect all task outputs
        task_outputs = "\n\n".join([
            f"=== {t.role} ===\n{t.output}" for t in self.state.tasks
        ])

        full_prompt = f"""Project: {self.state.project_name}
Initial idea: {self.state.initial_idea}

All tasks completed in this sprint:
{task_outputs}

{prompt_template}"""

        task = RoleTask(
            role=RoleType.RETRO.value,
            prompt=full_prompt,
            started_at=datetime.now(),
        )

        response = self.llm.complete(full_prompt)
        task.output = response
        task.completed_at = datetime.now()
        task.success = True

        self.state.add_task(task)
        self.state.add_artifact("retro", response)
        self.state.set_stage(WorkflowStage.COMPLETED)

        self._trigger_event("task_complete", task)
        self._trigger_event("stage_complete", WorkflowStage.REFLECT, self.state)
        self._trigger_event("workflow_complete", self.state)

        return task

    def get_full_plan(self) -> str:
        """Get the complete aggregated plan after planning"""
        artifacts = []
        for name in ["design_doc", "ceo_review", "design_review", "devex_review", "eng_review"]:
            content = self.state.get_artifact(name)
            if content:
                artifacts.append(f"# {name.replace('_', ' ').title()}\n\n{content}")

        return "\n\n".join(artifacts)

    def save_workflow(self, output_path: str) -> None:
        """Save the workflow state to a JSON file"""
        import json
        from dataclasses import asdict

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.state), f, indent=2, default=str)


def create_gstack_workflow(
    project_name: str,
    initial_idea: str,
    llm_config: Optional[Dict[str, Any]] = None,
) -> GStackWorkflow:
    """Create a new gstack workflow instance"""
    return GStackWorkflow(project_name, initial_idea, llm_config)
