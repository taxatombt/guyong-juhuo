"""
git_nexus_adapter — GitNexus 图谱感知适配器

集成 gitnexus CLI（npm install -g gitnexus）：
- 自动索引 juhuo 仓库
- 提供 call graph / symbol context / impact 分析
- 将代码变化检测结果写入 perception_intents
- 支持 MCP server 模式供 AI 工具调用

命令速查：
    gitnexus analyze [--force]      # 索引仓库
    gitnexus status                 # 查看索引状态
    gitnexus query <pattern>        # 搜索调用图谱
    gitnexus context <symbol>       # 符号360度视图
    gitnexus impact <symbol>        # 影响范围分析
    gitnexus detect-changes         # git diff → 符号映射
    gitnexus mcp                    # MCP server（stdio模式）
    gitnexus serve [--port N]       # HTTP web UI
    gitnexus wiki [--path]          # 生成项目Wiki
"""

import subprocess
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

# ---- 常量 ----
# Windows 需要完整路径才能找到 .cmd 包装器
if os.name == 'nt':
    _npm_dir = Path.home() / "AppData" / "Roaming" / "npm"
    GITNEXUS_CMD = str(_npm_dir / "gitnexus.cmd")
    # 确保路径存在
    if not Path(GITNEXUS_CMD).exists():
        GITNEXUS_CMD = "gitnexus.cmd"
else:
    GITNEXUS_CMD = "gitnexus"
GITNEXUS_DIR = Path.home() / ".gitnexus"
REGISTRY_FILE = GITNEXUS_DIR / "registry.json"
_JUHUO_ROOT = Path(__file__).parent.parent.resolve()


# ---- 数据结构 ----

@dataclass
class NexusRepo:
    """已索引的仓库"""
    name: str
    path: str
    indexed_at: Optional[str] = None
    file_count: int = 0
    symbol_count: int = 0


@dataclass
class NexusSymbol:
    """代码符号"""
    name: str
    kind: str  # function / class / variable / import
    file: str
    line: int
    signatures: List[str] = field(default_factory=list)


@dataclass
class NexusContext:
    """符号360度视图"""
    symbol: str
    kind: str
    file: str
    line: int
    callers: List[Dict[str, Any]] = field(default_factory=list)
    callees: List[Dict[str, Any]] = field(default_factory=list)
    definition: str = ""


@dataclass
class NexusImpact:
    """影响范围分析"""
    symbol: str
    file: str
    line: int
    blast_radius: int = 0
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    call_depth: int = 0


# ---- 核心功能 ----

