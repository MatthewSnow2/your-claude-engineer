"""MCP protocol server for skill execution."""

import importlib.util
import json
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import ValidationError, validate

from .cache import CachedSkillInfo, SkillCacheManager
from .models import MCPToolDefinition, SkillManifest

# Constants
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_LOG_FIELD_SIZE = 10000  # characters
MAX_ROTATED_LOGS = 5
RELOAD_CHECK_INTERVAL_SECONDS = 2


class ExecutionLog:
    """Manages skill execution audit trail."""

    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize execution log.

        Args:
            log_dir: Directory for log files (defaults to ~/.skillhub/logs)
        """
        if log_dir:
            self.log_dir = log_dir
        else:
            log_dir_str = os.getenv("SKILLHUB_CACHE_DIR")
            if log_dir_str:
                self.log_dir = Path(log_dir_str) / "logs"
            else:
                self.log_dir = Path.home() / ".skillhub" / "logs"

        self.log_dir = self.log_dir.resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "execution.jsonl"

    def log_execution(
        self,
        skill_name: str,
        tool_name: str,
        parameters: Dict[str, Any],
        status: str,
        duration: float,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ):
        """
        Log a skill execution.

        Args:
            skill_name: Name of the skill
            tool_name: Name of the tool/capability
            parameters: Input parameters
            status: Execution status (success/error)
            duration: Execution duration in seconds
            result: Execution result (if successful)
            error: Error message (if failed)
        """
        # Rotate log if it exceeds maximum size
        self._rotate_log_if_needed()

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "skill_name": skill_name,
            "tool_name": tool_name,
            "parameters": parameters,
            "status": status,
            "duration": duration,
        }

        # Truncate result and error fields to prevent unbounded growth
        if result is not None:
            result_str = json.dumps(result)
            if len(result_str) > MAX_LOG_FIELD_SIZE:
                log_entry["result"] = result_str[:MAX_LOG_FIELD_SIZE] + "... [truncated]"
            else:
                log_entry["result"] = result
        if error is not None:
            if len(error) > MAX_LOG_FIELD_SIZE:
                log_entry["error"] = error[:MAX_LOG_FIELD_SIZE] + "... [truncated]"
            else:
                log_entry["error"] = error

        with open(self.log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def _rotate_log_if_needed(self):
        """Rotate log file if it exceeds maximum size."""
        if not self.log_file.exists():
            return

        file_size = self.log_file.stat().st_size
        if file_size < MAX_LOG_FILE_SIZE:
            return

        # Rotate existing log files
        for i in range(MAX_ROTATED_LOGS - 1, 0, -1):
            old_log = self.log_dir / f"execution.{i}.jsonl"
            new_log = self.log_dir / f"execution.{i + 1}.jsonl"
            if old_log.exists():
                if i == MAX_ROTATED_LOGS - 1:
                    old_log.unlink()  # Delete oldest
                else:
                    old_log.rename(new_log)

        # Rename current log to .1
        self.log_file.rename(self.log_dir / "execution.1.jsonl")

    def get_execution_history(
        self, limit: int = 20, skill_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get execution history.

        Args:
            limit: Maximum number of entries to return
            skill_name: Filter by skill name (optional)

        Returns:
            List of execution log entries
        """
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if skill_name is None or entry.get("skill_name") == skill_name:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue

        # Return most recent entries
        return entries[-limit:]


