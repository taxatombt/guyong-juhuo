"""
Hermes-Agent Checkpoint Manager — 透明文件系统快照

逆向自 NousResearch/Hermes-Agent:
- 变异操作（write_file/patch）前自动快照
- 支持一键回滚到任意快照
- 使用阴影 git 仓库，不污染用户项目 git
- 兼容聚活 OpenSpace 全系统版本快照

核心设计点：
- GIT_DIR + GIT_WORK_TREE 分离：快照存 ~/.juhuo/checkpoints，不碰工作区
- 每轮对话自动触发一次快照（触发一次变异操作）
- 排除默认忽略模式（node_modules, venv, __pycache__, logs 等）
- 支持按时间和目录查询，支持回滚任意提交
"""

import hashlib
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .utils import get_juhuo_root

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHECKPOINT_BASE = get_juhuo_root() / "data" / "checkpoints"

DEFAULT_EXCLUDES = [
    "node_modules/",
    "dist/",
    "build/",
    ".env",
    ".env.*",
    ".env.*.local",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.log",
    ".cache/",
    ".next/",
    ".nuxt/",
    "coverage/",
    ".pytest_cache/",
    ".venv/",
    "venv/",
    ".git/",
    ".DS_Store",
    "*.tmp",
    "*.temp",
    "data/hermes_experience/",
    "data/checkpoints/",
    "__pycache__/",
]

# Git subprocess timeout (seconds)
_GIT_TIMEOUT: int = max(10, min(60, int(os.getenv("JUHUO_CHECKPOINT_TIMEOUT", "30"))))

# Max files to snapshot — skip huge directories to avoid slowdowns.
_MAX_FILES = 50_000

# Valid git commit hash pattern
_COMMIT_HASH_RE = re.compile(r'^[0-9a-fA-F]{4,64}$')


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def _validate_commit_hash(commit_hash: str) -> Optional[str]:
    """Validate a commit hash to prevent git argument injection."""
    if not commit_hash or not commit_hash.strip():
        return "Empty commit hash"
    if commit_hash.startswith("-"):
        return f"Invalid commit hash (must not start with '-'): {commit_hash!r}"
    if not _COMMIT_HASH_RE.match(commit_hash):
        return f"Invalid commit hash (expected 4-64 hex characters): {commit_hash!r}"
    return None


def _get_shadow_dir(work_dir: Path) -> Path:
    """Get shadow git directory for a working directory."""
    dir_hash = hashlib.sha256(str(work_dir.resolve()).encode()).hexdigest()[:16]
    return CHECKPOINT_BASE / dir_hash


