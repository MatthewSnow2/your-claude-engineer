"""Tests for linear_status.py — Linear issue status checking."""

import os
from unittest.mock import MagicMock, patch

import pytest

from linear_status import (
    CANCELLED_STATE_TYPES,
    COMPLETED_STATE_TYPES,
    check_issue_statuses,
    get_issue_status,
)


def _mock_execute_response(state_name: str, state_type: str, identifier: str = "T-1"):
    """Build a mock Arcade tools.execute response."""
    mock_response = MagicMock()
    mock_response.output.value = {
        "issue": {
            "identifier": identifier,
            "title": f"Test issue {identifier}",
            "state": {
                "name": state_name,
                "type": state_type,
            },
            "completed_at": "2026-02-19T00:00:00Z" if state_type == "completed" else None,
        },
        "retrieved_at": "2026-02-19T16:00:00Z",
    }
    return mock_response


class TestGetIssueStatus:
    @patch("linear_status.ARCADE_API_KEY", "arc_test_key")
    def test_done_issue(self) -> None:
        client = MagicMock()
        client.tools.execute.return_value = _mock_execute_response("Done", "completed", "T-1")

        result = get_issue_status(client, "T-1")
        assert result["state_name"] == "Done"
        assert result["state_type"] == "completed"
        assert result["completed_at"] is not None

    @patch("linear_status.ARCADE_API_KEY", "arc_test_key")
    def test_todo_issue(self) -> None:
        client = MagicMock()
        client.tools.execute.return_value = _mock_execute_response("Todo", "unstarted", "T-2")

        result = get_issue_status(client, "T-2")
        assert result["state_name"] == "Todo"
        assert result["state_type"] == "unstarted"

    @patch("linear_status.ARCADE_API_KEY", "arc_test_key")
    def test_cancelled_issue(self) -> None:
        client = MagicMock()
        client.tools.execute.return_value = _mock_execute_response("Canceled", "canceled", "T-3")

        result = get_issue_status(client, "T-3")
        assert result["state_type"] == "canceled"

    @patch("linear_status.ARCADE_API_KEY", "arc_test_key")
    def test_api_error_returns_unknown(self) -> None:
        client = MagicMock()
        client.tools.execute.side_effect = Exception("API error")

        result = get_issue_status(client, "T-4")
        assert result["state_type"] == "unknown"
        assert result["identifier"] == "T-4"


class TestCheckIssueStatuses:
    @patch("linear_status._create_arcade_client")
    def test_categorizes_correctly(self, mock_create_client: MagicMock) -> None:
        client = MagicMock()
        mock_create_client.return_value = client

        # Set up responses for 4 issues
        responses = [
            _mock_execute_response("Done", "completed", "T-1"),
            _mock_execute_response("Done", "completed", "T-2"),
            _mock_execute_response("Todo", "unstarted", "T-3"),
            _mock_execute_response("Canceled", "canceled", "T-4"),
        ]
        client.tools.execute.side_effect = responses

        completed, cancelled, status_map = check_issue_statuses(
            ["T-1", "T-2", "T-3", "T-4"]
        )

        assert completed == {"T-1", "T-2"}
        assert cancelled == {"T-4"}
        assert len(status_map) == 4
        assert status_map["T-3"]["state_type"] == "unstarted"

    @patch("linear_status._create_arcade_client")
    def test_empty_list(self, mock_create_client: MagicMock) -> None:
        mock_create_client.return_value = MagicMock()

        completed, cancelled, status_map = check_issue_statuses([])
        assert completed == set()
        assert cancelled == set()
        assert status_map == {}

    @patch("linear_status._create_arcade_client")
    def test_all_done(self, mock_create_client: MagicMock) -> None:
        client = MagicMock()
        mock_create_client.return_value = client

        responses = [
            _mock_execute_response("Done", "completed", f"T-{i}")
            for i in range(1, 4)
        ]
        client.tools.execute.side_effect = responses

        completed, cancelled, status_map = check_issue_statuses(
            ["T-1", "T-2", "T-3"]
        )
        assert len(completed) == 3
        assert len(cancelled) == 0

    @patch("linear_status._create_arcade_client")
    def test_partial_api_failure(self, mock_create_client: MagicMock) -> None:
        """If one issue fails to fetch, it should be treated as unknown (not completed)."""
        client = MagicMock()
        mock_create_client.return_value = client

        client.tools.execute.side_effect = [
            _mock_execute_response("Done", "completed", "T-1"),
            Exception("Network error"),
            _mock_execute_response("Todo", "unstarted", "T-3"),
        ]

        completed, cancelled, status_map = check_issue_statuses(
            ["T-1", "T-2", "T-3"]
        )
        assert completed == {"T-1"}
        assert "T-2" not in completed  # Failed fetch not counted as done
        assert status_map["T-2"]["state_type"] == "unknown"


class TestStateTypeConstants:
    def test_completed_types(self) -> None:
        assert "completed" in COMPLETED_STATE_TYPES

    def test_cancelled_types(self) -> None:
        assert "canceled" in CANCELLED_STATE_TYPES
