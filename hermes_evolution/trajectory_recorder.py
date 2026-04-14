"""
Trajectory Recorder for Hermes-style self-evolution

Records execution trajectories (dialogue, actions, results) for later analysis
and automatic skill extraction.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class TrajectoryRecorder:
    """Records execution trajectories for learning."""
    
    def __init__(self, storage_dir: str = "E:\\juhuo\\hermes_evolution\\trajectories"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.current_trajectory: Optional[Dict] = None
    
    def start_trajectory(
        self,
        task_description: str,
        skill_name: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> str:
        """Start a new trajectory recording."""
        trajectory_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_trajectory = {
            "id": trajectory_id,
            "task_description": task_description,
            "skill_name": skill_name,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "success": None,
            "context": context or {},
            "steps": [],
        }
        return trajectory_id
    
    def add_step(
        self,
        action: str,
        input: Any,
        output: Any,
        success: bool,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Add a step to the current trajectory."""
        if self.current_trajectory is None:
            raise RuntimeError("No trajectory started. Call start_trajectory first.")
        
        step = {
            "action": action,
            "input": input,
            "output": output,
            "success": success,
            "duration_seconds": duration_seconds,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self.current_trajectory["steps"].append(step)
    
    def end_trajectory(self, success: bool, final_result: Optional[Any] = None) -> str:
        """End the current trajectory and save it."""
        if self.current_trajectory is None:
            raise RuntimeError("No trajectory started. Call start_trajectory first.")
        
        self.current_trajectory["end_time"] = datetime.now().isoformat()
        self.current_trajectory["success"] = success
        self.current_trajectory["final_result"] = final_result
        
        trajectory_id = self.current_trajectory["id"]
        file_path = self.storage_dir / f"{trajectory_id}.json"
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.current_trajectory, f, indent=2, ensure_ascii=False)
        
        trajectory_id = self.current_trajectory["id"]
        self.current_trajectory = None
        return trajectory_id
    
    def get_trajectory(self, trajectory_id: str) -> Optional[Dict]:
        """Get a saved trajectory."""
        file_path = self.storage_dir / f"{trajectory_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def list_trajectories(self) -> List[Dict]:
        """List all saved trajectories."""
        trajectories = []
        for file in self.storage_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    trajectories.append({
                        "id": data["id"],
                        "task_description": data["task_description"],
                        "start_time": data["start_time"],
                        "end_time": data["end_time"],
                        "success": data["success"],
                        "steps_count": len(data["steps"]),
                    })
            except Exception:
                continue
        # Sort by start time descending
        trajectories.sort(key=lambda t: t["start_time"], reverse=True)
        return trajectories
    
    def get_failed_trajectories(self) -> List[Dict]:
        """Get all failed trajectories for analysis."""
        all_trajectories = self.list_trajectories()
        return [t for t in all_trajectories if t["success"] is False]
    
    def get_success_rate(self) -> float:
        """Calculate overall success rate."""
        all_trajectories = self.list_trajectories()
        if not all_trajectories:
            return 0.0
        success_count = sum(1 for t in all_trajectories if t["success"])
        return success_count / len(all_trajectories)
    
    def extract_candidates_for_skill(self) -> List[Dict]:
        """Extract candidate trajectories that could be turned into new skills."""
        candidates = []
        all_trajectories = self.list_trajectories()
        
        for traj_info in all_trajectories:
            traj = self.get_trajectory(traj_info["id"])
            if traj is None:
                continue
            
            # Criteria for skill extraction:
            # 1. Successfully completed
            # 2. Multiple steps (more than 3)
            # 3. Specific task description
            if (
                traj["success"] 
                and len(traj["steps"]) >= 3 
                and traj["task_description"] 
                and not traj.get("skill_name")
            ):
                candidates.append(traj)
        
        return candidates
    
    def delete_trajectory(self, trajectory_id: str) -> bool:
        """Delete a trajectory."""
        file_path = self.storage_dir / f"{trajectory_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def cleanup_old(self, keep_days: int = 30) -> int:
        """Clean up old trajectories beyond keep_days."""
        import time
        cutoff = time.time() - (keep_days * 24 * 60 * 60)
        deleted = 0
        
        for file in self.storage_dir.glob("*.json"):
            mtime = file.stat().st_mtime
            if mtime < cutoff:
                file.unlink()
                deleted += 1
        
        return deleted


# ── 全局函数（CoPaw evolver 标准接口）───────────────────────────────────────

TRAJECTORY_FILE = Path(__file__).parent.parent / "data" / "evolutions" / "trajectories.jsonl"
TRAJECTORY_FILE.parent.mkdir(parents=True, exist_ok=True)


def save_trajectory(tool: str, task: str, success: bool, error: str = None, tags: list = None) -> str:
    """
    记录单次工具调用轨迹（失败/成功都记）。
    由 evolver.record() 内联调用，或直接调用。
    """
    import hashlib
    traj_id = hashlib.sha256(f"{tool}{task}{error or ''}".encode()).hexdigest()[:16]
    entry = {
        "traj_id": traj_id,
        "timestamp": datetime.now().isoformat(),
        "tool": tool,
        "task": task[:200] if task else "",
        "success": success,
        "error": error,
        "tags": tags or [],
    }
    with open(TRAJECTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return traj_id


def load_failed_trajectories(limit: int = 50) -> list:
    """读取失败轨迹列表"""
    if not TRAJECTORY_FILE.exists():
        return []
    entries = []
    with open(TRAJECTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if not e.get("success"):
                    entries.append(e)
            except Exception:
                continue
    return sorted(entries, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]


def reflect_on_failures() -> dict:
    """
    分析失败轨迹，按 tool+error 分组，
    相同 pattern 出现 >=2 次生成 lesson。
    """
    failed = load_failed_trajectories(100)
    if not failed:
        return {"lessons": [], "groups": 0, "reflected": 0}

    # 按 (tool, error) 分组
    groups = {}
    for e in failed:
        key = (e.get("tool", ""), e.get("error", "")[:80])
        groups.setdefault(key, []).append(e)

    lessons = []
    for (tool, error), items in groups.items():
        if len(items) < 2:
            continue
        lesson = {
            "type": "trajectory_reflection",
            "tool": tool,
            "error_pattern": error,
            "occurrence": len(items),
            "advice": f"tool={tool}, error='{error[:60]}...' occurred {len(items)} times. Consider checking before use.",
            "timestamp": datetime.now().isoformat(),
        }
        lessons.append(lesson)

    return {"lessons": lessons, "groups": len(groups), "reflected": len(lessons)}


def evolver_update() -> dict:
    """
    定期自进化主函数（由 cron 或手动触发）。
    1. 分析失败轨迹 → 生成 lessons
    2. 统计学习成果
    3. 输出摘要
    """
    reflection = reflect_on_failures()
    failed = load_failed_trajectories(100)
    
    # 写入 lesson 到 evolutions/
    LESSONS_FILE = Path(__file__).parent.parent / "data" / "evolutions" / "self_lessons.jsonl"
    for lesson in reflection.get("lessons", []):
        with open(LESSONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(lesson, ensure_ascii=False) + "\n")

    return {
        "timestamp": datetime.now().isoformat(),
        "failed_count": len(failed),
        "reflection": reflection,
        "lessons_written": len(reflection.get("lessons", [])),
        "status": "ok",
    }
