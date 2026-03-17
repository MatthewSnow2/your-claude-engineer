"""Session replay engine for debugging agent executions."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from ...storage.database import Database
from ...storage.models import ToolCall, AgentSession, ReplayStep, ToolCallStatus

logger = logging.getLogger(__name__)


class SessionPlayer:
    """Replays agent sessions step-by-step for debugging."""

    def __init__(self, database: Database):
        """
        Initialize the session player.

        Args:
            database: Database instance for loading session data
        """
        self.db = database
        self.current_step = 0
        self.total_steps = 0
        self.session_data: Optional[AgentSession] = None
        self.tool_calls: List[ToolCall] = []
        self.is_paused = False

    async def load_session(self, session_id: str) -> Dict[str, Any]:
        """
        Load complete session data for replay.

        Args:
            session_id: Unique session identifier

        Returns:
            Dictionary with session metadata and loaded status

        Raises:
            ValueError: If session not found or database not initialized
        """
        if not self.db._connection:
            raise ValueError("Database connection not initialized")

        # Load session metadata
        self.session_data = await self.db.get_session(session_id)
        if not self.session_data:
            raise ValueError(f"Session not found: {session_id}")

        # Load all tool calls ordered by timestamp
        self.tool_calls = await self.db.get_session_tool_calls(session_id)
        self.total_steps = len(self.tool_calls)
        self.current_step = 0

        logger.info(f"Loaded session {session_id} with {self.total_steps} steps")

        return {
            "session_id": session_id,
            "total_steps": self.total_steps,
            "start_time": self.session_data.start_time,
            "end_time": self.session_data.end_time,
            "duration_ms": (
                int((self.session_data.end_time - self.session_data.start_time).total_seconds() * 1000)
                if self.session_data.end_time
                else None
            ),
            "total_tokens": self.session_data.total_tokens,
            "total_cost_usd": self.session_data.total_cost_usd,
        }

    async def get_step(self, step_number: int) -> Optional[ReplayStep]:
        """
        Get a specific step in the replay.

        Args:
            step_number: Step index (1-based)

        Returns:
            ReplayStep instance or None if step out of range
        """
        if not self.session_data or not self.tool_calls:
            logger.warning("Session not loaded")
            return None

        if step_number < 1 or step_number > self.total_steps:
            logger.warning(f"Step {step_number} out of range (1-{self.total_steps})")
            return None

        # Get the tool call for this step (convert to 0-based index)
        tool_call = self.tool_calls[step_number - 1]

        # Calculate elapsed time from session start
        elapsed_time_ms = int(
            (tool_call.timestamp - self.session_data.start_time).total_seconds() * 1000
        )

        # Calculate cumulative tokens and cost up to this step
        cumulative_tokens = sum(tc.tokens_consumed for tc in self.tool_calls[:step_number])

        # Rough cost estimation based on token ratio
        # Using Claude Opus 4.5 pricing approximation: $15/1M input, $75/1M output
        # Average: ~$45/1M tokens
        cumulative_cost = (cumulative_tokens / 1_000_000) * 45.0

        # Generate context summary
        context_summary = self._generate_context_summary(step_number, tool_call)

        return ReplayStep(
            step_number=step_number,
            tool_call=tool_call,
            elapsed_time_ms=elapsed_time_ms,
            cumulative_tokens=cumulative_tokens,
            cumulative_cost=cumulative_cost,
            context_summary=context_summary,
        )

    def _generate_context_summary(self, step_number: int, tool_call: ToolCall) -> str:
        """
        Generate a human-readable context summary for a step.

        Args:
            step_number: Current step number
            tool_call: Tool call for this step

        Returns:
            Context summary string
        """
        summaries = []

        # Position in session
        if step_number == 1:
            summaries.append("Session started")
        elif step_number == self.total_steps:
            summaries.append("Final step in session")

        # Status context
        if tool_call.status == ToolCallStatus.FAILURE:
            summaries.append("Tool call failed")
            if tool_call.retry_count > 0:
                summaries.append(f"{tool_call.retry_count} retries occurred")
        elif tool_call.status == ToolCallStatus.TIMEOUT:
            summaries.append("Tool call timed out")
        elif tool_call.status == ToolCallStatus.RETRY:
            summaries.append("Retry attempt")

        # Look for patterns
        if step_number > 1:
            prev_call = self.tool_calls[step_number - 2]
            if prev_call.tool_name == tool_call.tool_name:
                summaries.append(f"Repeated call to {tool_call.tool_name}")

        return "; ".join(summaries) if summaries else "Normal execution"

    async def get_replay_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a high-level summary of the session for replay overview.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session summary statistics
        """
        if not self.db._connection:
            raise ValueError("Database connection not initialized")

        session = await self.db.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        stats = await self.db.get_session_statistics(session_id)
        tool_calls = await self.db.get_session_tool_calls(session_id)

        # Calculate additional metrics
        unique_tools = len(set(tc.tool_name for tc in tool_calls))
        failure_count = sum(1 for tc in tool_calls if tc.status == ToolCallStatus.FAILURE)
        timeout_count = sum(1 for tc in tool_calls if tc.status == ToolCallStatus.TIMEOUT)

        # Find longest execution
        longest_call = max(tool_calls, key=lambda tc: tc.execution_time_ms) if tool_calls else None

        return {
            "session_id": session_id,
            "total_steps": len(tool_calls),
            "unique_tools": unique_tools,
            "success_rate": stats.get("success_rate", 0.0),
            "failure_count": failure_count,
            "timeout_count": timeout_count,
            "total_tokens": session.total_tokens,
            "total_cost_usd": session.total_cost_usd,
            "duration_ms": (
                int((session.end_time - session.start_time).total_seconds() * 1000)
                if session.end_time
                else None
            ),
            "longest_execution": {
                "tool": longest_call.tool_name,
                "time_ms": longest_call.execution_time_ms,
            }
            if longest_call
            else None,
        }

    async def get_failures(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all failure points in a session for quick debugging.

        Args:
            session_id: Session identifier

        Returns:
            List of failure dictionaries with context
        """
        if not self.db._connection:
            raise ValueError("Database connection not initialized")

        tool_calls = await self.db.get_session_tool_calls(session_id)
        session = await self.db.get_session(session_id)

        if not session:
            raise ValueError(f"Session not found: {session_id}")

        failures = []
        for idx, tool_call in enumerate(tool_calls, 1):
            if tool_call.status in [ToolCallStatus.FAILURE, ToolCallStatus.TIMEOUT]:
                elapsed_time_ms = int(
                    (tool_call.timestamp - session.start_time).total_seconds() * 1000
                )

                failures.append({
                    "step_number": idx,
                    "tool_name": tool_call.tool_name,
                    "status": tool_call.status.value,
                    "error_message": tool_call.error_message,
                    "elapsed_time_ms": elapsed_time_ms,
                    "parameters": tool_call.parameters,
                    "retry_count": tool_call.retry_count,
                })

        logger.info(f"Found {len(failures)} failures in session {session_id}")
        return failures

    async def export_session(self, session_id: str, output_path: str) -> str:
        """
        Export complete session data as JSON for sharing.

        Args:
            session_id: Session identifier
            output_path: File path for output JSON

        Returns:
            Absolute path to exported file

        Raises:
            ValueError: If session not found or database not initialized
        """
        if not self.db._connection:
            raise ValueError("Database connection not initialized")

        # Load session data
        session = await self.db.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        stats = await self.db.get_session_statistics(session_id)
        tool_calls = await self.db.get_session_tool_calls(session_id)

        # Build export data structure
        export_data = {
            "export_metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "mcp_obs_version": "0.1.0",
                "session_id": session_id,
            },
            "session": {
                "session_id": session.session_id,
                "agent_version": session.agent_version,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "total_tokens": session.total_tokens,
                "total_cost_usd": session.total_cost_usd,
                "tool_calls_count": session.tool_calls_count,
                "success_rate": session.success_rate,
                "context_data": session.context_data,
            },
            "statistics": stats,
            "tool_calls": [
                {
                    "step": idx,
                    "id": tc.id,
                    "tool_name": tc.tool_name,
                    "parameters": tc.parameters,
                    "response": tc.response,
                    "status": tc.status.value,
                    "execution_time_ms": tc.execution_time_ms,
                    "tokens_consumed": tc.tokens_consumed,
                    "timestamp": tc.timestamp.isoformat(),
                    "error_message": tc.error_message,
                    "retry_count": tc.retry_count,
                }
                for idx, tc in enumerate(tool_calls, 1)
            ],
        }

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Exported session {session_id} to {output_file}")
        return str(output_file.absolute())

    async def filter_by_status(
        self, session_id: str, status: str
    ) -> List[Dict[str, Any]]:
        """
        Filter replay steps by status (success/failure/timeout).

        Args:
            session_id: Session identifier
            status: Status to filter by

        Returns:
            List of filtered step dictionaries
        """
        if not self.db._connection:
            raise ValueError("Database connection not initialized")

        tool_calls = await self.db.get_session_tool_calls(session_id)
        session = await self.db.get_session(session_id)

        if not session:
            raise ValueError(f"Session not found: {session_id}")

        try:
            status_enum = ToolCallStatus(status)
        except ValueError:
            raise ValueError(f"Invalid status: {status}. Must be one of: success, failure, timeout, retry")

        filtered_steps = []
        for idx, tool_call in enumerate(tool_calls, 1):
            if tool_call.status == status_enum:
                elapsed_time_ms = int(
                    (tool_call.timestamp - session.start_time).total_seconds() * 1000
                )

                filtered_steps.append({
                    "step_number": idx,
                    "tool_name": tool_call.tool_name,
                    "status": tool_call.status.value,
                    "execution_time_ms": tool_call.execution_time_ms,
                    "elapsed_time_ms": elapsed_time_ms,
                    "tokens_consumed": tool_call.tokens_consumed,
                    "parameters": tool_call.parameters,
                    "response": tool_call.response,
                    "error_message": tool_call.error_message,
                })

        logger.info(f"Found {len(filtered_steps)} steps with status '{status}' in session {session_id}")
        return filtered_steps
