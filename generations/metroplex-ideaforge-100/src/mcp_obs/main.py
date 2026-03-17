"""CLI entry point for MCP Observability Layer."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box

from .utils.config import get_config
from .storage.database import Database
from .storage.models import ToolCallStatus
from .server.mcp_server import MCPObservabilityServer

console = Console()


def setup_logging(log_level: str) -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("mcp-obs.log"),
        ],
    )


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """MCP Observability Layer - Real-time agent execution tracing."""
    pass


@cli.command()
@click.option(
    "--port",
    type=int,
    help="Server port (default: from config)",
)
@click.option(
    "--host",
    type=str,
    default="localhost",
    help="Server host",
)
def start(port: Optional[int], host: str):
    """Start the MCP observability server."""
    config = get_config()
    if port:
        config.port = port
    if host:
        config.host = host

    setup_logging(config.log_level)

    console.print("\n[bold cyan]MCP Observability Layer[/bold cyan]")
    console.print(f"Version: 0.1.0\n")

    # Run the server
    server = MCPObservabilityServer(config)

    try:
        asyncio.run(server.serve_forever())
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Server error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--session",
    type=str,
    help="Filter by session ID",
)
@click.option(
    "--tool",
    type=str,
    help="Filter by tool name",
)
@click.option(
    "--status",
    type=click.Choice(["success", "failure", "timeout", "retry"]),
    help="Filter by execution status",
)
@click.option(
    "--hours",
    type=int,
    help="Show traces from last N hours",
)
@click.option(
    "--limit",
    type=int,
    default=50,
    help="Maximum number of results (default: 50)",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json", "detailed"]),
    default="table",
    help="Output format",
)
def query(
    session: Optional[str],
    tool: Optional[str],
    status: Optional[str],
    hours: Optional[int],
    limit: int,
    format: str,
):
    """Query execution traces with filtering."""
    config = get_config()
    setup_logging(config.log_level)

    asyncio.run(_query_traces(config, session, tool, status, hours, limit, format))


async def _query_traces(
    config,
    session_id: Optional[str],
    tool_name: Optional[str],
    status: Optional[str],
    hours: Optional[int],
    limit: int,
    output_format: str,
):
    """Async implementation of query command."""
    db = Database(config.db_path)
    await db.initialize()

    try:
        # Determine time range
        start_time = None
        if hours:
            start_time = datetime.utcnow() - timedelta(hours=hours)

        # Convert status string to enum
        status_enum = None
        if status:
            status_enum = ToolCallStatus(status)

        # Query tool calls
        tool_calls = await db.list_tool_calls(
            session_id=session_id,
            tool_name=tool_name,
            status=status_enum,
            start_time=start_time,
            limit=limit,
        )

        if not tool_calls:
            console.print("[yellow]No traces found matching criteria[/yellow]")
            return

        # Display results based on format
        if output_format == "json":
            import json
            console.print_json(json.dumps([tc.dict() for tc in tool_calls], default=str))
        elif output_format == "detailed":
            _display_detailed_traces(tool_calls)
        else:
            _display_trace_table(tool_calls)

        console.print(f"\n[dim]Showing {len(tool_calls)} trace(s)[/dim]")

    finally:
        await db.close()


def _display_trace_table(tool_calls):
    """Display traces in table format."""
    table = Table(title="Execution Traces", box=box.ROUNDED)

    table.add_column("Timestamp", style="cyan", no_wrap=True)
    table.add_column("Session", style="blue", max_width=12)
    table.add_column("Tool", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Time (ms)", justify="right", style="magenta")
    table.add_column("Tokens", justify="right", style="cyan")

    for tc in tool_calls:
        # Format timestamp
        ts = tc.timestamp.strftime("%H:%M:%S")

        # Session ID truncated
        sess = tc.session_id[:8] + "..."

        # Status with emoji
        status_display = {
            ToolCallStatus.SUCCESS: "✓ success",
            ToolCallStatus.FAILURE: "✗ failure",
            ToolCallStatus.TIMEOUT: "⏱ timeout",
            ToolCallStatus.RETRY: "↻ retry",
        }.get(tc.status, str(tc.status))

        table.add_row(
            ts,
            sess,
            tc.tool_name,
            status_display,
            str(tc.execution_time_ms),
            str(tc.tokens_consumed),
        )

    console.print(table)


def _display_detailed_traces(tool_calls):
    """Display traces in detailed format."""
    for i, tc in enumerate(tool_calls, 1):
        panel_content = f"""[bold]Tool:[/bold] {tc.tool_name}
[bold]Session:[/bold] {tc.session_id}
[bold]Status:[/bold] {tc.status.value}
[bold]Execution Time:[/bold] {tc.execution_time_ms}ms
[bold]Tokens:[/bold] {tc.tokens_consumed}
[bold]Timestamp:[/bold] {tc.timestamp}

