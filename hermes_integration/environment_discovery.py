"""
Hermes-Agent Environment Discovery — AST 自动环境发现

逆向自 NousResearch/Hermes-Agent RL 训练工具：
- AST-based scanning 自动发现目录中的 BaseEnv 子类
- 动态导入环境类
- 配置文件生成
- 用于 RL from Experience 训练

适配聚活：
- 自动发现用户自定义技能模块
- 自动发现判断维度扩展
- 自动发现环境类用于 RL 训练
"""

import ast
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Type

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .utils import get_juhuo_root


@dataclass
class EnvironmentInfo:
    """发现的环境/模块信息"""
    name: str
    file_path: Path
    class_name: str
    base_classes: List[str]
    docstring: Optional[str]
    line_count: int
    
    def to_dict(self):
        return {
            "name": self.name,
            "file_path": str(self.file_path),
            "class_name": self.class_name,
            "base_classes": self.base_classes,
            "docstring": self.docstring,
            "line_count": self.line_count
        }


class EnvironmentDiscovery:
    """AST-based environment discovery
    
    Scans directories for subclasses of a given base class,
    without importing them first (safer, avoids side effects).
    """
    
    def __init__(self, root_dir: Path = None):
        self.root_dir = root_dir or get_juhuo_root()
    
    def find_subclasses(
        self,
        base_class_name: str,
        search_dir: Optional[Path] = None,
        file_pattern: str = "*.py"
    ) -> List[EnvironmentInfo]:
        """Find all subclasses of base_class_name using AST scanning."""
        directory = search_dir or self.root_dir
        found = []
        
        for py_file in directory.rglob(file_pattern):
            # Skip __pycache__, hidden dirs, venv etc.
            if any(part.startswith(("_", ".")) for part in py_file.parts):
                continue
            if "venv" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            if "node_modules" in py_file.parts:
                continue
            
            try:
                found.extend(self._scan_file(py_file, base_class_name))
            except Exception as e:
                continue
        
        return found
    
    def _scan_file(self, file_path: Path, base_class_name: str) -> List[EnvironmentInfo]:
        """Scan a single Python file for subclasses."""
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
        
        found = []
        lines = content.count("\n")
        
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            
            # Check bases
            base_names = []
            found_target = False
            for base in node.bases:
                name = self._get_name_from_node(base)
                if name:
                    base_names.append(name)
                    if name == base_class_name:
                        found_target = True
            
            if found_target:
                docstring = ast.get_docstring(node)
                info = EnvironmentInfo(
                    name=node.name,
                    file_path=file_path,
                    class_name=node.name,
                    base_classes=base_names,
                    docstring=docstring,
                    line_count=lines
                )
                found.append(info)
        
        return found
    
    def _get_name_from_node(self, node: ast.AST) -> Optional[str]:
        """Extract class name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            # Handle case like 'metaclass=abc.ABCMeta'
            return None
        return None
    
    def load_environment_class(self, info: EnvironmentInfo) -> Optional[Type]:
        """Dynamically load the discovered environment class."""
        try:
            # Add parent directory to path
            parent_dir = info.file_path.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))
            
            # Import module
            module_name = info.file_path.stem
            spec = importlib.util.spec_from_file_location(
                module_name, info.file_path
            )
            if spec is None or spec.loader is None:
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Get the class
            if hasattr(module, info.class_name):
                return getattr(module, info.class_name)
            
            # Search in module for any class that matches
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and attr_name == info.class_name:
                    return attr
            
            return None
        
        except Exception as e:
            return None


def discover_environments(
    base_class_name: str = "BaseEnv",
    search_dir: Optional[Path] = None
) -> List[EnvironmentInfo]:
    """Convenience function to discover environments."""
    discovery = EnvironmentDiscovery(search_dir)
    return discovery.find_subclasses(base_class_name)
