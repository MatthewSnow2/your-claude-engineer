"""Tests for utils module."""

import pytest
from unittest.mock import patch, MagicMock
import subprocess
from voicenotify.utils import run_command_with_retry, generate_voice_note_filename, sanitize_agent_id, validate_phone_number


class TestSanitizeAgentId:
    """Tests for sanitize_agent_id function."""

    def test_valid_alphanumeric(self):
        """Test sanitization of valid alphanumeric agent_id."""
        result = sanitize_agent_id("test123")
        assert result == "test123"

    def test_valid_with_dash_underscore(self):
        """Test sanitization of agent_id with dash and underscore."""
        result = sanitize_agent_id("test-agent_123")
        assert result == "test-agent_123"

    def test_remove_special_characters(self):
        """Test removal of special characters."""
        result = sanitize_agent_id("test@agent!123")
        assert result == "testagent123"

    def test_path_traversal_attack(self):
        """Test prevention of path traversal attack."""
        result = sanitize_agent_id("../../etc/passwd")
        # os.path.basename strips path, leaving just "passwd"
        assert result == "passwd"
        assert ".." not in result
        assert "/" not in result

    def test_absolute_path_attack(self):
        """Test prevention of absolute path attack."""
        result = sanitize_agent_id("/etc/passwd")
        # os.path.basename strips path, leaving just "passwd"
        assert result == "passwd"
        assert "/" not in result

    def test_all_invalid_characters_raises(self):
        """Test that all invalid characters raises ValueError."""
        with pytest.raises(ValueError, match="contains no valid characters"):
            sanitize_agent_id("!@#$%^&*()")

    def test_mixed_valid_invalid(self):
        """Test mixed valid and invalid characters."""
        result = sanitize_agent_id("test123!@#agent")
        assert result == "test123agent"


class TestRunCommandWithRetry:
    """Tests for run_command_with_retry function."""

    def test_successful_command(self):
        """Test successful command execution."""
        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.return_value = "/bin/echo"
            mock_run.return_value = MagicMock(returncode=0)

            result = run_command_with_retry(["echo", "test"])

            assert result is True
            assert mock_run.call_count == 1

    def test_failed_command_no_retry(self):
        """Test failed command with no retries."""
        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.return_value = "/bin/false"
            mock_run.return_value = MagicMock(returncode=1)

            result = run_command_with_retry(["false"], max_retries=0)

            assert result is False
            assert mock_run.call_count == 1

    def test_failed_command_with_retry(self):
        """Test failed command with retries."""
        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.return_value = "/bin/false"
            mock_run.return_value = MagicMock(returncode=1)

            result = run_command_with_retry(["false"], max_retries=2)

            assert result is False
            assert mock_run.call_count == 3  # initial + 2 retries

    def test_command_succeeds_on_retry(self):
        """Test command that fails initially but succeeds on retry."""
        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.return_value = "/bin/test"
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
        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.return_value = "/bin/sleep"
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5.0)

            result = run_command_with_retry(["sleep", "10"], max_retries=1, timeout=1.0)

            assert result is False
            assert mock_run.call_count == 2  # initial + 1 retry

    def test_exception_handling(self):
        """Test handling of general exceptions."""
        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.return_value = "/bin/test"
            mock_run.side_effect = Exception("Unknown error")

            result = run_command_with_retry(["test"])

            assert result is False

    def test_empty_command_raises(self):
        """Test that empty command raises ValueError."""
        with pytest.raises(ValueError, match="Command list cannot be empty"):
            run_command_with_retry([])

    def test_command_not_in_path_raises(self):
        """Test that command not in PATH raises ValueError."""
        with patch('shutil.which') as mock_which:
            mock_which.return_value = None

            with pytest.raises(ValueError, match="Command not found in PATH"):
                run_command_with_retry(["nonexistent_command"])


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

    def test_filename_sanitizes_dangerous_agent_id(self):
        """Test filename generation sanitizes dangerous agent_id."""
        filename = generate_voice_note_filename(1730000000, "../../etc/passwd", "agent.completed")

        # os.path.basename strips directory path, leaving just "passwd"
        assert filename == "1730000000_passwd_completed.ogg"
        assert ".." not in filename
        assert "/" not in filename


class TestValidatePhoneNumber:
    """Tests for validate_phone_number function."""

    def test_valid_e164_us_number(self):
        """Test validation of valid US E.164 phone number."""
        assert validate_phone_number("+11234567890") is True

    def test_valid_e164_uk_number(self):
        """Test validation of valid UK E.164 phone number."""
        assert validate_phone_number("+442071234567") is True

    def test_valid_e164_short_number(self):
        """Test validation of valid short E.164 number (7 digits)."""
        assert validate_phone_number("+1234567") is True

    def test_valid_e164_long_number(self):
        """Test validation of valid long E.164 number (15 digits)."""
        assert validate_phone_number("+123456789012345") is True

    def test_invalid_missing_plus(self):
        """Test rejection of number missing + prefix."""
        assert validate_phone_number("1234567890") is False

    def test_invalid_too_short(self):
        """Test rejection of number with too few digits."""
        assert validate_phone_number("+123456") is False

    def test_invalid_too_long(self):
        """Test rejection of number with too many digits."""
        assert validate_phone_number("+1234567890123456") is False

    def test_invalid_contains_letters(self):
        """Test rejection of number containing letters."""
        assert validate_phone_number("+12345ABC90") is False

    def test_invalid_contains_spaces(self):
        """Test rejection of number containing spaces."""
        assert validate_phone_number("+1 234 567 890") is False

    def test_invalid_contains_dashes(self):
        """Test rejection of number containing dashes."""
        assert validate_phone_number("+1-234-567-890") is False

    def test_invalid_empty_string(self):
        """Test rejection of empty string."""
        assert validate_phone_number("") is False
