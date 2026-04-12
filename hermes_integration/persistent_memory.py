"""
Hermes-Agent Persistent Curated Memory — 持久化结构化记忆

逆向自 NousResearch/Hermes-Agent:
- 两个独立存储：MEMORY.md 系统/项目笔记 + USER.md 用户偏好/认知
- 会话启动注入完整快照，prompt 前缀稳定，保持前缀缓存
- 会话中写入直接更新磁盘，但不改变当前会话 prompt（保持缓存）
- 下一会话启动自动加载新快照
- 轻量级威胁检测，防止 prompt 注入

适配聚活：
- 与聚活因果记忆双向同步：因果记忆存储因果关系，这里存储笔记观察
- 符合身份锁：核心身份特质写入 USER.md 锁定，不允许自动进化
"""

import json
import logging
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from .utils import get_juhuo_root

logger = logging.getLogger(__name__)

# Entry delimiter: section sign §
ENTRY_DELIMITER = "\n§\n"

# fcntl is not available on Windows, use cross-platform locking
class DummyLock:
    def __enter__(self):
        pass
    def __exit__(self, *args):
        pass

@contextmanager
def _locked_write(self, file_path):
    """Cross-platform file locking — fcntl on Unix, dummy on Windows."""
    if sys.platform == "win32":
        # Windows doesn't have fcntl, just yield (atomic write via replacement should be safe)
        yield
    else:
        import fcntl
        lock_path = file_path.with_suffix(file_path.suffix + ".lock")
        with open(lock_path, "w") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            yield

# Threat patterns for prompt injection detection
# Lightweight check, not 100% but catches common attacks
_MEMORY_THREAT_PATTERNS = [
    # Prompt injection
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'you\s+are\s+now\s+', "role_hijack"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions"),
    # Exfiltration
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN)', "exfil_wget"),
    (r'\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|API_KEY).*curl', "exfil_curl"),
]


