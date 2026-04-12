"""
HermesEvolution - Core self-evolution engine based on NousResearch/Hermes-Agent

Implements the closed-loop learning cycle:
1. Execute task with existing skills
2. Record execution trajectory (success/failure)
3. Extract new skills from successful complex tasks
4. Improve existing skills based on failure analysis
5. Persist all knowledge to skill storage
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path

from .skill_storage import SkillStorage
from .trajectory_recorder import TrajectoryRecorder


class HermesEvolution:
    """Core self-evolution engine implementing Hermes-Agent closed-loop learning."""
    
    def __init__(
        self,
        db_path: str = "E:\\juhuo\\hermes_evolution\\skills.db",
        trajectories_dir: str = "E:\\juhuo\\hermes_evolution\\trajectories",
    ):
        self.skill_storage = SkillStorage(db_path)
        self.trajectory_recorder = TrajectoryRecorder(trajectories_dir)
        self.categories = [
            "development",
            "debugging",
            "automation",
            "data-processing",
            "web",
            "database",
            "git",
            "testing",
            "documentation",
            "other",
        ]
    
    def search_skills(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for relevant skills for a task."""
        return self.skill_storage.search_skills(query, limit)
    
    def get_skill(self, name: str) -> Optional[Dict]:
        """Get a specific skill by name."""
        return self.skill_storage.get_skill(name)
    
    def start_task(
        self,
        task_description: str,
        skill_name: Optional[str] = None,
    ) -> str:
        """Start recording a task trajectory."""
        return self.trajectory_recorder.start_trajectory(
            task_description=task_description,
            skill_name=skill_name,
        )
    
    def record_step(
        self,
        action: str,
        input: Any,
        output: Any,
        success: bool,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Record a step in the current task."""
        self.trajectory_recorder.add_step(
            action=action,
            input=input,
            output=output,
            success=success,
            duration_seconds=duration_seconds,
            metadata=metadata,
        )
    
    def end_task(self, success: bool, final_result: Optional[Any] = None) -> str:
        """End the current task and trigger potential learning."""
        trajectory_id = self.trajectory_recorder.end_trajectory(success, final_result)
        
        # If we used an existing skill, record the result for learning
        if self.trajectory_recorder.current_trajectory is None:
            trajectory = self.trajectory_recorder.get_trajectory(trajectory_id)
            if trajectory and trajectory.get("skill_name"):
                self.skill_storage.record_result(
                    trajectory["skill_name"], 
                    success,
                )
        
        return trajectory_id
    
    def extract_new_skill_from_trajectory(
        self,
        trajectory_id: str,
        category: str = "other",
    ) -> Optional[Dict]:
        """Extract a new skill from a successful trajectory.
        
        Based on Hermes principle: successfully completed complex tasks
        should be turned into reusable skills.
        """
        trajectory = self.trajectory_recorder.get_trajectory(trajectory_id)
        if not trajectory or not trajectory["success"]:
            return None
        
        if len(trajectory["steps"]) < 3:
            # Too simple, doesn't need to be a skill
            return None
        
        # Generate skill name from task description
        skill_name = self._generate_skill_name(trajectory["task_description"])
        description = trajectory["task_description"]
        
        # Generate skill content in SKILL.md format
        content = self._generate_skill_content(trajectory)
        
        # Extract tags from task and steps
        tags = self._extract_tags(trajectory)
        
        # Add to storage
        skill_id = self.skill_storage.add_skill(
            name=skill_name,
            description=description,
            content=content,
            category=category,
            version="1.0.0",
            author="HermesEvolution",
            tags=tags,
        )
        
        if skill_id > 0:
            return {
                "id": skill_id,
                "name": skill_name,
                "description": description,
                "category": category,
                "content": content,
                "tags": tags,
            }
        return None
    
    def improve_skill_from_failure(
        self,
        skill_name: str,
        trajectory_id: str,
    ) -> Optional[Dict]:
        """Improve an existing skill based on a failed execution.
        
        Analyze what went wrong and update the skill documentation.
        """
        trajectory = self.trajectory_recorder.get_trajectory(trajectory_id)
        if not trajectory:
            return None
        
        skill = self.skill_storage.get_skill(skill_name)
        if not skill:
            return None
        
        # Find the failed step
        failed_step = None
        for step in reversed(trajectory["steps"]):
            if not step["success"]:
                failed_step = step
                break
        
        if not failed_step:
            return None
        
        # Analyze failure and add troubleshooting section
        failure_analysis = self._analyze_failure(failed_step, trajectory)
        improved_content = self._add_troubleshooting_to_content(
            skill["content"], 
            failure_analysis,
        )
        
        # Bump version (patch increment)
        current_version = skill.get("version", "1.0.0")
        new_version = self._bump_patch_version(current_version)
        
        # Update in storage
        skill_id = self.skill_storage.add_skill(
            name=skill_name,
            description=skill["description"],
            content=improved_content,
            category=skill["category"],
            version=new_version,
            author=skill.get("author"),
            tags=skill["tags"],
            related_skills=skill.get("related_skills", []),
        )
        
        # Record this failure for statistics
        self.skill_storage.record_result(skill_name, success=False)
        
        if skill_id > 0:
            return {
                "id": skill_id,
                "name": skill_name,
                "old_version": current_version,
                "new_version": new_version,
                "failure_analysis": failure_analysis,
            }
        return None
    
    def auto_extract_candidates(self) -> List[Dict]:
        """Automatically extract new skill candidates from successful trajectories."""
        candidates = self.trajectory_recorder.extract_candidates_for_skill()
        extracted = []
        
        for candidate in candidates:
            result = self.extract_new_skill_from_trajectory(candidate["id"])
            if result:
                extracted.append(result)
        
        return extracted
    
    def get_stats(self) -> Dict:
        """Get overall evolution statistics."""
        skill_stats = self.skill_storage.get_stats()
        all_trajectories = self.trajectory_recorder.list_trajectories()
        failed = self.trajectory_recorder.get_failed_trajectories()
        
        return {
            "skills": skill_stats,
            "total_trajectories": len(all_trajectories),
            "failed_trajectories": len(failed),
            "trajectory_success_rate": self.trajectory_recorder.get_success_rate(),
        }
    
    def import_existing_skill(
        self,
        name: str,
        description: str,
        content: str,
        category: str,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Import an existing skill (e.g., from Clawhub/ECC)."""
        return self.skill_storage.add_skill(
            name=name,
            description=description,
            content=content,
            category=category,
            version="1.0.0",
            author="imported",
            tags=tags,
        )
    
    def import_from_directory(
        self,
        directory: str,
        category: str,
    ) -> int:
        """Import all SKILL.md files from a directory structure.
        
        Compatible with Clawhub/ECC skill formats.
        """
        imported = 0
        dir_path = Path(directory)
        
        for skill_dir in dir_path.glob("**/"):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                try:
                    name = skill_dir.name
                    with open(skill_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Try to extract description from frontmatter
                    description = self._extract_description_from_content(content)
                    tags = self._extract_tags_from_content(content)
                    
                    self.import_existing_skill(
                        name=name,
                        description=description,
                        content=content,
                        category=category,
                        tags=tags,
                    )
                    imported += 1
                except Exception:
                    continue
        
        return imported
    
    # === Internal helper methods ===
    
    def _generate_skill_name(self, task_description: str) -> str:
        """Generate a kebab-case skill name from task description."""
        # Take first 5 words, convert to kebab-case
        words = re.findall(r'[a-zA-Z0-9]+', task_description.lower())
        selected = words[:5]
        return "-".join(selected)
    
    def _generate_skill_content(self, trajectory: Dict) -> str:
        """Generate SKILL.md formatted content from a trajectory."""
        task = trajectory["task_description"]
        steps = trajectory["steps"]
        
        content_parts = [
            "---",
            f"name: {self._generate_skill_name(task)}",
            f"description: {task}",
            "version: 1.0.0",
            "author: HermesEvolution (auto-extracted)",
            "license: MIT",
            "metadata:",
            "  hermes:",
            f"    tags: {json.dumps(self._extract_tags(trajectory))}",
            "---",
            "",
            f"# {task}",
            "",
            "## Description",
            "",
            f"Automatically extracted skill from successful completion of: {task}",
            "",
            "## Steps",
            "",
        ]
        
        for i, step in enumerate(steps, 1):
            action = step["action"]
            content_parts.append(f"### {i}. {action}")
            content_parts.append("")
            if step.get("input"):
                content_parts.append("**Input:**")
                content_parts.append("```")
                content_parts.append(str(step["input"]))
                content_parts.append("```")
                content_parts.append("")
            if step.get("output"):
                content_parts.append("**Output:**")
                content_parts.append("```")
                content_parts.append(str(step["output"]))
                content_parts.append("```")
                content_parts.append("")
            if not step["success"]:
                content_parts.append("⚠️ **This step failed in this recording.**")
                content_parts.append("")
        
        content_parts.append("## Complete Example")
        content_parts.append("")
        content_parts.append("See original trajectory for complete execution example.")
        
        return "\n".join(content_parts)
    
    def _extract_tags(self, trajectory: Dict) -> List[str]:
        """Extract tags from trajectory content."""
        task = trajectory["task_description"].lower()
        tags = []
        
        keyword_map = {
            "git": ["git", "commit", "push", "pull", "branch", "merge", "pr"],
            "python": ["python", "pip", "django", "flask"],
            "javascript": ["javascript", "node", "npm", "react", "vue"],
            "testing": ["test", "testing", "unit test", "integration", "ci"],
            "debugging": ["debug", "debugging", "fix", "error", "issue"],
            "database": ["database", "sql", "postgres", "mysql", "sqlite"],
            "web": ["web", "http", "api", "frontend", "backend"],
            "automation": ["automate", "automation", "script", "batch"],
        }
        
        for tag, keywords in keyword_map.items():
            for keyword in keywords:
                if keyword in task:
                    tags.append(tag)
                    break
        
        if not tags:
            tags = ["general"]
        
        return list(set(tags))
    
    def _extract_description_from_content(self, content: str) -> str:
        """Extract description from existing skill content."""
        # Look for description in frontmatter
        match = re.search(r'description:\s*(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        # Fallback to first line after any frontmatter
        lines = content.split("\n")
        for line in lines:
            if line.strip() and not line.strip().startswith("-") and not line.strip().startswith("#"):
                return line.strip()[:100]
        return "Imported skill"
    
    def _extract_tags_from_content(self, content: str) -> List[str]:
        """Extract tags from existing skill content."""
        tags = []
        # Look for hermes metadata tags
        match = re.search(r'tags:\s*\[(.*?)\]', content)
        if match:
            tags_str = match.group(1)
            tags = [t.strip().strip('"\'') for t in tags_str.split(",") if t.strip()]
        return tags
    
    def _analyze_failure(self, failed_step: Dict, trajectory: Dict) -> Dict:
        """Analyze a failed step."""
        return {
            "action": failed_step["action"],
            "input": failed_step["input"],
            "output": failed_step["output"],
            "task_description": trajectory["task_description"],
            "failure_step_index": trajectory["steps"].index(failed_step),
            "total_steps": len(trajectory["steps"]),
        }
    
    def _add_troubleshooting_to_content(self, content: str, failure_analysis: Dict) -> str:
        """Add troubleshooting section to skill content."""
        action = failure_analysis["action"]
        output = failure_analysis["output"]
        
        if "## Troubleshooting" in content:
            # Add to existing troubleshooting
            new_section = f"\n### Common Failure: {action}\n\n"
            new_section += f"When this step fails with:\n```\n{output}\n```\n"
            new_section += "\nCheck the input format and permissions before proceeding.\n"
            
            content = content.replace(
                "## Troubleshooting",
                "## Troubleshooting\n" + new_section
            )
        else:
            # Add new troubleshooting section
            new_section = "\n\n## Troubleshooting\n\n"
            new_section += f"### Common Failure: {action}\n\n"
            new_section += f"Known issue: this step can fail with:\n```\n{output}\n```\n"
            new_section += "\nAlways verify input format and permissions before this step.\n"
            content += new_section
        
        return content
    
    def _bump_patch_version(self, version: str) -> str:
        """Bump patch version: 1.0.0 → 1.0.1"""
        parts = version.split(".")
        if len(parts) == 3:
            parts[2] = str(int(parts[2]) + 1)
            return ".".join(parts)
        elif len(parts) == 2:
            return f"{parts[0]}.{parts[1]}.1"
        else:
            return f"{version}.1"
