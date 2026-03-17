"""Configuration management for MCP observability layer."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class ObservabilityConfig(BaseModel):
    """Configuration for MCP observability server."""

    # Server configuration
    port: int = Field(
        default_factory=lambda: int(os.getenv("MCP_OBS_PORT", "8765")),
        description="MCP server port"
    )
    host: str = Field(
        default="localhost",
        description="MCP server host"
    )

    # Database configuration
    db_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv("MCP_OBS_DB_PATH", str(Path.home() / ".mcp-obs" / "traces.db"))
        ),
        description="SQLite database path"
    )

    # Logging configuration
    log_level: str = Field(
        default_factory=lambda: os.getenv("MCP_OBS_LOG_LEVEL", "INFO"),
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    # Storage configuration
    max_trace_size_mb: int = Field(
        default_factory=lambda: int(os.getenv("MCP_OBS_MAX_TRACE_SIZE", "100")),
        description="Maximum trace size in megabytes"
    )
    retention_days: int = Field(
        default_factory=lambda: int(os.getenv("MCP_OBS_RETENTION_DAYS", "30")),
        description="Days to retain trace data"
    )

    # API configuration
    anthropic_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"),
        description="Anthropic API key for testing"
    )

    def ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    class Config:
        arbitrary_types_allowed = True


def get_config() -> ObservabilityConfig:
    """Get the current configuration instance."""
    config = ObservabilityConfig()
    config.ensure_dirs()
    return config
