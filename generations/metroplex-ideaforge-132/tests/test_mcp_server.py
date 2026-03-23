"""Tests for MCP server functionality."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from skillhub.core.cache import SkillCacheManager
from skillhub.core.mcp_server import ExecutionLog, MCPServer, SkillExecutor
from skillhub.core.models import MCPToolDefinition


@pytest.fixture
def execution_log(tmp_path):
    """Create execution log for testing."""
    log_dir = tmp_path / "logs"
    return ExecutionLog(log_dir=log_dir)


@pytest.fixture
def cache_manager_with_skill(tmp_path, sample_manifest_data):
    """Create cache manager with a test skill installed."""
    cache_dir = tmp_path / "cache"
    cache_manager = SkillCacheManager(cache_dir)

    # Create skill files
    skill_files = {
        "skill.json": json.dumps(sample_manifest_data).encode(),
        "main.py": b'def execute(input: str) -> dict:\n    return {"result": f"Processed: {input}"}',
    }

    # Install skill
    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**sample_manifest_data)
    cache_manager.cache_skill("test-skill", "0.1.0", manifest, skill_files)

    return cache_manager


@pytest.fixture
def mcp_server(tmp_path, cache_manager_with_skill):
    """Create MCP server for testing."""
    cache_dir = tmp_path / "cache"
    server = MCPServer(
        host="localhost",
        port=0,  # Use any available port for testing
        cache_dir=cache_dir,
        reload=False,
        verbose=False,
    )
    return server


def test_execution_log_creation(execution_log):
    """Test execution log creation."""
    assert execution_log.log_dir.exists()
    assert execution_log.log_file.parent.exists()


def test_execution_log_write(execution_log):
    """Test writing to execution log."""
    execution_log.log_execution(
        skill_name="test-skill",
        tool_name="test_tool",
        parameters={"input": "test"},
        status="success",
        duration=0.5,
        result={"output": "result"},
    )

    assert execution_log.log_file.exists()

    with open(execution_log.log_file) as f:
        line = f.readline()
        entry = json.loads(line)

    assert entry["skill_name"] == "test-skill"
    assert entry["tool_name"] == "test_tool"
    assert entry["status"] == "success"
    assert entry["duration"] == 0.5
    assert "result" in entry


def test_execution_log_history(execution_log):
    """Test retrieving execution history."""
    # Log multiple executions
    for i in range(5):
        execution_log.log_execution(
            skill_name=f"skill-{i}",
            tool_name=f"tool-{i}",
            parameters={"input": f"test-{i}"},
            status="success",
            duration=0.1,
        )

    history = execution_log.get_execution_history(limit=10)
    assert len(history) == 5


def test_execution_log_filter_by_skill(execution_log):
    """Test filtering execution history by skill name."""
    execution_log.log_execution(
        skill_name="skill-a",
        tool_name="tool",
        parameters={},
        status="success",
        duration=0.1,
    )
    execution_log.log_execution(
        skill_name="skill-b",
        tool_name="tool",
        parameters={},
        status="success",
        duration=0.1,
    )

    history = execution_log.get_execution_history(skill_name="skill-a")
    assert len(history) == 1
    assert history[0]["skill_name"] == "skill-a"


def test_execution_log_limit(execution_log):
    """Test limit parameter in execution history."""
    for i in range(25):
        execution_log.log_execution(
            skill_name="test-skill",
            tool_name="tool",
            parameters={},
            status="success",
            duration=0.1,
        )

    history = execution_log.get_execution_history(limit=10)
    assert len(history) == 10


def test_skill_executor_initialization(cache_manager_with_skill, execution_log):
    """Test skill executor initialization."""
    executor = SkillExecutor(cache_manager_with_skill, execution_log)
    assert executor.cache_manager == cache_manager_with_skill
    assert executor.execution_log == execution_log


def test_skill_executor_execute_success(cache_manager_with_skill, execution_log):
    """Test successful skill execution."""
    executor = SkillExecutor(cache_manager_with_skill, execution_log)

    tool_def = MCPToolDefinition(
        name="test_tool",
        description="Test tool",
        inputSchema={"type": "object", "properties": {"input": {"type": "string"}}},
        function_path="main.execute",
    )

    result = executor.execute_skill(
        skill_name="test-skill",
        tool_name="test_tool",
        tool_def=tool_def,
        parameters={"input": "hello"},
    )

    assert result["status"] == "success"
    assert "result" in result
    assert "Processed: hello" in str(result["result"])


def test_skill_executor_skill_not_found(cache_manager_with_skill, execution_log):
    """Test execution with non-existent skill."""
    executor = SkillExecutor(cache_manager_with_skill, execution_log)

    tool_def = MCPToolDefinition(
        name="test_tool",
        description="Test tool",
        inputSchema={"type": "object"},
        function_path="main.execute",
    )

    with pytest.raises(ValueError, match="Skill not found"):
        executor.execute_skill(
            skill_name="nonexistent-skill",
            tool_name="test_tool",
            tool_def=tool_def,
            parameters={},
        )


def test_skill_executor_parameter_validation(cache_manager_with_skill, execution_log):
    """Test parameter validation against input schema."""
    executor = SkillExecutor(cache_manager_with_skill, execution_log)

    tool_def = MCPToolDefinition(
        name="test_tool",
        description="Test tool",
        inputSchema={
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        },
        function_path="main.execute",
    )

    # Execute with missing required parameter
    result = executor.execute_skill(
        skill_name="test-skill",
        tool_name="test_tool",
        tool_def=tool_def,
        parameters={},  # Missing 'input'
    )

    assert result["status"] == "error"
    assert "validation failed" in result["error"].lower()


def test_skill_executor_timeout(cache_manager_with_skill, execution_log, tmp_path):
    """Test skill execution timeout."""
    # Create a skill that takes too long
    slow_skill_files = {
        "skill.json": json.dumps(
            {
                "name": "slow-skill",
                "version": "0.1.0",
                "description": "A slow skill",
                "author": "Test",
                "agent_skills_version": "1.0.0",
                "capabilities": [],
                "main_module": "main.py",
                "mcp_tools": [
                    {
                        "name": "slow_tool",
                        "description": "Slow tool",
                        "inputSchema": {"type": "object"},
                        "function_path": "main.slow_execute",
                    }
                ],
                "license": "MIT",
            }
        ).encode(),
        "main.py": b"import time\ndef slow_execute():\n    time.sleep(5)\n    return {'result': 'done'}",
    }

    from skillhub.core.models import SkillManifest

    manifest_data = json.loads(slow_skill_files["skill.json"])
    manifest = SkillManifest(**manifest_data)
    cache_manager_with_skill.cache_skill("slow-skill", "0.1.0", manifest, slow_skill_files)

    executor = SkillExecutor(cache_manager_with_skill, execution_log)

    tool_def = MCPToolDefinition(
        name="slow_tool",
        description="Slow tool",
        inputSchema={"type": "object"},
        function_path="main.slow_execute",
    )

    result = executor.execute_skill(
        skill_name="slow-skill",
        tool_name="slow_tool",
        tool_def=tool_def,
        parameters={},
        timeout=1,  # 1 second timeout
    )

    assert result["status"] == "error"
    assert "timeout" in result["error"].lower()


def test_skill_executor_execution_error(cache_manager_with_skill, execution_log, tmp_path):
    """Test handling of execution errors."""
    # Create a skill that raises an error
    error_skill_files = {
        "skill.json": json.dumps(
            {
                "name": "error-skill",
                "version": "0.1.0",
                "description": "An error skill",
                "author": "Test",
                "agent_skills_version": "1.0.0",
                "capabilities": [],
                "main_module": "main.py",
                "mcp_tools": [
                    {
                        "name": "error_tool",
                        "description": "Error tool",
                        "inputSchema": {"type": "object"},
                        "function_path": "main.error_execute",
                    }
                ],
                "license": "MIT",
            }
        ).encode(),
        "main.py": b"def error_execute():\n    raise ValueError('Test error')",
    }

    from skillhub.core.models import SkillManifest

    manifest_data = json.loads(error_skill_files["skill.json"])
    manifest = SkillManifest(**manifest_data)
    cache_manager_with_skill.cache_skill("error-skill", "0.1.0", manifest, error_skill_files)

    executor = SkillExecutor(cache_manager_with_skill, execution_log)

    tool_def = MCPToolDefinition(
        name="error_tool",
        description="Error tool",
        inputSchema={"type": "object"},
        function_path="main.error_execute",
    )

    result = executor.execute_skill(
        skill_name="error-skill",
        tool_name="error_tool",
        tool_def=tool_def,
        parameters={},
    )

    assert result["status"] == "error"
    assert "Test error" in result["error"]


def test_mcp_server_initialization(mcp_server):
    """Test MCP server initialization."""
    assert mcp_server.cache_manager is not None
    assert mcp_server.execution_log is not None
    assert mcp_server.executor is not None
    assert len(mcp_server.tools) > 0


def test_mcp_server_tool_registration(mcp_server):
    """Test tool registration from installed skills."""
    # Check that test-skill tools are registered
    assert "test-skill.test_tool" in mcp_server.tools

    skill_name, tool_def = mcp_server.tools["test-skill.test_tool"]
    assert skill_name == "test-skill"
    assert tool_def.name == "test_tool"


def test_mcp_server_handle_initialize(mcp_server):
    """Test MCP initialize request."""
    request = {"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}

    response = mcp_server.handle_jsonrpc(request)

    assert response["jsonrpc"] == "2.0"
    assert "result" in response
    assert response["result"]["protocolVersion"] == "1.0.0"
    assert "serverInfo" in response["result"]


def test_mcp_server_handle_list_tools(mcp_server):
    """Test MCP tools/list request."""
    request = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}

    response = mcp_server.handle_jsonrpc(request)

    assert response["jsonrpc"] == "2.0"
    assert "result" in response
    assert "tools" in response["result"]
    assert len(response["result"]["tools"]) > 0

    # Check tool format
    tool = response["result"]["tools"][0]
    assert "name" in tool
    assert "description" in tool
    assert "inputSchema" in tool


def test_mcp_server_handle_call_tool(mcp_server):
    """Test MCP tools/call request."""
    request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "test-skill.test_tool", "arguments": {"input": "test"}},
        "id": 1,
    }

    response = mcp_server.handle_jsonrpc(request)

    assert response["jsonrpc"] == "2.0"
    assert "result" in response
    assert response["result"]["status"] == "success"


def test_mcp_server_handle_call_tool_not_found(mcp_server):
    """Test MCP tools/call with non-existent tool."""
    request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "nonexistent-tool", "arguments": {}},
        "id": 1,
    }

    response = mcp_server.handle_jsonrpc(request)

    assert response["jsonrpc"] == "2.0"
    assert "error" in response
    assert "not found" in response["error"]["message"].lower()


def test_mcp_server_handle_unknown_method(mcp_server):
    """Test MCP request with unknown method."""
    request = {"jsonrpc": "2.0", "method": "unknown/method", "params": {}, "id": 1}

    response = mcp_server.handle_jsonrpc(request)

    assert response["jsonrpc"] == "2.0"
    assert "error" in response
    assert response["error"]["code"] == -32601


def test_mcp_server_hot_reload(tmp_path, sample_manifest_data):
    """Test hot-reload detection of skill changes."""
    cache_dir = tmp_path / "cache"
    cache_manager = SkillCacheManager(cache_dir)

    # Install initial skill
    skill_files = {
        "skill.json": json.dumps(sample_manifest_data).encode(),
        "main.py": b'def execute(input: str) -> dict:\n    return {"result": "v1"}',
    }

    from skillhub.core.models import SkillManifest

    manifest = SkillManifest(**sample_manifest_data)
    cache_manager.cache_skill("test-skill", "0.1.0", manifest, skill_files)

    # Create server with reload enabled
    server = MCPServer(
        host="localhost",
        port=0,
        cache_dir=cache_dir,
        reload=True,
        verbose=False,
    )

    initial_tool_count = len(server.tools)

    # Update skill manifest
    updated_manifest_data = sample_manifest_data.copy()
    updated_manifest_data["version"] = "0.1.1"
    updated_manifest_data["mcp_tools"].append(
        {
            "name": "new_tool",
            "description": "New tool",
            "inputSchema": {"type": "object"},
            "function_path": "main.new_execute",
        }
    )

    updated_files = {
        "skill.json": json.dumps(updated_manifest_data).encode(),
        "main.py": b'def execute(input: str) -> dict:\n    return {"result": "v2"}\ndef new_execute():\n    return {"result": "new"}',
    }

    updated_manifest = SkillManifest(**updated_manifest_data)
    cache_manager.cache_skill("test-skill", "0.1.1", updated_manifest, updated_files)

    # Trigger reload check
    time.sleep(0.1)
    server._check_reload()

    # Verify new tool is registered
    assert len(server.tools) > initial_tool_count
    assert "test-skill.new_tool" in server.tools


def test_mcp_server_unregister_skill(mcp_server, cache_manager_with_skill):
    """Test unregistering a skill."""
    # Verify skill is registered
    assert "test-skill.test_tool" in mcp_server.tools

    # Unregister
    mcp_server._unregister_skill("test-skill")

    # Verify skill is no longer registered
    assert "test-skill.test_tool" not in mcp_server.tools
    assert "test-skill" not in mcp_server.skill_tools


def test_execution_log_error_handling(execution_log):
    """Test execution log with error."""
    execution_log.log_execution(
        skill_name="test-skill",
        tool_name="test_tool",
        parameters={"input": "test"},
        status="error",
        duration=0.1,
        error="Something went wrong",
    )

    history = execution_log.get_execution_history(limit=1)
    assert len(history) == 1
    assert history[0]["status"] == "error"
    assert history[0]["error"] == "Something went wrong"


def test_execution_log_empty_file(execution_log):
    """Test execution log with non-existent file."""
    history = execution_log.get_execution_history()
    assert history == []


def test_skill_executor_invalid_function_path(cache_manager_with_skill, execution_log):
    """Test execution with invalid function path."""
    executor = SkillExecutor(cache_manager_with_skill, execution_log)

    tool_def = MCPToolDefinition(
        name="test_tool",
        description="Test tool",
        inputSchema={"type": "object"},
        function_path="invalid",  # Invalid path
    )

    result = executor.execute_skill(
        skill_name="test-skill",
        tool_name="test_tool",
        tool_def=tool_def,
        parameters={},
    )

    assert result["status"] == "error"
    assert "Invalid function path" in result["error"]


def test_skill_executor_missing_module(cache_manager_with_skill, execution_log):
    """Test execution with missing module."""
    executor = SkillExecutor(cache_manager_with_skill, execution_log)

    tool_def = MCPToolDefinition(
        name="test_tool",
        description="Test tool",
        inputSchema={"type": "object"},
        function_path="nonexistent.execute",
    )

    result = executor.execute_skill(
        skill_name="test-skill",
        tool_name="test_tool",
        tool_def=tool_def,
        parameters={},
    )

    assert result["status"] == "error"
    assert "not found" in result["error"].lower()


def test_skill_executor_missing_function(cache_manager_with_skill, execution_log):
    """Test execution with missing function."""
    executor = SkillExecutor(cache_manager_with_skill, execution_log)

    tool_def = MCPToolDefinition(
        name="test_tool",
        description="Test tool",
        inputSchema={"type": "object"},
        function_path="main.nonexistent",
    )

    result = executor.execute_skill(
        skill_name="test-skill",
        tool_name="test_tool",
        tool_def=tool_def,
        parameters={},
    )

    assert result["status"] == "error"
    assert "Function not found" in result["error"]
