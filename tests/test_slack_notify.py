"""Tests for slack_notify module."""

import json
import unittest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from slack_notify import SlackNotifier


class TestSlackNotifierInit(unittest.TestCase):
    """Test SlackNotifier initialization and method selection."""

    @patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"})
    def test_prefers_webhook_when_available(self) -> None:
        notifier = SlackNotifier()
        assert notifier._method == "webhook"

    @patch.dict("os.environ", {"SLACK_WEBHOOK_URL": ""}, clear=False)
    @patch("slack_notify.SLACK_WEBHOOK_URL", "")
    @patch("slack_notify.ARCADE_API_KEY", "arc_test123")
    def test_falls_back_to_arcade(self) -> None:
        notifier = SlackNotifier()
        assert notifier._method == "arcade"

    @patch("slack_notify.SLACK_WEBHOOK_URL", "")
    @patch("slack_notify.ARCADE_API_KEY", "")
    def test_disabled_when_no_config(self) -> None:
        notifier = SlackNotifier()
        assert notifier._method == "none"

    def test_custom_channel(self) -> None:
        notifier = SlackNotifier(channel="dev-updates")
        assert notifier.channel == "dev-updates"


class TestSlackNotifierSend(unittest.TestCase):
    """Test message sending."""

    @patch("slack_notify.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("urllib.request.urlopen")
    def test_webhook_send_success(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = SlackNotifier()
        result = notifier.send("test message")

        assert result is True
        mock_urlopen.assert_called_once()

        # Verify the payload
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["text"] == "test message"

    @patch("slack_notify.SLACK_WEBHOOK_URL", "")
    @patch("slack_notify.ARCADE_API_KEY", "")
    def test_send_returns_false_when_disabled(self) -> None:
        notifier = SlackNotifier()
        result = notifier.send("test")
        assert result is False


class TestSlackNotifierMessages(unittest.TestCase):
    """Test high-level notification methods format correctly."""

    @patch("slack_notify.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_parallel_start_message(self) -> None:
        notifier = SlackNotifier()
        notifier.send = MagicMock(return_value=True)  # type: ignore[method-assign]

        notifier.send_parallel_start(
            project_name="gen-ui-dashboard",
            total_issues=38,
            remaining=5,
            max_workers=3,
        )

        msg = notifier.send.call_args[0][0]
        assert "gen-ui-dashboard" in msg
        assert "5 remaining" in msg
        assert "38 total" in msg
        assert "3 concurrent" in msg

    @patch("slack_notify.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_tier_complete_success(self) -> None:
        notifier = SlackNotifier()
        notifier.send = MagicMock(return_value=True)  # type: ignore[method-assign]

        notifier.send_tier_complete(
            tier_num=4,
            description="feature",
            completed=["M2A-32", "M2A-33"],
            failed=[],
        )

        msg = notifier.send.call_args[0][0]
        assert "Tier 4" in msg
        assert "feature" in msg
        assert ":white_check_mark:" in msg
        assert "M2A-32" in msg

    @patch("slack_notify.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_tier_complete_with_failures(self) -> None:
        notifier = SlackNotifier()
        notifier.send = MagicMock(return_value=True)  # type: ignore[method-assign]

        notifier.send_tier_complete(
            tier_num=5,
            description="styling",
            completed=["M2A-33"],
            failed=["M2A-35"],
        )

        msg = notifier.send.call_args[0][0]
        assert ":warning:" in msg
        assert "Failed: M2A-35" in msg

    @patch("slack_notify.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_run_summary_all_success(self) -> None:
        notifier = SlackNotifier()
        notifier.send = MagicMock(return_value=True)  # type: ignore[method-assign]

        notifier.send_run_summary(
            project_name="gen-ui-dashboard",
            completed=5,
            failed=0,
            skipped=33,
            total=38,
        )

        msg = notifier.send.call_args[0][0]
        assert ":tada:" in msg
        assert "All issues completed" in msg

    @patch("slack_notify.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_run_summary_with_failures(self) -> None:
        notifier = SlackNotifier()
        notifier.send = MagicMock(return_value=True)  # type: ignore[method-assign]

        notifier.send_run_summary(
            project_name="gen-ui-dashboard",
            completed=3,
            failed=2,
            skipped=33,
            total=38,
        )

        msg = notifier.send.call_args[0][0]
        assert ":memo:" in msg
        assert "failures" in msg

    @patch("slack_notify.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_issue_failed_truncates_long_error(self) -> None:
        notifier = SlackNotifier()
        notifier.send = MagicMock(return_value=True)  # type: ignore[method-assign]

        long_error = "x" * 500
        notifier.send_issue_failed("M2A-35", long_error)

        msg = notifier.send.call_args[0][0]
        assert len(msg) < 400  # Truncated


if __name__ == "__main__":
    unittest.main()
