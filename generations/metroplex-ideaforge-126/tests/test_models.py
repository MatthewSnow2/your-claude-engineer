"""Tests for models module."""

import pytest
from voicenotify.models import AgentEvent, NotificationConfig


class TestAgentEvent:
    """Tests for AgentEvent data model."""

    def test_valid_completed_event(self):
        """Test creating a valid completed event."""
        event = AgentEvent(
            event="agent.completed",
            agent_id="test1",
            ts=1730000000
        )

        assert event.event == "agent.completed"
        assert event.agent_id == "test1"
        assert event.ts == 1730000000

    def test_valid_stalled_event(self):
        """Test creating a valid stalled event."""
        event = AgentEvent(
            event="agent.stalled",
            agent_id="test2",
            ts=1730000001
        )

        assert event.event == "agent.stalled"

    def test_valid_need_decision_event(self):
        """Test creating a valid need_decision event."""
        event = AgentEvent(
            event="agent.need_decision",
            agent_id="test3",
            ts=1730000002
        )

        assert event.event == "agent.need_decision"

    def test_invalid_event_type(self):
        """Test that invalid event type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid event type"):
            AgentEvent(
                event="invalid.event",
                agent_id="test",
                ts=1730000000
            )

    def test_empty_agent_id(self):
        """Test that empty agent_id raises ValueError."""
        with pytest.raises(ValueError, match="agent_id must be a non-empty string"):
            AgentEvent(
                event="agent.completed",
                agent_id="",
                ts=1730000000
            )

    def test_non_string_agent_id(self):
        """Test that non-string agent_id raises ValueError."""
        with pytest.raises(ValueError, match="agent_id must be a non-empty string"):
            AgentEvent(
                event="agent.completed",
                agent_id=123,
                ts=1730000000
            )

    def test_negative_timestamp(self):
        """Test that negative timestamp raises ValueError."""
        with pytest.raises(ValueError, match="ts must be a non-negative integer"):
            AgentEvent(
                event="agent.completed",
                agent_id="test",
                ts=-1
            )

    def test_non_integer_timestamp(self):
        """Test that non-integer timestamp raises ValueError."""
        with pytest.raises(ValueError, match="ts must be a non-negative integer"):
            AgentEvent(
                event="agent.completed",
                agent_id="test",
                ts="not_a_number"
            )


class TestNotificationConfig:
    """Tests for NotificationConfig data model."""

    def test_valid_call_config(self):
        """Test creating a valid call mode config."""
        config = NotificationConfig(
            mode="call",
            target="+15551234567"
        )

        assert config.mode == "call"
        assert config.target == "+15551234567"
        assert config.lang == "en-US"
        assert config.voice == "default"
        assert config.playback is False

    def test_valid_tg_config(self):
        """Test creating a valid tg mode config."""
        config = NotificationConfig(
            mode="tg",
            target="/tmp/voicenotes",
            lang="fr-FR",
            voice="custom-voice",
            playback=True
        )

        assert config.mode == "tg"
        assert config.target == "/tmp/voicenotes"
        assert config.lang == "fr-FR"
        assert config.voice == "custom-voice"
        assert config.playback is True

    def test_invalid_mode(self):
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid mode"):
            NotificationConfig(
                mode="invalid",
                target="/tmp/test"
            )

    def test_empty_target(self):
        """Test that empty target raises ValueError."""
        with pytest.raises(ValueError, match="target must be specified"):
            NotificationConfig(
                mode="call",
                target=""
            )

    def test_default_values(self):
        """Test default values for optional fields."""
        config = NotificationConfig(
            mode="call",
            target="+15551234567"
        )

        assert config.lang == "en-US"
        assert config.voice == "default"
        assert config.playback is False