[bold]Parameters:[/bold]
{tc.parameters}
"""

        if tc.response:
            panel_content += f"\n[bold]Response:[/bold]\n{tc.response}"

        if tc.error_message:
            panel_content += f"\n[bold red]Error:[/bold red] {tc.error_message}"

        panel = Panel(
            panel_content,
            title=f"Trace {i}/{len(tool_calls)}",
            border_style="cyan",
        )
        console.print(panel)
        console.print()


@cli.command()
def status():
    """Show server status and statistics."""
    config = get_config()
    setup_logging(config.log_level)

    asyncio.run(_show_status(config))


async def _show_status(config):
    """Async implementation of status command."""
    db = Database(config.db_path)
    await db.initialize()

    try:
        # Get recent sessions
        sessions = await db.list_sessions(limit=10)

        # Calculate overall statistics
        total_sessions = len(sessions)
        active_sessions = sum(1 for s in sessions if s.end_time is None)

        # Create status display
        status_tree = Tree("📊 [bold cyan]MCP Observability Status[/bold cyan]")

        # Server info
        server_node = status_tree.add("🖥️  Server Configuration")
        server_node.add(f"Host: {config.host}")
        server_node.add(f"Port: {config.port}")
        server_node.add(f"Database: {config.db_path}")
        server_node.add(f"Log Level: {config.log_level}")

        # Statistics
        stats_node = status_tree.add("📈 Statistics")
        stats_node.add(f"Total Sessions (last 100): {total_sessions}")
        stats_node.add(f"Active Sessions: {active_sessions}")

        if sessions:
            total_cost = sum(s.total_cost_usd for s in sessions)
            total_tokens = sum(s.total_tokens for s in sessions)
            avg_success_rate = sum(s.success_rate for s in sessions) / len(sessions)

            stats_node.add(f"Total Cost: ${total_cost:.4f}")
            stats_node.add(f"Total Tokens: {total_tokens:,}")
            stats_node.add(f"Avg Success Rate: {avg_success_rate:.1f}%")

        # Recent sessions
        if sessions:
            recent_node = status_tree.add("🕒 Recent Sessions")
            for session in sessions[:5]:
                sess_info = f"{session.session_id[:8]}... | {session.tool_calls_count} calls | {session.success_rate:.0f}% success"
                recent_node.add(sess_info)

        console.print(status_tree)

    finally:
        await db.close()


@cli.command()
@click.argument("session_id")
@click.option(
    "--format",
    type=click.Choice(["table", "json", "tree"]),
    default="tree",
    help="Output format",
)
def session(session_id: str, format: str):
    """Show detailed information about a session."""
    config = get_config()
    setup_logging(config.log_level)

    asyncio.run(_show_session(config, session_id, format))


async def _show_session(config, session_id: str, output_format: str):
    """Async implementation of session command."""
    db = Database(config.db_path)
    await db.initialize()

    try:
        # Get session
        session = await db.get_session(session_id)
        if not session:
            console.print(f"[red]Session not found: {session_id}[/red]")
            return

        # Get session statistics
        stats = await db.get_session_statistics(session_id)

        # Get tool calls
        tool_calls = await db.list_tool_calls(session_id=session_id, limit=1000)

        if output_format == "json":
            import json
            data = {
                "session": session.dict(),
                "statistics": stats,
                "tool_calls": [tc.dict() for tc in tool_calls],
            }
            console.print_json(json.dumps(data, default=str))
        elif output_format == "tree":
            _display_session_tree(session, stats, tool_calls)
        else:
            _display_session_table(session, stats, tool_calls)

    finally:
        await db.close()


def _display_session_tree(session, stats, tool_calls):
    """Display session in tree format."""
    tree = Tree(f"[bold cyan]Session: {session.session_id}[/bold cyan]")

    # Session info
    info_node = tree.add("📋 Session Info")
    info_node.add(f"Start Time: {session.start_time}")
    if session.end_time:
        duration = session.end_time - session.start_time
        info_node.add(f"End Time: {session.end_time}")
        info_node.add(f"Duration: {duration}")
    else:
        info_node.add("Status: [green]Active[/green]")

    if session.agent_version:
        info_node.add(f"Agent Version: {session.agent_version}")

    # Statistics
    stats_node = tree.add("📊 Statistics")
    stats_node.add(f"Total Calls: {stats.get('total_calls', 0)}")
    stats_node.add(f"Success Rate: {stats.get('success_rate', 0):.1f}%")
    stats_node.add(f"Avg Execution Time: {stats.get('avg_execution_time_ms', 0):.0f}ms")
    stats_node.add(f"Total Tokens: {stats.get('total_tokens', 0):,}")
    stats_node.add(f"Estimated Cost: ${session.total_cost_usd:.4f}")

    # Tool calls summary
    if tool_calls:
        tools_node = tree.add(f"🔧 Tool Calls ({len(tool_calls)})")

        # Group by tool name
        tool_summary = {}
        for tc in tool_calls:
            if tc.tool_name not in tool_summary:
                tool_summary[tc.tool_name] = {"count": 0, "success": 0, "failure": 0}
            tool_summary[tc.tool_name]["count"] += 1
            if tc.status == ToolCallStatus.SUCCESS:
                tool_summary[tc.tool_name]["success"] += 1
            else:
                tool_summary[tc.tool_name]["failure"] += 1

        for tool_name, summary in tool_summary.items():
            success_rate = (summary["success"] / summary["count"] * 100) if summary["count"] > 0 else 0
            tool_node = tools_node.add(
                f"{tool_name}: {summary['count']} calls, {success_rate:.0f}% success"
            )

    console.print(tree)


def _display_session_table(session, stats, tool_calls):
    """Display session in table format."""
    # Session info panel
    info_text = f"""[bold]Session ID:[/bold] {session.session_id}
[bold]Start Time:[/bold] {session.start_time}
[bold]Status:[/bold] {"Active" if session.end_time is None else "Completed"}
[bold]Total Tokens:[/bold] {session.total_tokens:,}
[bold]Total Cost:[/bold] ${session.total_cost_usd:.4f}
[bold]Success Rate:[/bold] {stats.get('success_rate', 0):.1f}%
"""
    console.print(Panel(info_text, title="Session Info", border_style="cyan"))

    # Tool calls table
    if tool_calls:
        console.print("\n")
        _display_trace_table(tool_calls)


if __name__ == "__main__":
    cli()
