"""Seed test data for tool effectiveness scoring engine testing."""

import asyncio
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import random

from ..storage.database import Database
from ..storage.models import AgentSession, ToolCall, ToolCallStatus


async def seed_test_data(db_path: Path):
    """
    Seed database with diverse tool call patterns for testing.

    Creates:
    - High-performing tools (80%+ success rate)
    - Medium-performing tools (50-70% success rate)
    - Low-performing tools (<50% success rate)
    - Tools with retry patterns
    - Tools with various execution times
    """
    db = Database(db_path)
    await db.initialize()

    try:
        print("Seeding test data...")

        # Create test sessions
        sessions = []
        for i in range(5):
            session_id = f"test-session-{uuid.uuid4().hex[:8]}"
            session = AgentSession(
                session_id=session_id,
                agent_version="1.0.0-test",
                start_time=datetime.utcnow() - timedelta(hours=24 - i * 4),
                end_time=datetime.utcnow() - timedelta(hours=24 - i * 4) + timedelta(hours=2),
            )
            await db.create_session(session)
            sessions.append(session)
            print(f"Created session: {session_id}")

        # Tool profiles with different characteristics
        tool_profiles = {
            # High-performing tool
            "file_search": {
                "success_rate": 0.85,
                "avg_exec_time": 120,
                "timeout_rate": 0.02,
                "retry_rate": 0.05,
                "errors": ["File not found", "Permission denied"],
            },
            # Medium-performing tool with high execution time
            "database_query": {
                "success_rate": 0.65,
                "avg_exec_time": 850,
                "timeout_rate": 0.10,
                "retry_rate": 0.15,
                "errors": ["Connection timeout", "Query timeout", "Invalid query syntax"],
            },
            # Low-performing tool with diverse errors
            "api_call": {
                "success_rate": 0.35,
                "avg_exec_time": 450,
                "timeout_rate": 0.20,
                "retry_rate": 0.30,
                "errors": [
                    "Network connection failed",
                    "Rate limit exceeded",
                    "Invalid API key",
                    "Service unavailable",
                    "Timeout",
                ],
            },
            # Stable high-performer
            "cache_lookup": {
                "success_rate": 0.95,
                "avg_exec_time": 45,
                "timeout_rate": 0.01,
                "retry_rate": 0.02,
                "errors": ["Cache miss"],
            },
            # Degrading tool (starts good, gets worse)
            "external_service": {
                "success_rate": 0.70,
                "avg_exec_time": 300,
                "timeout_rate": 0.08,
                "retry_rate": 0.12,
                "errors": ["Service degraded", "Temporary failure", "Network error"],
                "degrading": True,
            },
        }

        # Generate tool calls for each session
        call_count = 0
        for session in sessions:
            for tool_name, profile in tool_profiles.items():
                # Generate 20-40 calls per tool per session
                num_calls = random.randint(20, 40)

                for i in range(num_calls):
                    # Determine status based on profile
                    rand = random.random()

                    # For degrading tools, reduce success rate over time
                    success_rate = profile["success_rate"]
                    if profile.get("degrading"):
                        # Each session represents a time period - make it worse
                        session_index = sessions.index(session)
                        success_rate -= session_index * 0.05

                    if rand < success_rate:
                        status = ToolCallStatus.SUCCESS
                        error_message = None
                    elif rand < success_rate + profile["timeout_rate"]:
                        status = ToolCallStatus.TIMEOUT
                        error_message = "Operation timed out"
                    else:
                        status = ToolCallStatus.FAILURE
                        error_message = random.choice(profile["errors"])

                    # Execution time with some variance
                    exec_time = int(profile["avg_exec_time"] * random.uniform(0.7, 1.3))

                    # Retry count
                    retry_count = 1 if random.random() < profile["retry_rate"] else 0

                    # Timestamp spread across session
                    time_offset = timedelta(
                        minutes=random.randint(0, 120)
                    )
                    timestamp = session.start_time + time_offset

                    tool_call = ToolCall(
                        id=f"call-{uuid.uuid4().hex[:12]}",
                        session_id=session.session_id,
                        tool_name=tool_name,
                        parameters={"test": True, "index": i},
                        response={"result": "success"} if status == ToolCallStatus.SUCCESS else None,
                        status=status,
                        execution_time_ms=exec_time,
                        tokens_consumed=random.randint(10, 100),
                        timestamp=timestamp,
                        error_message=error_message,
                        retry_count=retry_count,
                    )

                    await db.create_tool_call(tool_call)
                    call_count += 1

        print(f"✓ Created {call_count} tool calls across {len(sessions)} sessions")
        print(f"✓ Tools seeded: {', '.join(tool_profiles.keys())}")
        print("\nExpected effectiveness scores (approximate):")
        print("  • cache_lookup: ~95 (high performer)")
        print("  • file_search: ~85 (good performer)")
        print("  • external_service: ~65 (degrading)")
        print("  • database_query: ~60 (moderate issues)")
        print("  • api_call: ~30 (low performer)")

        # Create a special demo session for replay demonstration
        await create_demo_replay_session(db)

    finally:
        await db.close()


