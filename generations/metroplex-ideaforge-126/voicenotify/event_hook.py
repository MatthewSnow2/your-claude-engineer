"""Agent event hook - JSON parsing and validation."""

import json
import logging
from typing import Optional
from voicenotify.models import AgentEvent


logger = logging.getLogger(__name__)


def parse_event(line: str) -> Optional[AgentEvent]:
    """Parse and validate an agent event from JSON line.

    Args:
        line: JSON string containing event data

    Returns:
        AgentEvent if valid, None if invalid

    Expected schema:
        {
            "event": "agent.completed|agent.stalled|agent.need_decision",
            "agent_id": string,
            "ts": integer
        }
    """
    try:
        data = json.loads(line)

        # Validate required fields
        if not isinstance(data, dict):
            logger.error("Event data must be a JSON object")
            return None

        if "event" not in data:
            logger.error("Missing required field: event")
            return None

        if "agent_id" not in data:
            logger.error("Missing required field: agent_id")
            return None

        if "ts" not in data:
            logger.error("Missing required field: ts")
            return None

        # Create and validate AgentEvent
        event = AgentEvent(
            event=data["event"],
            agent_id=data["agent_id"],
            ts=data["ts"]
        )

        return event

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return None
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid event data: {e}")
        return None


def process_event(event: AgentEvent) -> str:
    """Process a validated agent event.

    Args:
        event: Validated AgentEvent object

    Returns:
        str: Event type without 'agent.' prefix
    """
    # Extract event type without 'agent.' prefix
    event_type = event.event.replace("agent.", "")
    return event_type
