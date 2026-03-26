"""Git commit extraction and message preprocessing."""

import subprocess
from pathlib import Path
from typing import List


CONVENTIONAL_PREFIXES = [
    "feat:",
    "fix:",
    "docs:",
    "style:",
    "refactor:",
    "perf:",
    "test:",
    "build:",
    "ci:",
    "chore:",
    "revert:",
]


def strip_prefix(message: str) -> str:
    """Remove conventional commit prefix from a commit message.

    Args:
        message: The commit message to process

    Returns:
        The message with conventional commit prefix removed and leading/trailing
        whitespace stripped

    Examples:
        >>> strip_prefix("feat: add login feature")
        'add login feature'
        >>> strip_prefix("fix: resolve bug in parser")
        'resolve bug in parser'
        >>> strip_prefix("update readme")
        'update readme'
    """
    message = message.strip()

    for prefix in CONVENTIONAL_PREFIXES:
        if message.lower().startswith(prefix):
            # Remove prefix and strip leading/trailing whitespace
            return message[len(prefix):].strip()

    return message


def extract_commits(repo_path: str = ".", count: int = 5) -> List[str]:
    """Extract the last N commit messages from a Git repository.

    Args:
        repo_path: Path to the Git repository (defaults to current directory)
        count: Number of commits to retrieve (must be >= 1, max 1000, defaults to 5)

    Returns:
        List of commit messages with conventional prefixes stripped,
        ordered from most recent to oldest

    Raises:
        FileNotFoundError: If the path does not exist
        NotADirectoryError: If the path is not a directory
        ValueError: If count is invalid or path is not a git repository
        RuntimeError: If git command fails or is not installed

    Examples:
        >>> extract_commits(".", 2)  # doctest: +SKIP
        ['add login feature', 'resolve bug in parser']
    """
    if count < 1:
        raise ValueError(f"Count must be at least 1, got: {count}")

    if count > 1000:
        raise ValueError(f"Count cannot exceed 1000, got: {count}")

    # Convert to absolute path for better error messages
    repo_path = Path(repo_path).resolve()

    # Check if path exists
    if not repo_path.exists():
        raise FileNotFoundError(f"Path does not exist: {repo_path}")

    # Check if it's a directory
    if not repo_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {repo_path}")

    try:
        # Run git log to get commit messages
        # %s = subject (commit message first line)
        # -n <count> = limit to N commits
        result = subprocess.run(
            ["git", "log", "-n", str(count), "--format=%s"],
            cwd=str(repo_path),
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            check=True,
            timeout=30
        )

        # Split output into lines and filter empty lines
        messages = [line for line in result.stdout.split("\n") if line.strip()]

        # Strip conventional commit prefixes
        cleaned_messages = [strip_prefix(msg) for msg in messages]

        return cleaned_messages

    except subprocess.TimeoutExpired:
        raise RuntimeError("Error: Git command timed out")
    except subprocess.CalledProcessError as e:
        # Git command failed - likely not a git repository
        error_msg = e.stderr.strip() if e.stderr else "Not a git repository"
        raise ValueError(f"Error: {error_msg}")
    except FileNotFoundError:
        # Git not installed
        raise RuntimeError("Error: Git is not installed or not in PATH")
