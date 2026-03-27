"""Tests for notifier module."""

import pytest
import logging
from voicenotify.notifier import send_notification
from voicenotify.models import NotificationConfig


class TestSendNotification:
    """Tests for send_notification function (STUB)."""

    def test_send_completed_notification(self, caplog):
        """Test sending completed notification."""
        config = NotificationConfig(mode="call", target="+15551234567")

        with caplog.at_level(logging.INFO):
            send_notification("completed", "test1", config)

        assert "Notification required: completed for test1" in caplog.text

    def test_send_stalled_notification(self, caplog):
        """Test sending stalled notification."""
        config = NotificationConfig(mode="tg", target="/tmp/voicenotes")

        with caplog.at_level(logging.INFO):
            send_notification("stalled", "test2", config)

        assert "Notification required: stalled for test2" in caplog.text

    def test_send_need_decision_notification(self, caplog):
        """Test sending need_decision notification."""
        config = NotificationConfig(mode="tg", target="/tmp/voicenotes")

        with caplog.at_level(logging.INFO):
            send_notification("need_decision", "test3", config)

        assert "Notification required: need_decision for test3" in caplog.text
