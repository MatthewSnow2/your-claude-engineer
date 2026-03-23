"""Serve command to start MCP server."""

from pathlib import Path
from typing import Optional

import click

from skillhub.core.mcp_server import MCPServer


@click.command()
@click.option(
    "--mcp-port",
    default=3000,
    type=int,
    help="MCP server port (default: 3000)",
    show_default=True,
)
@click.option(
    "--host",
    default="localhost",
    help="Server host (default: localhost)",
    show_default=True,
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable hot-reload for development",
)
@click.option(
    "--cache-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Custom cache directory (defaults to ~/.skillhub)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
def serve(
    mcp_port: int,
    host: str,
    reload: bool,
    cache_dir: Optional[Path],
    verbose: bool,
):
    """
    Start MCP server exposing installed skills.

    The MCP (Model Context Protocol) server allows Claude Code and other
    MCP-compatible agents to discover and execute installed skills directly
    without manual installation steps.

    Examples:

        # Start server on default port
        skillhub serve

        # Start with hot-reload for development
        skillhub serve --reload

        # Start on custom port with verbose logging
        skillhub serve --mcp-port 8080 --verbose
    """
    # Validate port range
    if not (1 <= mcp_port <= 65535):
        click.echo(
            f"Error: Port must be in range 1-65535, got {mcp_port}",
            err=True,
        )
        raise click.Abort()

    try:
        server = MCPServer(
            host=host,
            port=mcp_port,
            cache_dir=cache_dir,
            reload=reload,
            verbose=verbose,
        )

        click.echo(f"Starting MCP server at {host}:{mcp_port}")
        if reload:
            click.echo("Hot-reload enabled - changes will be detected automatically")

        server.serve_with_graceful_shutdown()

    except OSError as e:
        if "Address already in use" in str(e):
            click.echo(
                f"Error: Port {mcp_port} is already in use. "
                f"Try a different port with --mcp-port",
                err=True,
            )
        else:
            click.echo(f"Error starting server: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