def _run(args: List[str], timeout: int = 60, cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """
    运行 gitnexus 命令。
    返回 (returncode, stdout, stderr)
    """
    cmd = [GITNEXUS_CMD] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd or str(_JUHUO_ROOT),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timeout after {timeout}s"
    except FileNotFoundError:
        return -2, "", f"gitnexus not found. Run: npm install -g gitnexus"
    except Exception as e:
        return -3, "", str(e)


def is_available() -> bool:
    """检查 gitnexus 是否可用"""
    rc, _, _ = _run(["--version"], timeout=5)
    return rc == 0


def analyze(path: Optional[str] = None, force: bool = False,
           embeddings: bool = False) -> Dict[str, Any]:
    """
    索引仓库，生成 AST + 调用图谱。

    Args:
        path: 仓库路径，None 则用 juhuo 根目录
        force: 强制重新索引
        embeddings: 生成语义向量（用于语义搜索）

    Returns:
        {"success": bool, "message": str, "stats": dict}
    """
    target = path or str(_JUHUO_ROOT)
    args = ["analyze"]
    if force:
        args.append("--force")
    if embeddings:
        args.append("--embeddings")
    args.append(target)

    rc, stdout, stderr = _run(args, timeout=300, cwd=target)

    stats = {}
    # 尝试从输出中提取统计信息
    for line in stdout.splitlines():
        m = re.search(r"(\d+)\s*files?", line, re.IGNORECASE)
        if m:
            stats["files"] = int(m.group(1))
        m = re.search(r"(\d+)\s*symbols?", line, re.IGNORECASE)
        if m:
            stats["symbols"] = int(m.group(1))

    if rc == 0:
        return {"success": True, "message": "分析完成", "stats": stats}
    else:
        return {"success": False, "message": stderr or stdout, "stats": stats}


def status(path: Optional[str] = None) -> Dict[str, Any]:
    """查看索引状态"""
    target = path or str(_JUHUO_ROOT)
    rc, stdout, stderr = _run(["status"], timeout=10, cwd=target)
    return {
        "success": rc == 0,
        "output": stdout + stderr,
    }


def query_graph(search_query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    搜索调用图谱，返回匹配的执行流。

    Returns:
        List[{"file": str, "line": int, "symbol": str, "snippet": str, "context": str}]
    """
    rc, stdout, stderr = _run(
        ["query", "--limit", str(limit), search_query],
        timeout=30,
    )
    if rc != 0:
        return []

    results = []
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            results = data
        elif isinstance(data, dict) and "results" in data:
            results = data["results"]
    except json.JSONDecodeError:
        # 非JSON输出，手动解析
        results = _parse_query_output(stdout)

    return results


def _parse_query_output(text: str) -> List[Dict[str, Any]]:
    """解析 gitnexus query 的文本输出"""
    results = []
    current = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " -> " in line:
            # 调用链格式: caller -> callee
            parts = line.split("->", 1)
            current = {"caller": parts[0].strip(), "callee": parts[1].strip()}
            results.append(current)
        elif ":" in line and not line.startswith("["):
            # 文件:行号 格式
            m = re.match(r"(.+?):(\d+)(?::(.*))?", line)
            if m:
                current["file"] = m.group(1).strip()
                current["line"] = int(m.group(2))
                if m.group(3):
                    current["snippet"] = m.group(3).strip()
    return results


def symbol_context(symbol: str, path: Optional[str] = None) -> NexusContext:
    """
    获取符号的360度视图：调用者、被调用者、定义位置。
    """
    target = path or str(_JUHUO_ROOT)
    rc, stdout, stderr = _run(
        ["context", symbol],
        timeout=30,
        cwd=target,
    )

    ctx = NexusContext(symbol=symbol, kind="unknown", file="", line=0)

    if rc == 0:
        try:
            data = json.loads(stdout)
            ctx = NexusContext(
                symbol=data.get("symbol", symbol),
                kind=data.get("kind", "unknown"),
                file=data.get("file", ""),
                line=data.get("line", 0),
                callers=data.get("callers", []),
                callees=data.get("callees", []),
                definition=data.get("definition", ""),
            )
        except json.JSONDecodeError:
            _parse_context_output(stdout, ctx)

    return ctx


def _parse_context_output(text: str, ctx: NexusContext) -> None:
    """解析 context 命令的文本输出"""
    in_callers = False
    in_callees = False
    for line in text.splitlines():
        line = line.strip()
        if "callers" in line.lower():
            in_callers = True
            in_callees = False
        elif "callees" in line.lower():
            in_callees = True
            in_callers = False
        elif "::" in line:
            parts = line.split("::", 1)
            entry = {"file": parts[0].strip(), "symbol": parts[1].strip()}
            if in_callers:
                ctx.callers.append(entry)
            elif in_callees:
                ctx.callees.append(entry)

def symbol_impact(symbol: str, path: Optional[str] = None,
                  max_depth: int = 3):
    target = path or str(_JUHUO_ROOT)
    rc, stdout, stderr = _run(
        ['impact', '--max-depth', str(max_depth), symbol],
        timeout=30, cwd=target)
    impact = NexusImpact(symbol=symbol, file='', line=0)
    if rc == 0:
        try:
            data = json.loads(stdout)
            impact = NexusImpact(
                symbol=data.get('symbol', symbol),
                file=data.get('file', ''),
                line=data.get('line', 0),
                blast_radius=data.get('blast_radius', 0),
                affected_files=data.get('affected_files', []),
                affected_symbols=data.get('affected_symbols', []),
                call_depth=data.get('call_depth', 0))
        except json.JSONDecodeError:
            _parse_impact_output(stdout, impact)
    return impact

def _parse_impact_output(text: str, impact: NexusImpact):
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        if line.endswith('.py') or line.endswith('.ts') or '/' in line:
            impact.affected_files.append(line)
        elif '->' in line:
            for p in line.split('->'):
                s = p.strip()
                if s and s not in impact.affected_symbols:
                    impact.affected_symbols.append(s)

def detect_changes(path: Optional[str] = None) -> List[Dict[str, Any]]:
    target = path or str(_JUHUO_ROOT)
    rc1, du, _ = _run(['diff', '--no-color'], timeout=10, cwd=target)
    rc2, dc, _ = _run(['diff', '--cached', '--no-color'], timeout=10, cwd=target)
    diff_all = (du + dc) if (rc1 == 0 or rc2 == 0) else ''
    if not diff_all.strip(): return []
    rc, stdout, stderr = _run(['detect-changes'], timeout=30, cwd=target)
    results = []
    if rc == 0:
        try:
            results = json.loads(stdout)
            if not isinstance(results, list): results = results.get('results', [])
        except json.JSONDecodeError:
            results = _parse_changes_output(stdout)
    return results

def _parse_changes_output(text: str) -> List[Dict[str, Any]]:
    results, current = [], {}
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        if line.startswith('---') or line.startswith('+++'):
            if current and 'file' in current: results.append(current)
            f = line.replace('--- ', '').replace('+++ ', '').strip()
            if f and f != '/dev/null': current = {'file': f, 'hunks': [], 'impact': []}
        elif line.startswith('@@'):
            m = re.search(r'\+(\d+)', line)
            if m: current.setdefault('hunks', []).append({'line': int(m.group(1)), 'symbols': []})
        elif '->' in line and current:
            current.setdefault('impact', []).append(line)
    if current and 'file' in current: results.append(current)
    return results

def generate_wiki(path: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    target = path or str(_JUHUO_ROOT)
    args = ['wiki', target]
    if model: args.extend(['--model', model])
    rc, stdout, stderr = _run(args, timeout=120, cwd=target)
    return {'success': rc == 0, 'message': stderr or stdout}

def list_repos() -> List[NexusRepo]:
    if not REGISTRY_FILE.exists(): return []
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding='utf-8'))
        repos = data if isinstance(data, list) else data.get('repos', [])
        return [NexusRepo(**r) for r in repos]
    except (json.JSONDecodeError, TypeError): return []

def index_juhuo(force: bool = False) -> Dict[str, Any]:
    return analyze(str(_JUHUO_ROOT), force=force)

def save_to_perception_intents(symbols: List[str],
                               reason: str = "代码变化检测",
                               source: str = "git_nexus") -> None:
    try:
        from judgment.user_model import save_perception_result
        for sym in symbols[:20]:
            save_perception_result(
                source=source,
                topic="代码符号: " + sym,
                content="影响分析触发词: " + sym + "。原因: " + reason,
                priority=3)
    except Exception as e:
        import sys; print("save_to_perception_intents failed: " + str(e), file=sys.stderr)

def context_for_judgment(query: str, limit: int = 5) -> str:
    results = query_graph(query, limit=limit)
    if not results: return ""
    lines = ["【代码图谱】" + str(len(results)) + " 条相关调用链:"]
    for r in results[:limit]:
        if isinstance(r, dict):
            caller = r.get('caller', '')
            callee = r.get('callee', '')
            file_l = r.get('file', '')
            if caller and callee: lines.append("  " + caller + " -> " + callee)
            elif file_l: lines.append("  " + file_l + ":" + str(r.get('line', '?')))
        elif isinstance(r, str): lines.append("  " + r)
    return chr(10).join(lines)

_mcp_proc = None

def start_mcp_server():
    global _mcp_proc
    _mcp_proc = subprocess.Popen(
        [GITNEXUS_CMD, 'mcp'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding='utf-8',
        cwd=str(_JUHUO_ROOT))
    return _mcp_proc

def stop_mcp_server():
    global _mcp_proc
    if _mcp_proc:
        _mcp_proc.terminate()
        _mcp_proc = None

_background_thread = None
_stop_flag = threading.Event()

def _background_update(interval=300):
    while not _stop_flag.is_set():
        if _stop_flag.wait(interval): break
        try:
            rc, _, _ = _run(['diff', '--quiet'], timeout=10)
            if rc != 0: analyze(str(_JUHUO_ROOT), force=False)
        except: pass

def start_auto_update(interval=300):
    global _background_thread, _stop_flag
    _stop_flag.clear()
    _background_thread = threading.Thread(
        target=_background_update, args=(interval,), daemon=True,
        name='gitnexus-auto-update')
    _background_thread.start()

def stop_auto_update():
    global _background_thread, _stop_flag
    if _background_thread:
        _stop_flag.set()
        _background_thread.join(timeout=5)
        _background_thread = None


# ---- MCP / Web UI ----
_mcp_proc = None
_ui_proc = None


def start_web_ui(port: int = 54321) -> subprocess.Popen:
    """启动 GitNexus Web UI HTTP 服务器"""
    global _ui_proc
    _ui_proc = subprocess.Popen(
        [GITNEXUS_CMD, "serve", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=str(_JUHUO_ROOT),
    )
    return _ui_proc


def stop_web_ui():
    global _ui_proc
    if _ui_proc:
        _ui_proc.terminate()
        _ui_proc = None
