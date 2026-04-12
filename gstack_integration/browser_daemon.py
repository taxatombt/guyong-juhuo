"""
gstack Browser Daemon Integration
Adopted from garrytan/gstack browse architecture
- Long-lived Chromium daemon for persistent state (cookies, tabs, login sessions)
- Sub-100ms command latency after initial startup
- Ref-based element addressing (no CSS selectors needed)
- Security: localhost-only + bearer token auth
"""

import json
import os
import platform
import socket
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import requests


class BrowserState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class BrowserDaemonConfig:
    """Configuration for the browser daemon"""
    port_range_start: int = 10000
    port_range_end: int = 60000
    idle_timeout_minutes: int = 30
    data_dir: str = ".gstack"
    binary_version: Optional[str] = None


@dataclass
class BrowserDaemonState:
    """Persistent state of the browser daemon"""
    pid: Optional[int] = None
    port: Optional[int] = None
    token: Optional[str] = None
    started_at: Optional[str] = None
    binary_version: Optional[str] = None


class BrowserDaemonClient:
    """Client for connecting to a running gstack browser daemon"""

    def __init__(
        self,
        state_file: Optional[str] = None,
        config: Optional[BrowserDaemonConfig] = None,
    ):
        self.state_file = state_file or os.path.join(
            os.getcwd(), ".gstack", "browse.json"
        )
        self.config = config or BrowserDaemonConfig()
        self._state: Optional[BrowserDaemonState] = None
        self._load_state()

    def _load_state(self) -> None:
        """Load state from disk"""
        if not os.path.exists(self.state_file):
            self._state = None
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._state = BrowserDaemonState(**data)
        except Exception:
            self._state = None

    def _save_state(self) -> None:
        """Save state to disk (atomic)"""
        if self._state is None:
            return

        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        # Atomic write: write to temp then rename
        tmp_file = self.state_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(self._state.__dict__, f, indent=2)
        os.replace(tmp_file, self.state_file)
        # Set permissions to owner-only
        try:
            os.chmod(self.state_file, 0o600)
        except Exception:
            pass  # Windows doesn't always respect this

    def _find_available_port(self) -> int:
        """Find an available port in the configured range"""
        import random
        ports = list(range(self.config.port_range_start, self.config.port_range_end))
        random.shuffle(ports)

        for port in ports[:5]:  # retry up to 5 times
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(("127.0.0.1", port))
                s.close()
                return port
            except OSError:
                continue
        raise RuntimeError("No available ports found in the configured range")

    def _is_server_running(self) -> bool:
        """Check if the server is actually responding"""
        if self._state is None or self._state.port is None or self._state.token is None:
            return False

        try:
            response = requests.get(
                f"http://127.0.0.1:{self._state.port}/health",
                timeout=1.0,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def _kill_old_server(self) -> None:
        """Kill the old server if it's running"""
        if self._state is None or self._state.pid is None:
            return

        try:
            if platform.system() == "Windows":
                subprocess.run(
                    ["taskkill", "/PID", str(self._state.pid), "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                subprocess.run(
                    ["kill", str(self._state.pid)],
                    capture_output=True,
                    check=False,
                )
        except Exception:
            pass  # already dead

        time.sleep(0.5)

    def start(self, binary_path: Optional[str] = None) -> int:
        """
        Start the browser daemon
        Returns the port number
        """
        # Check if already running
        if self._is_server_running():
            assert self._state is not None
            assert self._state.port is not None
            return self._state.port

        # Kill any stale server
        self._kill_old_server()

        # Find available port
        port = self._find_available_port()
        token = str(uuid.uuid4())
        version = self.config.binary_version or "unknown"

        # Start the server
        # Note: In the real gstack, this is the compiled bun binary
        # For Juhuo integration, we expect the server to be available
        # We're documenting the architecture for integration
        if binary_path is None:
            # Try to find it in common locations
            if platform.system() == "Windows":
                possible_paths = [
                    os.path.expanduser("~/.claude/skills/gstack/browse/dist/browse.exe"),
                    os.path.expanduser("~/.gstack/browse/dist/browse.exe"),
                ]
            else:
                possible_paths = [
                    os.path.expanduser("~/.claude/skills/gstack/browse/dist/browse"),
                    os.path.expanduser("~/.gstack/browse/dist/browse"),
                ]
            for path in possible_paths:
                if os.path.exists(path):
                    binary_path = path
                    break

        if binary_path is None or not os.path.exists(binary_path):
            raise RuntimeError(
                "gstack browser binary not found. Please install gstack first:\n"
                "git clone --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack\n"
                "cd ~/.claude/skills/gstack && ./setup"
            )

        # Start the daemon in background
        env = os.environ.copy()
        env["GSTACK_BROWSE_PORT"] = str(port)
        env["GSTACK_BROWSE_TOKEN"] = token

        if platform.system() == "Windows":
            # Windows: start detached
            creationflags = subprocess.CREATE_NO_WINDOW
            process = subprocess.Popen(
                [binary_path],
                env=env,
                creationflags=creationflags,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(binary_path),
            )
        else:
            # Unix: nohup background
            process = subprocess.Popen(
                [binary_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
                cwd=os.path.dirname(binary_path),
            )

        # Save state
        self._state = BrowserDaemonState(
            pid=process.pid,
            port=port,
            token=token,
            started_at=datetime.now().isoformat(),
            binary_version=version,
        )
        self._save_state()

        # Wait for server to start
        for _ in range(10):
            time.sleep(0.3)
            if self._is_server_running():
                return port

        raise RuntimeError(
            f"Browser daemon failed to start after {10 * 0.3} seconds"
        )

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> requests.Response:
        """Make an authenticated request to the daemon"""
        if self._state is None or self._state.port is None or self._state.token is None:
            raise RuntimeError("Browser daemon not started. Call start() first.")

        url = f"http://127.0.0.1:{self._state.port}{path}"
        headers = {
            "Authorization": f"Bearer {self._state.token}",
        }

        response = requests.request(
            method,
            url,
            headers=headers,
            json=json,
            timeout=timeout,
        )
        response.raise_for_status()
        return response

    def snapshot(self, interactive: bool = True) -> str:
        """
        Take an accessibility snapshot of the current page
        Returns annotated tree with @refs for element addressing
        """
        response = self._request(
            "POST",
            "/command",
            json={"command": "snapshot", "args": ["-i" if interactive else ""]},
        )
        return response.text

    def click(self, ref: str) -> bool:
        """Click an element by ref (@e1, @c1)"""
        response = self._request(
            "POST",
            "/command",
            json={"command": "click", "args": [ref]},
        )
        return response.status_code == 200

    def goto(self, url: str) -> bool:
        """Navigate to a URL"""
        response = self._request(
            "POST",
            "/command",
            json={"command": "goto", "args": [url]},
        )
        return response.status_code == 200

    def fill(self, ref: str, text: str) -> bool:
        """Fill a form field by ref"""
        response = self._request(
            "POST",
            "/command",
            json={"command": "fill", "args": [ref, text]},
        )
        return response.status_code == 200

    def screenshot(
        self,
        output_path: str,
        full_page: bool = True,
    ) -> str:
        """Take a screenshot"""
        response = self._request(
            "POST",
            "/command",
            json={
                "command": "screenshot",
                "args": ["--full" if full_page else ""],
            },
        )
        # Response is image bytes
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path

    def console_messages(self, level: str = "info") -> List[Dict[str, Any]]:
        """Get console messages"""
        response = self._request(
            "POST",
            "/command",
            json={"command": "console", "args": [level]},
        )
        return response.json()

    def network_requests(self, include_static: bool = False) -> List[Dict[str, Any]]:
        """Get network requests"""
        args = ["--include-static"] if include_static else []
        response = self._request(
            "POST",
            "/command",
            json={"command": "network", "args": args},
        )
        return response.json()

    def stop(self) -> None:
        """Stop the browser daemon"""
        try:
            self._request("POST", "/command", json={"command": "stop"})
        except Exception:
            pass  # server might already be dead

        self._kill_old_server()
        self._state = None
        if os.path.exists(self.state_file):
            os.remove(self.state_file)


# Integration with Juhuo QA system
class GStackBrowserQA:
    """
    gstack-powered browser QA for Juhuo
    Uses the persistent browser daemon for automated testing
    """

    def __init__(self, state_file: Optional[str] = None):
        self.client = BrowserDaemonClient(state_file=state_file)
        self.ensure_running()

    def ensure_running(self) -> int:
        """Ensure the browser daemon is running"""
        if self.client._is_server_running():
            assert self.client._state is not None
            assert self.client._state.port is not None
            return self.client._state.port
        return self.client.start()

    def test_flow(
        self,
        base_url: str,
        steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Test a user flow:
        steps = [
            {"action": "goto", "url": "https://example.com"},
            {"action": "click", "ref": "@e1"},
            {"action": "fill", "ref": "@e2", "text": "test"},
            {"action": "click", "ref": "@e3"},
            {"action": "screenshot", "path": "result.png"},
        ]
        """
        results = []
        errors = []
        current_url = base_url

        self.client.goto(base_url)
        time.sleep(1.0)

        for i, step in enumerate(steps):
            action = step["action"]
            try:
                if action == "goto":
                    url = step["url"]
                    success = self.client.goto(url)
                    current_url = url
                    results.append({
                        "step": i,
                        "action": action,
                        "success": success,
                    })
                elif action == "click":
                    ref = step["ref"]
                    # Need snapshot first to get refs
                    if i > 0:  # after first navigation
                        self.client.snapshot()
                    success = self.client.click(ref)
                    results.append({
                        "step": i,
                        "action": action,
                        "ref": ref,
                        "success": success,
                    })
                    time.sleep(0.5)
                elif action == "fill":
                    ref = step["ref"]
                    text = step["text"]
                    success = self.client.fill(ref, text)
                    results.append({
                        "step": i,
                        "action": action,
                        "ref": ref,
                        "success": success,
                    })
                elif action == "screenshot":
                    path = step.get("path", tempfile.mktemp(suffix=".png"))
                    self.client.screenshot(path)
                    results.append({
                        "step": i,
                        "action": action,
                        "path": path,
                        "success": os.path.exists(path),
                    })
                else:
                    errors.append({
                        "step": i,
                        "error": f"Unknown action: {action}",
                    })
            except Exception as e:
                errors.append({
                    "step": i,
                    "error": str(e),
                })

        # Get console errors after all steps
        console_errors = self.client.console_messages(level="error")
        network_errors = [
            req for req in self.client.network_requests(include_static=False)
            if req.get("status", 200) >= 400
        ]

        return {
            "base_url": base_url,
            "steps_completed": len(results),
            "results": results,
            "errors": errors,
            "console_errors": len(console_errors),
            "network_errors": len(network_errors),
            "success": len(errors) == 0 and len(console_errors) == 0,
        }

    def import_cookies_from_chrome(self) -> Dict[str, Any]:
        """Import cookies from Chrome (gstack handles this)"""
        # The actual import is done by the daemon via cookie-picker UI
        # This just triggers it
        response = self.client._request("GET", "/cookie-picker")
        return {"status": "opened", "html": response.text}
