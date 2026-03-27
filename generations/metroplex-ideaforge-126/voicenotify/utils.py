"""Utility functions for VoiceNotify plugin."""

import os
import re
import shutil
import subprocess
import time
from typing import List, Optional


def validate_phone_number(phone: str) -> bool:
    """Validate phone number format (E.164).

    Args:
        phone: Phone number to validate

    Returns:
        bool: True if phone number is valid E.164 format, False otherwise

    E.164 format: +[country code][subscriber number]
    - Starts with '+'
    - Followed by 7-15 digits
    """
    # E.164 format: + followed by 7-15 digits
    pattern = r'^\+\d{7,15}$'
    return bool(re.match(pattern, phone))


def sanitize_agent_id(agent_id: str) -> str:
    """Sanitize agent_id to prevent path traversal attacks.

    Only allows alphanumeric characters, dashes, and underscores.

    Args:
        agent_id: Raw agent identifier

    Returns:
        str: Sanitized agent identifier safe for use in filenames

    Raises:
        ValueError: If agent_id contains no valid characters
    """
    # Remove any path components (security: prevent directory traversal)
    agent_id = os.path.basename(agent_id)

    # Only allow alphanumeric, dash, and underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', agent_id)

    if not sanitized:
        raise ValueError(f"agent_id contains no valid characters: {agent_id}")

    return sanitized


def run_command_with_retry(
    command: List[str],
    max_retries: int = 2,
    timeout: float = 5.0
) -> bool:
    """Run a command with retry logic.

    Args:
        command: Command and arguments as list
        max_retries: Maximum number of retry attempts
        timeout: Timeout in seconds for each attempt

    Returns:
        bool: True if command succeeded, False otherwise

    Raises:
        ValueError: If command list is empty or command not found
    """
    # Validate command is non-empty
    if not command or len(command) == 0:
        raise ValueError("Command list cannot be empty")

    # Verify command exists in PATH
    cmd_path = shutil.which(command[0])
    if cmd_path is None:
        raise ValueError(f"Command not found in PATH: {command[0]}")

    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(
                command,
                timeout=timeout,
                capture_output=True,
                check=False
            )
            if result.returncode == 0:
                return True

            if attempt < max_retries:
                time.sleep(0.1)  # Brief pause before retry

        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                time.sleep(0.1)
            continue
        except Exception:
            return False

    return False


def generate_voice_note_filename(ts: int, agent_id: str, event: str) -> str:
    """Generate filename for voice note.

    Args:
        ts: Unix timestamp
        agent_id: Agent identifier (will be sanitized)
        event: Event type (e.g., 'agent.completed')

    Returns:
        str: Filename in format {ts}_{agent_id}_{event_type}.ogg

    Raises:
        ValueError: If agent_id cannot be sanitized
    """
    # Sanitize agent_id to prevent path traversal
    safe_agent_id = sanitize_agent_id(agent_id)

    # Extract event type without 'agent.' prefix
    event_type = event.replace("agent.", "")

    return f"{ts}_{safe_agent_id}_{event_type}.ogg"
