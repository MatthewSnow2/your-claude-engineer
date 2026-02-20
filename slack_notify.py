"""
Slack Notification Module
=========================

Sends Slack notifications from the parallel coordinator at key milestones.
Workers do NOT send notifications — the coordinator handles all Slack comms.

Two delivery methods, tried in order:
1. Slack Incoming Webhook (SLACK_WEBHOOK_URL) — fastest, no auth overhead
2. Arcade SDK (Slack_SendMessage) — fallback if no webhook configured

Usage:
    from slack_notify import SlackNotifier

    notifier = SlackNotifier()
    notifier.send_tier_complete(tier_num=4, description="feature", completed=["M2A-32"], failed=[])
    notifier.send_run_summary(completed=30, failed=2, skipped=6, total=38)
"""

import json
import os
import urllib.request
import urllib.error
from typing import Any

from arcade_config import ARCADE_API_KEY, ARCADE_USER_ID


# Default channel for notifications
SLACK_CHANNEL: str = os.environ.get("SLACK_CHANNEL", "new-channel")
SLACK_WEBHOOK_URL: str = os.environ.get("SLACK_WEBHOOK_URL", "")


class SlackNotifier:
    """Sends Slack notifications for parallel execution milestones."""

    def __init__(self, channel: str = SLACK_CHANNEL) -> None:
        self.channel = channel
        self._webhook_url = SLACK_WEBHOOK_URL
        self._arcade_client: Any = None
        self._method: str = "none"

        if self._webhook_url:
            self._method = "webhook"
        elif ARCADE_API_KEY:
            self._method = "arcade"
        else:
            print("  [slack] Warning: No SLACK_WEBHOOK_URL or ARCADE_API_KEY — notifications disabled")

    def _send_webhook(self, text: str) -> bool:
        """Send via Slack Incoming Webhook (simple HTTP POST)."""
        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            self._webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"  [slack] Webhook failed: {e}")
            return False

    def _send_arcade(self, text: str) -> bool:
        """Send via Arcade SDK Slack_SendMessage tool."""
        if self._arcade_client is None:
            try:
                from arcadepy import Arcade
                self._arcade_client = Arcade(api_key=ARCADE_API_KEY)
            except Exception as e:
                print(f"  [slack] Arcade client init failed: {e}")
                return False

        try:
            self._arcade_client.tools.execute(
                tool_name="Slack_SendMessage",
                input={
                    "channel_name": self.channel,
                    "message": text,
                },
                user_id=ARCADE_USER_ID,
            )
            return True
        except Exception as e:
            print(f"  [slack] Arcade Slack_SendMessage failed: {e}")
            return False

    def send(self, text: str) -> bool:
        """
        Send a Slack message, trying webhook first then Arcade SDK fallback.

        Returns True if sent successfully, False otherwise.
        """
        if self._method == "none":
            return False

        # Try webhook first (faster), fall back to Arcade if it fails
        if self._webhook_url:
            if self._send_webhook(text):
                return True
            # Webhook failed — try Arcade if available
            if ARCADE_API_KEY:
                print("  [slack] Falling back to Arcade SDK...")
                return self._send_arcade(text)
            return False

        if self._method == "arcade":
            return self._send_arcade(text)

        return False

    # =========================================================================
    # High-level notification methods
    # =========================================================================

    def send_parallel_start(
        self,
        project_name: str,
        total_issues: int,
        remaining: int,
        max_workers: int,
    ) -> None:
        """Notify that parallel execution is starting."""
        self.send(
            f":rocket: *Parallel execution started*\n"
            f"Project: `{project_name}`\n"
            f"Issues: {remaining} remaining of {total_issues} total\n"
            f"Workers: {max_workers} concurrent"
        )

    def send_tier_complete(
        self,
        tier_num: int,
        description: str,
        completed: list[str],
        failed: list[str],
    ) -> None:
        """Notify that a tier has completed."""
        status_icon = ":white_check_mark:" if not failed else ":warning:"
        parts = [f"{status_icon} *Tier {tier_num} complete: {description}*"]

        if completed:
            parts.append(f"Completed: {', '.join(completed)}")
        if failed:
            parts.append(f"Failed: {', '.join(failed)}")

        self.send("\n".join(parts))

    def send_issue_complete(self, issue_id: str, issue_title: str) -> None:
        """Notify that a single issue was completed and merged."""
        self.send(
            f":white_check_mark: *Completed:* {issue_title}\n"
            f"Linear issue: {issue_id}"
        )

    def send_issue_failed(self, issue_id: str, error: str) -> None:
        """Notify that an issue failed."""
        # Truncate error to keep message readable
        short_error = error[:200] if len(error) > 200 else error
        self.send(
            f":x: *Failed:* {issue_id}\n"
            f"Error: {short_error}"
        )

    def send_run_summary(
        self,
        project_name: str,
        completed: int,
        failed: int,
        skipped: int,
        total: int,
    ) -> None:
        """Send final run summary."""
        if failed == 0:
            icon = ":tada:"
            status = "All issues completed!"
        else:
            icon = ":memo:"
            status = "Run finished with failures"

        self.send(
            f"{icon} *{status}*\n"
            f"Project: `{project_name}`\n"
            f"• Completed: {completed}\n"
            f"• Failed: {failed}\n"
            f"• Skipped (already done): {skipped}\n"
            f"• Total: {total}"
        )
