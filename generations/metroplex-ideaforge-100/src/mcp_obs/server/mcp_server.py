"""MCP Protocol server for observability."""

import asyncio
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime

from ..storage.database import Database
from ..utils.config import ObservabilityConfig
from .trace_collector import TraceCollector
from .tool_interceptor import ToolInterceptor

logger = logging.getLogger(__name__)


class MCPObservabilityServer:
    """
    MCP-compatible observability server for agent execution tracing.

    This server listens for MCP protocol messages and records traces
    of tool calls, reasoning steps, and token usage.
    """

    def __init__(self, config: ObservabilityConfig):
        """
        Initialize MCP observability server.

        Args:
            config: Server configuration
        """
        self.config = config
        self.database = Database(config.db_path)
        self.trace_collector = TraceCollector(self.database)
        self.tool_interceptor = ToolInterceptor(self.trace_collector)
        self._server: Optional[asyncio.Server] = None
        self._running = False

    async def start(self) -> None:
        """Start the MCP observability server."""
        # Initialize database
        await self.database.initialize()

        # Start TCP server
        self._server = await asyncio.start_server(
            self._handle_client,
            self.config.host,
            self.config.port,
        )

        self._running = True

        addrs = ", ".join(str(sock.getsockname()) for sock in self._server.sockets)
        logger.info(f"MCP Observability Server listening on {addrs}")

        print(f"🚀 MCP Observability Server started on {self.config.host}:{self.config.port}")
        print(f"📊 Database: {self.config.db_path}")
        print(f"✨ Ready to capture agent traces...")

    async def stop(self) -> None:
        """Stop the MCP observability server."""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        await self.database.close()
        logger.info("MCP Observability Server stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle incoming client connection.

        Args:
            reader: Stream reader for incoming data
            writer: Stream writer for responses
        """
        addr = writer.get_extra_info("peername")
        logger.info(f"Client connected: {addr}")

        # Start a new session for this connection
        session_id = await self.trace_collector.start_session(
            agent_version="unknown",
            context_data={"client_addr": str(addr)},
        )

        try:
            while self._running:
                # Read MCP message (JSON-RPC format)
                data = await reader.readline()
                if not data:
                    break

                try:
                    message = json.loads(data.decode())
                    logger.debug(f"Received message: {message.get('method', 'unknown')}")

                    # Process the message
                    response = await self._process_mcp_message(session_id, message)

                    # Send response
                    if response:
                        writer.write(json.dumps(response).encode() + b"\n")
                        await writer.drain()

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                        "id": None,
                    }
                    writer.write(json.dumps(error_response).encode() + b"\n")
                    await writer.drain()

        except asyncio.CancelledError:
            logger.info(f"Client connection cancelled: {addr}")
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            # End the session
            await self.trace_collector.end_session(session_id)
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client disconnected: {addr}")

    async def _process_mcp_message(
        self,
        session_id: str,
        message: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Process an MCP protocol message.

        Args:
            session_id: Current session ID
            message: MCP message (JSON-RPC format)

        Returns:
            Response message if required
        """
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        # Record the MCP message
        await self.tool_interceptor.record_mcp_message(
            session_id=session_id,
            message_type=method or "notification",
            content=params,
            tokens=self._estimate_tokens(message),
        )

        # Handle different MCP methods
        if method == "tools/call":
            return await self._handle_tool_call(session_id, params, msg_id)
        elif method == "tools/list":
            return await self._handle_tools_list(msg_id)
        elif method == "ping":
            return {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": msg_id}

        # Default response for unknown methods
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Method not found"},
            "id": msg_id,
        }

    async def _handle_tool_call(
        self,
        session_id: str,
        params: Dict[str, Any],
        msg_id: Any,
    ) -> Dict[str, Any]:
        """Handle a tool call request."""
        tool_name = params.get("name", "unknown")
        tool_params = params.get("arguments", {})

        # For now, we just echo back success (actual tool execution would happen here)
        # In a real implementation, this would delegate to actual tool implementations
        logger.info(f"Tool call: {tool_name} in session {session_id}")

        result = {
            "success": True,
            "tool": tool_name,
            "message": f"Tool {tool_name} executed (observability mode)",
        }

        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": msg_id,
        }

    async def _handle_tools_list(self, msg_id: Any) -> Dict[str, Any]:
        """Handle a tools list request."""
        tools = [
            {
                "name": "file_operations",
                "description": "File read/write operations",
            },
            {
                "name": "shell_command",
                "description": "Execute shell commands",
            },
            {
                "name": "web_scrape",
                "description": "Scrape web content",
            },
        ]

        return {
            "jsonrpc": "2.0",
            "result": {"tools": tools},
            "id": msg_id,
        }

    def _estimate_tokens(self, message: Dict[str, Any]) -> int:
        """
        Estimate token count for a message.

        Args:
            message: MCP message

        Returns:
            Estimated token count (rough approximation)
        """
        # Rough approximation: ~4 characters per token
        message_str = json.dumps(message)
        return len(message_str) // 4

    async def serve_forever(self) -> None:
        """Run the server indefinitely."""
        await self.start()

        try:
            # Keep server running
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()