class SkillExecutor:
    """Executes skills in a sandboxed environment."""

    def __init__(self, cache_manager: SkillCacheManager, execution_log: ExecutionLog):
        """
        Initialize skill executor.

        Args:
            cache_manager: Skill cache manager
            execution_log: Execution log instance
        """
        self.cache_manager = cache_manager
        self.execution_log = execution_log

    def execute_skill(
        self,
        skill_name: str,
        tool_name: str,
        tool_def: MCPToolDefinition,
        parameters: Dict[str, Any],
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        Execute a skill tool.

        Args:
            skill_name: Name of the skill
            tool_name: Name of the tool
            tool_def: Tool definition
            parameters: Input parameters
            timeout: Execution timeout in seconds

        Returns:
            Execution result

        Raises:
            ValueError: If skill not found or execution fails
            TimeoutError: If execution exceeds timeout
        """
        start_time = time.time()
        cached_skill = self.cache_manager.get_cached_skill(skill_name)

        if not cached_skill:
            raise ValueError(f"Skill not found: {skill_name}")

        try:
            # Validate parameters against input schema
            validate(instance=parameters, schema=tool_def.inputSchema)

            # Import and execute skill function
            result = self._execute_function(
                cached_skill, tool_def.function_path, parameters, timeout
            )

            # Log successful execution
            duration = time.time() - start_time
            self.execution_log.log_execution(
                skill_name=skill_name,
                tool_name=tool_name,
                parameters=parameters,
                status="success",
                duration=duration,
                result=result,
            )

            return {"status": "success", "result": result}

        except ValidationError as e:
            duration = time.time() - start_time
            error_msg = f"Parameter validation failed: {e.message}"
            self.execution_log.log_execution(
                skill_name=skill_name,
                tool_name=tool_name,
                parameters=parameters,
                status="error",
                duration=duration,
                error=error_msg,
            )
            return {"status": "error", "error": error_msg}

        except TimeoutError as e:
            duration = time.time() - start_time
            error_msg = f"Execution timeout: {str(e)}"
            self.execution_log.log_execution(
                skill_name=skill_name,
                tool_name=tool_name,
                parameters=parameters,
                status="error",
                duration=duration,
                error=error_msg,
            )
            return {"status": "error", "error": error_msg}

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Execution error: {str(e)}"
            self.execution_log.log_execution(
                skill_name=skill_name,
                tool_name=tool_name,
                parameters=parameters,
                status="error",
                duration=duration,
                error=error_msg,
            )
            return {"status": "error", "error": error_msg, "traceback": traceback.format_exc()}

    def _execute_function(
        self,
        cached_skill: CachedSkillInfo,
        function_path: str,
        parameters: Dict[str, Any],
        timeout: int,
    ) -> Any:
        """
        Execute a skill function with timeout.

        Args:
            cached_skill: Cached skill info
            function_path: Function path (e.g., "main.execute")
            parameters: Input parameters
            timeout: Timeout in seconds

        Returns:
            Function result

        Raises:
            ValueError: If function not found
            TimeoutError: If execution exceeds timeout
        """
        # Parse function path
        parts = function_path.split(".")
        if len(parts) < 2:
            raise ValueError(f"Invalid function path: {function_path}")

        module_name = ".".join(parts[:-1])
        function_name = parts[-1]

        # Import module
        module_path = cached_skill.install_path / f"{module_name.replace('.', '/')}.py"
        if not module_path.exists():
            raise ValueError(f"Module not found: {module_path}")

        # Load module dynamically
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot load module: {module_path}")

        module = importlib.util.module_from_spec(spec)

        # Add skill directory to sys.path temporarily
        original_path = sys.path.copy()
        sys.path.insert(0, str(cached_skill.install_path))

        try:
            spec.loader.exec_module(module)
        finally:
            sys.path = original_path

        # Get function
        if not hasattr(module, function_name):
            raise ValueError(f"Function not found: {function_name} in {module_name}")

        function = getattr(module, function_name)

        # Execute with timeout
        result_container = {}
        exception_container = {}

        def target():
            try:
                result_container["result"] = function(**parameters)
            except Exception as e:
                exception_container["exception"] = e

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            raise TimeoutError(f"Execution exceeded {timeout} seconds")

        if "exception" in exception_container:
            raise exception_container["exception"]

        return result_container.get("result")


class MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MCP protocol."""

    def log_message(self, format, *args):
        """Override to control logging."""
        if self.server.verbose:
            super().log_message(format, *args)

    def do_POST(self):
        """Handle POST requests (JSON-RPC 2.0)."""
        try:
            content_length = int(self.headers["Content-Length"])

            # Validate request size before reading
            if content_length > MAX_REQUEST_SIZE:
                self.send_error(413, "Request too large")
                return

            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode("utf-8"))

            response = self.server.handle_jsonrpc(request)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))

        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            self.send_error(500, str(e))

    def do_GET(self):
        """Handle GET requests (health check)."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            health = {
                "status": "healthy",
                "tools_registered": len(self.server.tools),
                "skills_loaded": len(self.server.skill_tools),
            }
            self.wfile.write(json.dumps(health).encode("utf-8"))
        else:
            self.send_error(404, "Not found")


class MCPServer(HTTPServer):
    """MCP protocol server for skill execution."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3000,
        cache_dir: Optional[Path] = None,
        reload: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize MCP server.

        Args:
            host: Server host
            port: Server port
            cache_dir: Cache directory for skills
            reload: Enable hot-reload
            verbose: Enable verbose logging
        """
        self.cache_manager = SkillCacheManager(cache_dir)
        self.execution_log = ExecutionLog()
        self.executor = SkillExecutor(self.cache_manager, self.execution_log)
        self.reload = reload
        self.verbose = verbose

        # Threading lock for hot-reload safety
        self._lock = threading.RLock()

        # Tool registry: tool_name -> (skill_name, tool_definition)
        self.tools: Dict[str, Tuple[str, MCPToolDefinition]] = {}
        self.skill_tools: Dict[str, List[str]] = {}  # skill_name -> [tool_names]
        self.skill_mtimes: Dict[str, float] = {}  # skill_name -> mtime

        # Load installed skills
        self._load_skills()

        # Initialize HTTP server
        super().__init__((host, port), MCPRequestHandler)

        # Start reload thread if enabled
        if self.reload:
            self._start_reload_thread()

    def _load_skills(self):
        """Load all installed skills and register as MCP tools."""
        installed_skills = self.cache_manager.list_installed()

        for cached_skill in installed_skills:
            self._register_skill(cached_skill)

    def _register_skill(self, cached_skill: CachedSkillInfo):
        """
        Register a skill's tools in the MCP registry.

        Args:
            cached_skill: Cached skill info
        """
        with self._lock:
            skill_name = cached_skill.name
            manifest = cached_skill.manifest

            # Track skill modification time for hot-reload
            manifest_path = cached_skill.install_path / "skill.json"
            self.skill_mtimes[skill_name] = manifest_path.stat().st_mtime

            # Register each MCP tool
            tool_names = []
            for tool_def in manifest.mcp_tools:
                tool_name = f"{skill_name}.{tool_def.name}"
                self.tools[tool_name] = (skill_name, tool_def)
                tool_names.append(tool_name)

            self.skill_tools[skill_name] = tool_names

            if self.verbose:
                print(f"Registered skill: {skill_name} ({len(tool_names)} tools)")

    def _unregister_skill(self, skill_name: str):
        """
        Unregister a skill's tools.

        Args:
            skill_name: Skill name
        """
        with self._lock:
            if skill_name in self.skill_tools:
                for tool_name in self.skill_tools[skill_name]:
                    if tool_name in self.tools:
                        del self.tools[tool_name]
                del self.skill_tools[skill_name]

            if skill_name in self.skill_mtimes:
                del self.skill_mtimes[skill_name]

            if self.verbose:
                print(f"Unregistered skill: {skill_name}")

    def _check_reload(self):
        """Check for skill changes and reload if necessary."""
        with self._lock:
            installed_skills = self.cache_manager.list_installed()
            current_skills = {skill.name for skill in installed_skills}

            # Check for removed skills
            for skill_name in list(self.skill_tools.keys()):
                if skill_name not in current_skills:
                    self._unregister_skill(skill_name)

            # Check for new or modified skills
            for cached_skill in installed_skills:
                skill_name = cached_skill.name
                manifest_path = cached_skill.install_path / "skill.json"

                if not manifest_path.exists():
                    continue

                current_mtime = manifest_path.stat().st_mtime

                # New skill or modified skill
                if (
                    skill_name not in self.skill_mtimes
                    or current_mtime > self.skill_mtimes[skill_name]
                ):
                    if skill_name in self.skill_tools:
                        self._unregister_skill(skill_name)
                    self._register_skill(cached_skill)

    def _start_reload_thread(self):
        """Start background thread for hot-reload."""

        def reload_loop():
            while self.reload:
                time.sleep(RELOAD_CHECK_INTERVAL_SECONDS)
                try:
                    self._check_reload()
                except Exception as e:
                    if self.verbose:
                        print(f"Reload error: {e}")

        thread = threading.Thread(target=reload_loop, daemon=True)
        thread.start()

    def handle_jsonrpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle JSON-RPC 2.0 request.

        Args:
            request: JSON-RPC request

        Returns:
            JSON-RPC response
        """
        jsonrpc = request.get("jsonrpc", "2.0")
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_list_tools(params)
            elif method == "tools/call":
                result = self._handle_call_tool(params)
            else:
                return {
                    "jsonrpc": jsonrpc,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": request_id,
                }

            return {"jsonrpc": jsonrpc, "result": result, "id": request_id}

        except Exception as e:
            return {
                "jsonrpc": jsonrpc,
                "error": {"code": -32603, "message": str(e)},
                "id": request_id,
            }

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": "1.0.0",
            "serverInfo": {
                "name": "SkillHub MCP Server",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {"listChanged": self.reload},
            },
        }

    def _handle_list_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        with self._lock:
            tools_list = []

            for tool_name, (skill_name, tool_def) in self.tools.items():
                tools_list.append(
                    {
                        "name": tool_name,
                        "description": tool_def.description,
                        "inputSchema": tool_def.inputSchema,
                    }
                )

            return {"tools": tools_list}

    def _handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        with self._lock:
            if tool_name not in self.tools:
                raise ValueError(f"Tool not found: {tool_name}")

            skill_name, tool_def = self.tools[tool_name]

        result = self.executor.execute_skill(
            skill_name=skill_name,
            tool_name=tool_name,
            tool_def=tool_def,
            parameters=arguments,
        )

        return result

    def serve_with_graceful_shutdown(self):
        """Serve with graceful shutdown on SIGINT/SIGTERM."""
        shutdown_requested = threading.Event()

        def signal_handler(signum, frame):
            print("\nShutting down MCP server...")
            shutdown_requested.set()
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        print(f"MCP server running on {self.server_address[0]}:{self.server_address[1]}")
        print(f"Loaded {len(self.tools)} tools from {len(self.skill_tools)} skills")
        if self.reload:
            print("Hot-reload enabled")

        try:
            self.serve_forever()
        except Exception as e:
            if not shutdown_requested.is_set():
                print(f"Server error: {e}")
        finally:
            print("Server stopped.")