class CheckpointManager:
    """透明检查点管理器 — 自动快照文件系统，支持回滚
    
    使用：
    ```python
    from hermes_integration.checkpoint_manager import CheckpointManager
    cm = CheckpointManager(Path("."))
    cm.ensure_initialized()
    commit_hash = cm.create_checkpoint("Before modifying main.py")
    # 如果改坏了，回滚：
    cm.rollback_to_checkpoint(commit_hash)
    ```
    """
    
    def __init__(self, work_dir: Path = None):
        self.work_dir = work_dir or get_juhuo_root()
        self.shadow_dir = _get_shadow_dir(self.work_dir)
        self._initialized = False
    
    def ensure_initialized(self) -> bool:
        """确保阴影仓库已初始化"""
        if self._initialized:
            return True
        
        CHECKPOINT_BASE.mkdir(parents=True, exist_ok=True)
        
        if not (self.shadow_dir / "HEAD").exists():
            self.shadow_dir.mkdir(parents=True, exist_ok=True)
            result = self._git_cmd(["init", "--bare"], capture_output=True)
            if result[0] != 0:
                logger.error(f"Failed to init shadow git: {result[1]}")
                return False
            
            # Write original workdir path for recovery
            with open(self.shadow_dir / "HERMES_WORKDIR", "w") as f:
                f.write(str(self.work_dir.resolve()) + "\n")
            
            # Create default excludes
            with open(self.shadow_dir / "info" / "exclude", "w") as f:
                for pattern in DEFAULT_EXCLUDES:
                    f.write(pattern + "\n")
        
        self._initialized = True
        return True
    
    def _git_cmd(self, args: List[str], capture_output: bool = False) -> Tuple[int, str]:
        """Run git command in shadow git directory."""
        env = os.environ.copy()
        env["GIT_DIR"] = str(self.shadow_dir)
        env["GIT_WORK_TREE"] = str(self.work_dir)
        
        try:
            result = subprocess.run(
                ["git"] + args,
                env=env,
                capture_output=capture_output,
                text=True,
                timeout=_GIT_TIMEOUT
            )
            if capture_output:
                return result.returncode, (result.stdout + result.stderr)
            return result.returncode, ""
        except subprocess.TimeoutExpired:
            return 124, "timeout"
    
    def is_clean(self) -> bool:
        """Check if working directory has no changes vs last checkpoint."""
        if not self.ensure_initialized():
            return False
        code, _ = self._git_cmd(["diff --quiet"], capture_output=True)
        # 0 = no changes, 1 = changes
        return code == 0
    
    def create_checkpoint(self, message: str) -> Optional[str]:
        """Create a new checkpoint (snapshot) of current working directory.
        
        Returns:
            commit hash if successful, None otherwise
        """
        if not self.ensure_initialized():
            return None
        
        # Add all changes
        code, output = self._git_cmd(["add", "."], capture_output=True)
        if code != 0:
            logger.error(f"git add failed: {output}")
            return None
        
        # Check if anything changed
        if self.is_clean():
            logger.debug("No changes to checkpoint")
            # Still return HEAD hash
            code, head = self._git_cmd(["rev-parse", "HEAD"], capture_output=True)
            if code == 0:
                return head.strip()
            return None
        
        # Commit
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"{message} — {timestamp}"
        code, output = self._git_cmd(["commit", "-m", commit_msg], capture_output=True)
        
        if code != 0 and "nothing to commit" not in output:
            logger.warning(f"git commit gave code {code}: {output}")
        
        # Get commit hash
        code, commit_hash = self._git_cmd(["rev-parse", "HEAD"], capture_output=True)
        if code != 0:
            return None
        
        return commit_hash.strip()
    
    def list_checkpoints(self, max_count: int = 20) -> List[Dict[str, str]]:
        """List recent checkpoints with their messages."""
        if not self.ensure_initialized():
            return []
        
        code, output = self._git_cmd(
            ["log", "--pretty=format:%h | %s | %ci", f"-{max_count}"],
            capture_output=True
        )
        if code != 0:
            return []
        
        result = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(" | ", 2)
            if len(parts) == 3:
                result.append({
                    "short_hash": parts[0],
                    "message": parts[1],
                    "date": parts[2]
                })
        return result
    
    def rollback_to_checkpoint(self, commit_hash: str) -> Tuple[bool, str]:
        """Rollback working directory to a specific checkpoint.
        
        Returns:
            (success, message)
        """
        error = _validate_commit_hash(commit_hash)
        if error:
            return False, error
        
        if not self.ensure_initialized():
            return False, "Failed to initialize checkpoint manager"
        
        # Verify commit exists
        code, _ = self._git_cmd(["cat-file", "-e", f"{commit_hash}^{{commit}}"], capture_output=True)
        if code != 0:
            return False, f"Commit {commit_hash} not found"
        
        # Hard reset to commit
        code, output = self._git_cmd(["reset", "--hard", commit_hash], capture_output=True)
        if code != 0:
            return False, f"Reset failed: {output}"
        
        # Clean untracked files (respecting .gitignore/exclude)
        self._git_cmd(["clean", "-fd"], capture_output=False)
        
        return True, f"Successfully rolled back to {commit_hash[:8]}"
    
    def diff(self, commit_hash: str) -> Optional[str]:
        """Get diff between current working directory and a checkpoint."""
        error = _validate_commit_hash(commit_hash)
        if error:
            return None
        
        if not self.ensure_initialized():
            return None
        
        code, output = self._git_cmd(["diff", commit_hash], capture_output=True)
        return output


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def create_checkpoint(message: str, work_dir: Path = None) -> Optional[str]:
    """Convenience: create a checkpoint"""
    cm = CheckpointManager(work_dir)
    return cm.create_checkpoint(message)


def rollback_to_checkpoint(commit_hash: str, work_dir: Path = None) -> Tuple[bool, str]:
    """Convenience: rollback to checkpoint"""
    cm = CheckpointManager(work_dir)
    return cm.rollback_to_checkpoint(commit_hash)


def list_checkpoints(work_dir: Path = None, max_count: int = 20) -> List[Dict[str, str]]:
    """Convenience: list checkpoints"""
    cm = CheckpointManager(work_dir)
    return cm.list_checkpoints(max_count)
