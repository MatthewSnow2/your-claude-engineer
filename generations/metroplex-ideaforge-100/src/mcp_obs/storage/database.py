"""Async SQLite database operations for MCP observability."""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import aiosqlite

from .models import AgentSession, ToolCall, ToolCallStatus

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database manager for trace storage."""

    def __init__(self, db_path: Path):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database schema and connection."""
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row

        # Enable foreign keys
        await self._connection.execute("PRAGMA foreign_keys = ON")

        # Run migrations
        await self._run_migrations()

        logger.info(f"Database initialized at {self.db_path}")

    async def _run_migrations(self) -> None:
        """Run database migrations."""
        migrations_dir = Path(__file__).parent / "migrations"
        migration_file = migrations_dir / "001_initial.sql"

        if migration_file.exists():
            with open(migration_file, "r") as f:
                migration_sql = f.read()

            await self._connection.executescript(migration_sql)
            await self._connection.commit()
            logger.info("Database migrations completed")

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            logger.info("Database connection closed")

    # Session operations

    async def create_session(self, session: AgentSession) -> None:
        """
        Create a new agent session record.

        Args:
            session: AgentSession model instance
        """
        query = """
            INSERT INTO sessions (
                session_id, agent_version, start_time, end_time,
                total_tokens, total_cost_usd, tool_calls_count,
                success_rate, context_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self._connection.execute(
            query,
            (
                session.session_id,
                session.agent_version,
                session.start_time.isoformat(),
                session.end_time.isoformat() if session.end_time else None,
                session.total_tokens,
                session.total_cost_usd,
                session.tool_calls_count,
                session.success_rate,
                json.dumps(session.context_data),
            ),
        )
        await self._connection.commit()
        logger.debug(f"Created session: {session.session_id}")

    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Unique session identifier

        Returns:
            AgentSession if found, None otherwise
        """
        query = "SELECT * FROM sessions WHERE session_id = ?"
        async with self._connection.execute(query, (session_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_session(row)
        return None

    async def update_session(self, session: AgentSession) -> None:
        """
        Update an existing session record.

        Args:
            session: AgentSession model instance with updated data
        """
        query = """
            UPDATE sessions SET
                agent_version = ?,
                end_time = ?,
                total_tokens = ?,
                total_cost_usd = ?,
                tool_calls_count = ?,
                success_rate = ?,
                context_data = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        """
        await self._connection.execute(
            query,
            (
                session.agent_version,
                session.end_time.isoformat() if session.end_time else None,
                session.total_tokens,
                session.total_cost_usd,
                session.tool_calls_count,
                session.success_rate,
                json.dumps(session.context_data),
                session.session_id,
            ),
        )
        await self._connection.commit()
        logger.debug(f"Updated session: {session.session_id}")

    async def list_sessions(
        self,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AgentSession]:
        """
        List sessions with optional filtering.

        Args:
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            start_time: Filter sessions starting after this time
            end_time: Filter sessions starting before this time

        Returns:
            List of AgentSession instances
        """
        query = "SELECT * FROM sessions WHERE 1=1"
        params = []

        if start_time:
            query += " AND start_time >= ?"
            params.append(start_time.isoformat())

        if end_time:
            query += " AND start_time <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        sessions = []
        async with self._connection.execute(query, params) as cursor:
            async for row in cursor:
                sessions.append(self._row_to_session(row))

        return sessions

    # Tool call operations

    async def create_tool_call(self, tool_call: ToolCall) -> None:
        """
        Create a new tool call record.

        Args:
            tool_call: ToolCall model instance
        """
        query = """
            INSERT INTO tool_calls (
                id, session_id, tool_name, parameters, response,
                status, execution_time_ms, tokens_consumed,
                timestamp, error_message, retry_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self._connection.execute(
            query,
            (
                tool_call.id,
                tool_call.session_id,
                tool_call.tool_name,
                json.dumps(tool_call.parameters),
                json.dumps(tool_call.response) if tool_call.response else None,
                tool_call.status.value,
                tool_call.execution_time_ms,
                tool_call.tokens_consumed,
                tool_call.timestamp.isoformat(),
                tool_call.error_message,
                tool_call.retry_count,
            ),
        )
        await self._connection.commit()
        logger.debug(f"Created tool call: {tool_call.id} ({tool_call.tool_name})")

    async def get_tool_call(self, tool_call_id: str) -> Optional[ToolCall]:
        """
        Retrieve a tool call by ID.

        Args:
            tool_call_id: Unique tool call identifier

        Returns:
            ToolCall if found, None otherwise
        """
        query = "SELECT * FROM tool_calls WHERE id = ?"
        async with self._connection.execute(query, (tool_call_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_tool_call(row)
        return None

    async def list_tool_calls(
        self,
        session_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        status: Optional[ToolCallStatus] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ToolCall]:
        """
        List tool calls with optional filtering.

        Args:
            session_id: Filter by session ID
            tool_name: Filter by tool name
            status: Filter by execution status
            start_time: Filter calls after this time
            end_time: Filter calls before this time
            limit: Maximum number of calls to return
            offset: Number of calls to skip

        Returns:
            List of ToolCall instances
        """
        query = "SELECT * FROM tool_calls WHERE 1=1"
        params = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        if tool_name:
            query += " AND tool_name = ?"
            params.append(tool_name)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        tool_calls = []
        async with self._connection.execute(query, params) as cursor:
            async for row in cursor:
                tool_calls.append(self._row_to_tool_call(row))

        return tool_calls

    async def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """
        Get statistics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session statistics
        """
        query = """
            SELECT
                COUNT(*) as total_calls,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status = 'failure' THEN 1 ELSE 0 END) as failure_count,
                AVG(execution_time_ms) as avg_execution_time,
                SUM(tokens_consumed) as total_tokens
            FROM tool_calls
            WHERE session_id = ?
        """
        async with self._connection.execute(query, (session_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                total_calls = row["total_calls"] or 0
                success_count = row["success_count"] or 0
                return {
                    "total_calls": total_calls,
                    "success_count": success_count,
                    "failure_count": row["failure_count"] or 0,
                    "success_rate": (success_count / total_calls * 100) if total_calls > 0 else 0.0,
                    "avg_execution_time_ms": row["avg_execution_time"] or 0.0,
                    "total_tokens": row["total_tokens"] or 0,
                }
        return {}

    async def cleanup_old_traces(self, retention_days: int) -> int:
        """
        Delete traces older than retention period.

        Args:
            retention_days: Number of days to retain data

        Returns:
            Number of sessions deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        query = "DELETE FROM sessions WHERE start_time < ?"

        cursor = await self._connection.execute(query, (cutoff_date.isoformat(),))
        await self._connection.commit()

        deleted_count = cursor.rowcount
        logger.info(f"Cleaned up {deleted_count} old sessions")
        return deleted_count

    # Helper methods

    def _row_to_session(self, row: aiosqlite.Row) -> AgentSession:
        """Convert database row to AgentSession model."""
        return AgentSession(
            session_id=row["session_id"],
            agent_version=row["agent_version"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            total_tokens=row["total_tokens"],
            total_cost_usd=row["total_cost_usd"],
            tool_calls_count=row["tool_calls_count"],
            success_rate=row["success_rate"],
            context_data=json.loads(row["context_data"]),
        )

    def _row_to_tool_call(self, row: aiosqlite.Row) -> ToolCall:
        """Convert database row to ToolCall model."""
        return ToolCall(
            id=row["id"],
            session_id=row["session_id"],
            tool_name=row["tool_name"],
            parameters=json.loads(row["parameters"]),
            response=json.loads(row["response"]) if row["response"] else None,
            status=ToolCallStatus(row["status"]),
            execution_time_ms=row["execution_time_ms"],
            tokens_consumed=row["tokens_consumed"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            error_message=row["error_message"],
            retry_count=row["retry_count"],
        )
