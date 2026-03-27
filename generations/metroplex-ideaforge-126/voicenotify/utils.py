"""Utility functions for VoiceNotify plugin."""

import subprocess
import time
from typing import List, Optional


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
    """
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
        agent_id: Agent identifier
        event: Event type (e.g., 'agent.completed')

    Returns:
        str: Filename in format {ts}_{agent_id}_{event_type}.ogg
    """
    # Extract event type without 'agent.' prefix
    event_type = event.replace("agent.", "")
    return f"{ts}_{agent_id}_{event_type}.ogg"
