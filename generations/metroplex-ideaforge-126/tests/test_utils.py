"""Tests for utils module."""

import pytest
from unittest.mock import patch, MagicMock
import subprocess
from voicenotify.utils import run_command_with_retry, generate_voice_note_filename


class TestRunCommandWithRetry:
    """Tests for run_command_with_retry function."""

    def test_successful_command(self):
        """Test successful command execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = run_command_with_retry(["echo", "test"])

            assert result is True
            assert mock_run.call_count == 1

    def test_failed_command_no_retry(self):
        """Test failed command with no retries."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            result = run_command_with_retry(["false"], max_retries=0)

            assert result is False
            assert mock_run.call_count == 1

    def test_failed_command_with_retry(self):
        """Test failed command with retries."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            result = run_command_with_retry(["false"], max_retries=2)

            assert result is False
            assert mock_run.call_count == 3  # initial + 2 retries

    def test_command_succeeds_on_retry(self):
        """Test command that fails initially but succeeds on retry."""
        with patch('subprocess.run') as mock_run:
            # First call fails, second succeeds
            mock_run.side_effect = [
                MagicMock(returncode=1),
                MagicMock(returncode=0)
            ]

            result = run_command_with_retry(["test"], max_retries=2)

            assert result is True
            assert mock_run.call_count == 2

    def test_timeout_handling(self):
        """Test handling of timeout."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5.0)

            result = run_command_with_retry(["sleep", "10"], max_retries=1, timeout=1.0)

            assert result is False
            assert mock_run.call_count == 2  # initial + 1 retry

    def test_exception_handling(self):
        """Test handling of general exceptions."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Unknown error")

            result = run_command_with_retry(["test"])

            assert result is False


class TestGenerateVoiceNoteFilename:
    """Tests for generate_voice_note_filename function."""

    def test_completed_event_filename(self):
        """Test filename generation for completed event."""
        filename = generate_voice_note_filename(1730000000, "test1", "agent.completed")

        assert filename == "1730000000_test1_completed.ogg"

    def test_stalled_event_filename(self):
        """Test filename generation for stalled event."""
        filename = generate_voice_note_filename(1730000001, "test2", "agent.stalled")

        assert filename == "1730000001_test2_stalled.ogg"

    def test_need_decision_event_filename(self):
        """Test filename generation for need_decision event."""
        filename = generate_voice_note_filename(1730000002, "test3", "agent.need_decision")

        assert filename == "1730000002_test3_need_decision.ogg"

    def test_filename_with_special_characters(self):
        """Test filename generation with special characters in agent_id."""
        filename = generate_voice_note_filename(1730000000, "test-agent_123", "agent.completed")

        assert filename == "1730000000_test-agent_123_completed.ogg"
