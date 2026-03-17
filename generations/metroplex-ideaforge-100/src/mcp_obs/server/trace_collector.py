"""Trace collection for agent execution monitoring."""

import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from ..storage.database import Database
from ..storage.models import AgentSession, ToolCall, ToolCallStatus
from ..utils.pricing import calculate_cost

logger = logging.getLogger(__name__)


class TraceCollector:
    """Collects and stores execution traces for agent sessions."""

    def __init__(self, database: Database):
        """
        Initialize trace collector.

        Args:
            database: Database instance for persistence
        """
        self.database = database
        self._active_sessions: Dict[str, AgentSession] = {}

    async def start_session(
        self,
        session_id: Optional[str] = None,
        agent_version: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a new agent session.

        Args:
            session_id: Optional session ID (generated if not provided)
            agent_version: Version identifier for the agent
            context_data: Additional context metadata

        Returns:
            Session ID
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        session = AgentSession(
            session_id=session_id,
            agent_version=agent_version,
            start_time=datetime.utcnow(),
            context_data=context_data or {},
        )

        await self.database.create_session(session)
        self._active_sessions[session_id] = session

        logger.info(f"Started session: {session_id}")
        return session_id

    async def end_session(self, session_id: str) -> None:
        """
        End an active agent session and update statistics.

        Args:
            session_id: Session identifier
        """
        session = self._active_sessions.get(session_id)
        if not session:
            # Fetch from database if not in memory
            session = await self.database.get_session(session_id)
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return

        # Update session end time
        session.end_time = datetime.utcnow()

        # Calculate statistics
        stats = await self.database.get_session_statistics(session_id)
        session.tool_calls_count = stats.get("total_calls", 0)
        session.success_rate = stats.get("success_rate", 0.0)
        session.total_tokens = stats.get("total_tokens", 0)

        # Calculate cost (assuming Sonnet 4.5, adjust based on actual model usage)
        # For now, we'll use a simple estimate: 60% input, 40% output ratio
        input_tokens = int(session.total_tokens * 0.6)
        output_tokens = int(session.total_tokens * 0.4)
        session.total_cost_usd = calculate_cost(input_tokens, output_tokens)

        # Save to database
        await self.database.update_session(session)

        # Remove from active sessions
        self._active_sessions.pop(session_id, None)

        logger.info(f"Ended session: {session_id} (tokens: {session.total_tokens}, cost: ${session.total_cost_usd:.4f})")

    async def record_tool_call(
        self,
        session_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        response: Optional[Dict[str, Any]] = None,
        status: ToolCallStatus = ToolCallStatus.SUCCESS,
        execution_time_ms: int = 0,
        tokens_consumed: int = 0,
        error_message: Optional[str] = None,
        retry_count: int = 0,
    ) -> str:
        """
        Record a tool call execution.

        Args:
            session_id: Session identifier
            tool_name: Name of the tool called
            parameters: Tool call parameters
            response: Tool response data
            status: Execution status
            execution_time_ms: Execution duration in milliseconds
            tokens_consumed: Tokens used for this call
            error_message: Error details if failed
            retry_count: Number of retry attempts

        Returns:
            Tool call ID
        """
        tool_call_id = str(uuid.uuid4())

        tool_call = ToolCall(
            id=tool_call_id,
            session_id=session_id,
            tool_name=tool_name,
            parameters=parameters,
            response=response,
            status=status,
            execution_time_ms=execution_time_ms,
            tokens_consumed=tokens_consumed,
            timestamp=datetime.utcnow(),
            error_message=error_message,
            retry_count=retry_count,
        )

        await self.database.create_tool_call(tool_call)

        logger.debug(
            f"Recorded tool call: {tool_name} ({status.value}) "
            f"in session {session_id} - {execution_time_ms}ms"
        )

        return tool_call_id

    async def get_session_traces(self, session_id: str) -> Dict[str, Any]:
        """
        Get all traces for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary containing session data and tool calls
        """
        session = await self.database.get_session(session_id)
        if not session:
            return {}

        tool_calls = await self.database.list_tool_calls(session_id=session_id)
        stats = await self.database.get_session_statistics(session_id)

        return {
            "session": session.dict(),
            "tool_calls": [tc.dict() for tc in tool_calls],
            "statistics": stats,
        }

    def get_active_sessions(self) -> list:
        """
        Get list of currently active session IDs.

        Returns:
            List of active session IDs
        """
        return list(self._active_sessions.keys())