async def create_demo_replay_session(db: Database):
    """Create a demo session specifically for replay feature demonstration."""
    print("\nCreating demo replay session...")

    session_id = "demo-session-001"
    start_time = datetime.utcnow() - timedelta(hours=1)

    session = AgentSession(
        session_id=session_id,
        agent_version="1.0.0-demo",
        start_time=start_time,
        end_time=start_time + timedelta(minutes=10),
        total_tokens=5700,
        total_cost_usd=0.2565,
    )
    await db.create_session(session)

    # Create a realistic sequence of tool calls with a story
    tool_calls_sequence = [
        {
            "tool_name": "file_search",
            "parameters": {"query": "find config files", "directory": "/home/user/project"},
            "response": {"files_found": 3, "matches": ["config.json", "settings.yaml", "env.local"]},
            "status": ToolCallStatus.SUCCESS,
            "execution_time_ms": 85,
            "tokens_consumed": 1200,
            "error_message": None,
            "offset_seconds": 0,
        },
        {
            "tool_name": "file_read",
            "parameters": {"path": "/home/user/project/config.json"},
            "response": {"content": '{"api_key": "***", "endpoint": "https://api.example.com"}'},
            "status": ToolCallStatus.SUCCESS,
            "execution_time_ms": 42,
            "tokens_consumed": 850,
            "error_message": None,
            "offset_seconds": 2,
        },
        {
            "tool_name": "api_call",
            "parameters": {"endpoint": "https://api.example.com/data", "method": "GET"},
            "response": None,
            "status": ToolCallStatus.FAILURE,
            "execution_time_ms": 5000,
            "tokens_consumed": 500,
            "error_message": "Connection timeout: host not responding",
            "offset_seconds": 5,
        },
        {
            "tool_name": "api_call",
            "parameters": {"endpoint": "https://api.example.com/data", "method": "GET", "timeout": 10},
            "response": None,
            "status": ToolCallStatus.FAILURE,
            "execution_time_ms": 10000,
            "tokens_consumed": 450,
            "error_message": "Connection timeout: network unreachable",
            "offset_seconds": 11,
        },
        {
            "tool_name": "cache_lookup",
            "parameters": {"key": "api_data_backup"},
            "response": {"cached": True, "data": {"records": 150}},
            "status": ToolCallStatus.SUCCESS,
            "execution_time_ms": 15,
            "tokens_consumed": 900,
            "error_message": None,
            "offset_seconds": 22,
        },
        {
            "tool_name": "database_query",
            "parameters": {"query": "SELECT * FROM users WHERE active = true", "database": "prod"},
            "response": {"rows": 42, "execution_time": 234},
            "status": ToolCallStatus.SUCCESS,
            "execution_time_ms": 234,
            "tokens_consumed": 1100,
            "error_message": None,
            "offset_seconds": 25,
        },
        {
            "tool_name": "file_write",
            "parameters": {"path": "/tmp/results.json", "content": "..."},
            "response": {"bytes_written": 1024},
            "status": ToolCallStatus.SUCCESS,
            "execution_time_ms": 28,
            "tokens_consumed": 700,
            "error_message": None,
            "offset_seconds": 28,
        },
    ]

    for tc_data in tool_calls_sequence:
        tool_call = ToolCall(
            id=f"call-{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            tool_name=tc_data["tool_name"],
            parameters=tc_data["parameters"],
            response=tc_data["response"],
            status=tc_data["status"],
            execution_time_ms=tc_data["execution_time_ms"],
            tokens_consumed=tc_data["tokens_consumed"],
            timestamp=start_time + timedelta(seconds=tc_data["offset_seconds"]),
            error_message=tc_data["error_message"],
            retry_count=0,
        )
        await db.create_tool_call(tool_call)

    # Update session statistics
    success_count = sum(1 for tc in tool_calls_sequence if tc["status"] == ToolCallStatus.SUCCESS)
    session.tool_calls_count = len(tool_calls_sequence)
    session.success_rate = (success_count / len(tool_calls_sequence)) * 100
    await db.update_session(session)

    print(f"✓ Created demo session: {session_id}")
    print(f"  - {len(tool_calls_sequence)} tool calls")
    print(f"  - {success_count} successes, {len(tool_calls_sequence) - success_count} failures")
    print(f"  - Includes retry scenario and failure recovery")


if __name__ == "__main__":
    from ..utils.config import get_config

    config = get_config()
    asyncio.run(seed_test_data(config.db_path))
