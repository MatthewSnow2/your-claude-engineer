"""Tool call interception and monitoring."""

import time
import logging
from typing import Any, Dict, Optional, Callable, Awaitable
from functools import wraps

from ..storage.models import ToolCallStatus
from .trace_collector import TraceCollector

logger = logging.getLogger(__name__)


class ToolInterceptor:
    """Intercepts and monitors tool calls for tracing."""

    def __init__(self, trace_collector: TraceCollector):
        """
        Initialize tool interceptor.

        Args:
            trace_collector: TraceCollector instance for recording calls
        """
        self.trace_collector = trace_collector

    def intercept_tool(
        self,
        tool_func: Callable[..., Awaitable[Any]],
        tool_name: str,
    ) -> Callable[..., Awaitable[Any]]:
        """
        Wrap a tool function to intercept and record its execution.

        Args:
            tool_func: Async function to wrap
            tool_name: Name of the tool

        Returns:
            Wrapped function with tracing
        """
        @wraps(tool_func)
        async def wrapped(*args, session_id: str, **kwargs) -> Any:
            """Wrapped tool function with execution tracing."""
            # Extract parameters (excluding session_id)
            parameters = {
                "args": [str(arg) for arg in args],
                "kwargs": {k: str(v) for k, v in kwargs.items()},
            }

            start_time = time.perf_counter()
            status = ToolCallStatus.SUCCESS
            response = None
            error_message = None
            retry_count = 0

            try:
                # Execute the actual tool
                result = await tool_func(*args, **kwargs)
                response = {"result": str(result)[:1000]}  # Limit response size
                return result

            except TimeoutError as e:
                status = ToolCallStatus.TIMEOUT
                error_message = str(e)
                logger.warning(f"Tool {tool_name} timed out: {e}")
                raise

            except Exception as e:
                status = ToolCallStatus.FAILURE
                error_message = str(e)
                logger.error(f"Tool {tool_name} failed: {e}")
                raise

            finally:
                # Record execution time
                end_time = time.perf_counter()
                execution_time_ms = int((end_time - start_time) * 1000)

                # Record the tool call
                try:
                    await self.trace_collector.record_tool_call(
                        session_id=session_id,
                        tool_name=tool_name,
                        parameters=parameters,
                        response=response,
                        status=status,
                        execution_time_ms=execution_time_ms,
                        tokens_consumed=0,  # Will be updated from MCP messages
                        error_message=error_message,
                        retry_count=retry_count,
                    )
                except Exception as e:
                    logger.error(f"Failed to record tool call: {e}")

        return wrapped

    async def record_mcp_message(
        self,
        session_id: str,
        message_type: str,
        content: Dict[str, Any],
        tokens: int = 0,
    ) -> None:
        """
        Record an MCP protocol message.

        Args:
            session_id: Session identifier
            message_type: Type of MCP message
            content: Message content
            tokens: Token count for this message
        """
        # Record as a special "mcp_message" tool call
        await self.trace_collector.record_tool_call(
            session_id=session_id,
            tool_name=f"mcp_{message_type}",
            parameters={"content": content},
            status=ToolCallStatus.SUCCESS,
            execution_time_ms=0,
            tokens_consumed=tokens,
        )

        logger.debug(f"Recorded MCP message: {message_type} ({tokens} tokens)")
