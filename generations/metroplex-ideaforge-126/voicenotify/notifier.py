"""Notification delivery - STUB implementation for Feature 1."""

import logging
from voicenotify.models import NotificationConfig


logger = logging.getLogger(__name__)


def send_notification(event_type: str, agent_id: str, config: NotificationConfig) -> None:
    """Send notification for an agent event.

    This is a STUB implementation for Feature 1.
    Actual call/TTS logic will be implemented in Feature 2.

    Args:
        event_type: Event type (e.g., 'completed', 'stalled', 'need_decision')
        agent_id: Agent identifier
        config: Notification configuration
    """
    # STUB: Just log that notification is required
    logger.info(f"Notification required: {event_type} for {agent_id}")

    # Future implementation will check config.mode and either:
    # - Place a phone call (mode='call')
    # - Generate and save voice note (mode='tg')