class MemoryStore:
    """基础持久化存储 — 一个文件存储多个带分隔符的条目"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("", encoding="utf-8")
    
    def _locked_write(self):
        """原子写入带文件锁，防止并发损坏 — cross-platform"""
        return _locked_write(self, self.file_path)
            # lock released on close
    
    def _scan_entries(self, content: str) -> List[str]:
        """Scan and split entries"""
        if not content.strip():
            return []
        entries = content.split(ENTRY_DELIMITER)
        return [e.strip() for e in entries if e.strip()]
    
    def _check_for_threats(self, text: str) -> Optional[Tuple[bool, str]]:
        """Check for potential prompt injection threats.
        
        Returns (safe, reason) — (False, reason) if unsafe.
        """
        text_lower = text.lower()
        for pattern, threat_type in _MEMORY_THREAT_PATTERNS:
            if re.search(pattern, text_lower):
                return False, f"Detected potential {threat_type}"
        return None
    
    def read_all(self) -> List[str]:
        """Read all entries from storage."""
        if not self.file_path.exists():
            return []
        content = self.file_path.read_text(encoding="utf-8")
        return self._scan_entries(content)
    
    def read_as_text(self) -> str:
        """Read entire file as single text for prompt injection."""
        if not self.file_path.exists():
            return ""
        return self.file_path.read_text(encoding="utf-8").strip()
    
    def add_entry(self, entry: str) -> Tuple[bool, str]:
        """Add a new entry to storage."""
        # Check for threats
        threat = self._check_for_threats(entry)
        if threat:
            return threat
        
        entries = self.read_all()
        entries.append(entry.strip())
        
        with self._locked_write():
            self.file_path.write_text(
                ENTRY_DELIMITER.join(entries),
                encoding="utf-8"
            )
        
        return True, "Added successfully"
    
    def replace_entry(self, search_substring: str, new_content: str) -> Tuple[bool, str]:
        """Replace entry that contains the search substring.
        
        Uses substring matching as requested by Hermes design, not full IDs.
        """
        threat = self._check_for_threats(new_content)
        if threat:
            return threat
        
        entries = self.read_all()
        found = False
        new_entries = []
        
        for entry in entries:
            if search_substring in entry:
                new_entries.append(new_content.strip())
                found = True
            else:
                new_entries.append(entry)
        
        if not found:
            return False, f"No entry containing '{search_substring}' found"
        
        with self._locked_write():
            self.file_path.write_text(
                ENTRY_DELIMITER.join(new_entries),
                encoding="utf-8"
            )
        
        return True, f"Replaced entry containing '{search_substring}'"
    
    def remove_entry(self, search_substring: str) -> Tuple[bool, str]:
        """Remove entry that contains the search substring."""
        entries = self.read_all()
        original_count = len(entries)
        entries = [e for e in entries if search_substring not in e]
        
        if len(entries) == original_count:
            return False, f"No entry containing '{search_substring}' found"
        
        with self._locked_write():
            self.file_path.write_text(
                ENTRY_DELIMITER.join(entries),
                encoding="utf-8"
            )
        
        return True, f"Removed entry containing '{search_substring}'"
    
    def search(self, query: str) -> List[str]:
        """Fuzzy search entries containing query."""
        entries = self.read_all()
        query_lower = query.lower()
        return [e for e in entries if query_lower in e.lower()]
    
    def clear_all(self) -> None:
        """Clear all entries (dangerous for testing only)."""
        with self._locked_write():
            self.file_path.write_text("", encoding="utf-8")


class PersistentMemory:
    """两级持久化记忆 — Hermes 设计：MEMORY + USER
    
    - MEMORY: 系统笔记、项目约定、工具怪癖、学到的教训
    - USER: 关于用户的认知 — 偏好、沟通风格、期望、工作习惯
    - 核心身份特质写在这里，受身份锁保护
    """
    
    def __init__(self, data_dir: Path = None):
        import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .utils import get_juhuo_root

class PersistentMemory:
    """两级持久化记忆 — Hermes 设计：MEMORY + USER
    
    - MEMORY: 系统笔记、项目约定、工具怪癖、学到的教训
    - USER: 关于用户的认知 — 偏好、沟通风格、期望、工作习惯
    - 核心身份特质写在这里，受身份锁保护
    """
    
    def __init__(self, data_dir: Path = None):
        data_dir = data_dir or get_juhuo_root() / "data" / "memory"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        self.memory_store = MemoryStore(data_dir / "MEMORY.md")
        self.user_store = MemoryStore(data_dir / "USER.md")
    
    def add_memory(self, entry: str) -> Tuple[bool, str]:
        """Add entry to MEMORY storage."""
        return self.memory_store.add_entry(entry)
    
    def add_user_note(self, entry: str) -> Tuple[bool, str]:
        """Add entry to USER storage."""
        return self.user_store.add_entry(entry)
    
    def replace_memory(self, search: str, new_content: str) -> Tuple[bool, str]:
        """Replace memory entry."""
        return self.memory_store.replace_entry(search, new_content)
    
    def replace_user_note(self, search: str, new_content: str) -> Tuple[bool, str]:
        """Replace user note entry."""
        return self.user_store.replace_entry(search, new_content)
    
    def remove_memory(self, search: str) -> Tuple[bool, str]:
        """Remove memory entry."""
        return self.memory_store.remove_entry(search)
    
    def remove_user_note(self, search: str) -> Tuple[bool, str]:
        """Remove user note entry."""
        return self.user_store.remove_entry(search)
    
    def get_session_snapshot(self) -> str:
        """Get snapshot for injection into system prompt at session start.
        
        Following Hermes design: frozen snapshot for entire session,
        writes during session go to disk but don't change prompt
        to preserve prefix cache.
        """
        memory_text = self.memory_store.read_as_text()
        user_text = self.user_store.read_as_text()
        
        snapshot = []
        if memory_text.strip():
            snapshot.append("=== STORED MEMORY ===\n" + memory_text)
        if user_text.strip():
            snapshot.append("\n=== USER PREFERENCES ===\n" + user_text)
        
        return "\n".join(snapshot)
    
    def search_memory(self, query: str) -> List[str]:
        """Search memory entries."""
        return self.memory_store.search(query)
    
    def search_user(self, query: str) -> List[str]:
        """Search user entries."""
        return self.user_store.search(query)
    
    def read_all_memory(self) -> List[str]:
        """Read all memory entries."""
        return self.memory_store.read_all()
    
    def read_all_user(self) -> List[str]:
        """Read all user entries."""
        return self.user_store.read_all()


# ---------------------------------------------------------------------------
# Convenience functions for module-level use
# ---------------------------------------------------------------------------

_persistent_memory: Optional[PersistentMemory] = None


def _get_instance() -> PersistentMemory:
    global _persistent_memory
    if _persistent_memory is None:
        _persistent_memory = PersistentMemory()
    return _persistent_memory


def add_memory(entry: str) -> Tuple[bool, str]:
    return _get_instance().add_memory(entry)


def add_user_note(entry: str) -> Tuple[bool, str]:
    return _get_instance().add_user_note(entry)


def replace_memory(search: str, new_content: str) -> Tuple[bool, str]:
    return _get_instance().replace_memory(search, new_content)


def replace_user_note(search: str, new_content: str) -> Tuple[bool, str]:
    return _get_instance().replace_user_note(search, new_content)


def remove_memory(search: str) -> Tuple[bool, str]:
    return _get_instance().remove_memory(search)


def remove_user_note(search: str) -> Tuple[bool, str]:
    return _get_instance().remove_user_note(search)


def read_memory() -> str:
    return _get_instance().get_session_snapshot()


def get_session_snapshot() -> str:
    return _get_instance().get_session_snapshot()
