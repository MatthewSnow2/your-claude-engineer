"""Pytest configuration and fixtures for MCP Observability tests."""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from src.mcp_obs.storage.database import Database
from src.mcp_obs.storage.models import AgentSession, ToolCall, ToolCallStatus
from src.mcp_obs.server.trace_collector import TraceCollector
from src.mcp_obs.utils.config import ObservabilityConfig


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_traces.db"
    yield db_path
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def database(temp_db_path):
    """Create a test database instance."""
    db = Database(temp_db_path)
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
async def trace_collector(database):
    """Create a trace collector instance for testing."""
    return TraceCollector(database)


@pytest.fixture
def test_config(temp_db_path):
    """Create a test configuration."""
    config = ObservabilityConfig(
        port=18765,  # Use different port for testing
        host="localhost",
        db_path=temp_db_path,
        log_level="DEBUG",
    )
    return config


@pytest.fixture
async def sample_session(database):
    """Create a sample session for testing."""
    from datetime import datetime

    session = AgentSession(
        session_id="test-session-123",
        agent_version="1.0.0",
        start_time=datetime.utcnow(),
        context_data={"test": "data"},
    )
    await database.create_session(session)
    return session


@pytest.fixture
async def sample_tool_call(database, sample_session):
    """Create a sample tool call for testing."""
    from datetime import datetime

    tool_call = ToolCall(
        id="test-call-456",
        session_id=sample_session.session_id,
        tool_name="test_tool",
        parameters={"param1": "value1"},
        response={"result": "success"},
        status=ToolCallStatus.SUCCESS,
        execution_time_ms=100,
        tokens_consumed=50,
        timestamp=datetime.utcnow(),
    )
    await database.create_tool_call(tool_call)
    return tool_call
