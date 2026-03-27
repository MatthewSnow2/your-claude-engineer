"""Data models for VoiceNotify plugin."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class AgentEvent:
    """Agent event data model."""
    event: Literal["agent.completed", "agent.stalled", "agent.need_decision"]
    agent_id: str
    ts: int  # Unix epoch seconds

    def __post_init__(self):
        """Validate event data."""
        valid_events = ["agent.completed", "agent.stalled", "agent.need_decision"]
        if self.event not in valid_events:
            raise ValueError(f"Invalid event type: {self.event}. Must be one of {valid_events}")

        if not isinstance(self.agent_id, str) or not self.agent_id:
            raise ValueError("agent_id must be a non-empty string")

        if not isinstance(self.ts, int) or self.ts < 0:
            raise ValueError("ts must be a non-negative integer")


@dataclass
class NotificationConfig:
    """Configuration for notification delivery."""
    mode: Literal["call", "tg"] = "call"
    target: str = ""  # phone number or directory path
    lang: str = "en-US"
    voice: str = "default"
    playback: bool = False  # only relevant for tg mode

    def __post_init__(self):
        """Validate configuration."""
        if self.mode not in ["call", "tg"]:
            raise ValueError(f"Invalid mode: {self.mode}. Must be 'call' or 'tg'")

        if not self.target:
            raise ValueError("target must be specified")
