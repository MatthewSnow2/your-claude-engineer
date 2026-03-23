"""Utility functions for CLI."""

from pathlib import Path


def get_skill_directory() -> Path:
    """Get current skill directory (current working directory)."""
    return Path.cwd()


def find_skill_manifest(start_dir: Path = None) -> Path:
    """
    Find skill.json manifest in directory tree.

    Args:
        start_dir: Starting directory (defaults to current dir)

    Returns:
        Path to skill.json

    Raises:
        FileNotFoundError: If skill.json not found
    """
    if start_dir is None:
        start_dir = Path.cwd()

    # Check current directory
    manifest_path = start_dir / "skill.json"
    if manifest_path.exists():
        return manifest_path

    # Check parent directories (up to 3 levels)
    for parent in list(start_dir.parents)[:3]:
        manifest_path = parent / "skill.json"
        if manifest_path.exists():
            return manifest_path

    raise FileNotFoundError("skill.json not found in current directory or parents")


def format_error(message: str) -> str:
    """Format error message for CLI output."""
    return f"Error: {message}"


def format_success(message: str) -> str:
    """Format success message for CLI output."""
    return f"Success: {message}"


def format_warning(message: str) -> str:
    """Format warning message for CLI output."""
    return f"Warning: {message}"
