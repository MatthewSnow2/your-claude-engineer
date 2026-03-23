"""Logs command to view execution history."""

from datetime import datetime
from typing import Optional

import click

from skillhub.core.mcp_server import ExecutionLog


@click.group()
def logs():
    """View skill execution logs and history."""
    pass


@logs.command(name="execution-history")
@click.option(
    "--limit",
    default=20,
    type=int,
    help="Number of entries to display (default: 20)",
    show_default=True,
)
@click.option(
    "--skill",
    help="Filter by skill name",
)
def execution_history(limit: int, skill: Optional[str]):
    """
    Show skill execution audit trail.

    Displays recent skill executions including timestamp, skill name,
    parameters, status, and duration. Useful for debugging and monitoring
    skill usage.

    Examples:

        # Show last 20 executions
        skillhub logs execution-history

        # Show last 50 executions
        skillhub logs execution-history --limit 50

        # Show executions for specific skill
        skillhub logs execution-history --skill test-skill
    """
    execution_log = ExecutionLog()
    entries = execution_log.get_execution_history(limit=limit, skill_name=skill)

    if not entries:
        if skill:
            click.echo(f"No execution history found for skill: {skill}")
        else:
            click.echo("No execution history found.")
        return

    # Display header
    click.echo("\nSkill Execution History")
    click.echo("=" * 80)
    click.echo()

    # Display each entry
    for i, entry in enumerate(entries, 1):
        timestamp = entry.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except (ValueError, AttributeError):
                pass

        skill_name = entry.get("skill_name", "unknown")
        tool_name = entry.get("tool_name", "unknown")
        status = entry.get("status", "unknown")
        duration = entry.get("duration", 0.0)
        parameters = entry.get("parameters", {})

        # Format status with color
        if status == "success":
            status_display = click.style("SUCCESS", fg="green", bold=True)
        else:
            status_display = click.style("ERROR", fg="red", bold=True)

        click.echo(f"[{i}] {timestamp}")
        click.echo(f"    Skill: {skill_name}")
        click.echo(f"    Tool: {tool_name}")
        click.echo(f"    Status: {status_display}")
        click.echo(f"    Duration: {duration:.3f}s")

        if parameters:
            params_str = ", ".join(f"{k}={v}" for k, v in parameters.items())
            if len(params_str) > 60:
                params_str = params_str[:57] + "..."
            click.echo(f"    Parameters: {params_str}")

        if status == "error" and "error" in entry:
            error_msg = entry["error"]
            if len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."
            click.echo(f"    Error: {click.style(error_msg, fg='red')}")

        if "result" in entry:
            result = entry["result"]
            result_str = str(result)
            if len(result_str) > 60:
                result_str = result_str[:57] + "..."
            click.echo(f"    Result: {result_str}")

        click.echo()

    # Display summary
    total = len(entries)
    success_count = sum(1 for e in entries if e.get("status") == "success")
    error_count = total - success_count

    click.echo("=" * 80)
    click.echo(
        f"Showing {total} execution(s) | "
        f"{click.style(f'{success_count} success', fg='green')} | "
        f"{click.style(f'{error_count} error', fg='red')}"
    )
    click.echo()
