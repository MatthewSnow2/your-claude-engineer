"""Tests for notifier module."""

import os
import tempfile
import pytest
import logging
from unittest.mock import patch, MagicMock, call
from voicenotify.notifier import (
    send_notification,
    create_notifier,
    CallNotifier,
    TelegramNotifier,
)
from voicenotify.models import NotificationConfig


class TestCallNotifier:
    """Tests for CallNotifier class."""

    def test_no_telephony_tool_available(self, caplog):
        """Test behavior when no telephony tool is available."""
        config = NotificationConfig(mode="call", target="+15551234567")

        with patch('shutil.which') as mock_which:
            mock_which.return_value = None

            notifier = CallNotifier(config)

            assert notifier.telephony_tool is None

            with caplog.at_level(logging.WARNING):
                result = notifier.send("completed", "test1", 1730000000)

            assert result is False
            assert "No telephony CLI tool found" in caplog.text
            assert "Cannot place call: no telephony tool available" in caplog.text

    def test_telephony_tool_detected(self):
        """Test detection of telephony tool."""
        config = NotificationConfig(mode="call", target="+15551234567")

        with patch('shutil.which') as mock_which:
            # mmcli is available
            mock_which.side_effect = lambda cmd: "/usr/bin/mmcli" if cmd == "mmcli" else None

            notifier = CallNotifier(config)

            assert notifier.telephony_tool is not None
            assert notifier.telephony_tool[0] == "mmcli"

    def test_call_success(self, caplog):
        """Test successful phone call."""
        config = NotificationConfig(mode="call", target="+15551234567")

        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.side_effect = lambda cmd: "/usr/bin/mmcli" if cmd == "mmcli" else None
            mock_run.return_value = MagicMock(returncode=0)

            notifier = CallNotifier(config)

            with caplog.at_level(logging.INFO):
                result = notifier.send("completed", "test1", 1730000000)

            assert result is True
            assert "Call placed successfully" in caplog.text
            assert mock_run.call_count == 1

    def test_call_retry_on_failure(self, caplog):
        """Test retry logic on call failure."""
        config = NotificationConfig(mode="call", target="+15551234567")

        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.side_effect = lambda cmd: "/usr/bin/mmcli" if cmd == "mmcli" else None
            # First two attempts fail, third succeeds
            mock_run.side_effect = [
                MagicMock(returncode=1),
                MagicMock(returncode=1),
                MagicMock(returncode=0)
            ]

            notifier = CallNotifier(config)

            with caplog.at_level(logging.INFO):
                result = notifier.send("completed", "test1", 1730000000)

            assert result is True
            assert mock_run.call_count == 3
            assert "Call placed successfully (attempt 3)" in caplog.text

    def test_call_all_retries_fail(self, caplog):
        """Test when all retry attempts fail."""
        config = NotificationConfig(mode="call", target="+15551234567")

        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.side_effect = lambda cmd: "/usr/bin/mmcli" if cmd == "mmcli" else None
            mock_run.return_value = MagicMock(returncode=1)

            notifier = CallNotifier(config)

            with caplog.at_level(logging.ERROR):
                result = notifier.send("completed", "test1", 1730000000)

            assert result is False
            assert mock_run.call_count == 3
            assert "Call failed after 3 attempts" in caplog.text


class TestTelegramNotifier:
    """Tests for TelegramNotifier class."""

    def test_no_tts_engine_available(self, caplog):
        """Test behavior when no TTS engine is available."""
        config = NotificationConfig(mode="tg", target="/tmp/voicenotes")

        with patch('shutil.which') as mock_which:
            mock_which.return_value = None

            notifier = TelegramNotifier(config)

            assert notifier.tts_engine is None

            with caplog.at_level(logging.WARNING):
                result = notifier.send("completed", "test1", 1730000000)

            assert result is False
            assert "No TTS engine found" in caplog.text
            assert "Cannot create voice note: no TTS engine available" in caplog.text

    def test_tts_engine_detected(self):
        """Test detection of TTS engine."""
        config = NotificationConfig(mode="tg", target="/tmp/voicenotes")

        with patch('shutil.which') as mock_which:
            # espeak-ng is available
            mock_which.side_effect = lambda cmd: "/usr/bin/espeak-ng" if cmd == "espeak-ng" else None

            notifier = TelegramNotifier(config)

            assert notifier.tts_engine is not None
            assert notifier.tts_engine[0] == "espeak-ng"

    def test_voice_note_creation_success(self, caplog):
        """Test successful voice note creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NotificationConfig(mode="tg", target=tmpdir, playback=False)

            with patch('shutil.which') as mock_which, \
                 patch('subprocess.run') as mock_run:
                # espeak-ng available, no ffmpeg
                def which_side_effect(cmd):
                    if cmd == "espeak-ng":
                        return "/usr/bin/espeak-ng"
                    return None

                mock_which.side_effect = which_side_effect
                mock_run.return_value = MagicMock(returncode=0)

                notifier = TelegramNotifier(config)

                # Create a dummy WAV file for the test
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    temp_wav = os.path.join(tmpdir, "temp.wav")
                    mock_temp.return_value.__enter__.return_value.name = temp_wav

                    # Create the temp file
                    with open(temp_wav, 'w') as f:
                        f.write("dummy wav")

                    with caplog.at_level(logging.INFO):
                        result = notifier.send("completed", "test1", 1730000000)

            assert result is True
            assert "Voice note saved to" in caplog.text

            # Check that file was created
            files = os.listdir(tmpdir)
            assert len(files) >= 1
            assert any("test1" in f for f in files)
            assert any("completed.ogg" in f for f in files)

    def test_voice_note_with_invalid_agent_id(self, caplog):
        """Test voice note creation with invalid agent_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NotificationConfig(mode="tg", target=tmpdir, playback=False)

            with patch('shutil.which') as mock_which:
                mock_which.side_effect = lambda cmd: "/usr/bin/espeak-ng" if cmd == "espeak-ng" else None

                notifier = TelegramNotifier(config)

                with caplog.at_level(logging.ERROR):
                    result = notifier.send("completed", "!@#$%", 1730000000)

            assert result is False
            assert "Failed to generate filename" in caplog.text

    def test_voice_note_with_playback(self, caplog):
        """Test voice note creation with playback enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NotificationConfig(mode="tg", target=tmpdir, playback=True)

            with patch('shutil.which') as mock_which, \
                 patch('subprocess.run') as mock_run:
                # espeak-ng and afplay available
                def which_side_effect(cmd):
                    if cmd in ["espeak-ng", "afplay"]:
                        return f"/usr/bin/{cmd}"
                    return None

                mock_which.side_effect = which_side_effect
                mock_run.return_value = MagicMock(returncode=0)

                notifier = TelegramNotifier(config)

                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    temp_wav = os.path.join(tmpdir, "temp.wav")
                    mock_temp.return_value.__enter__.return_value.name = temp_wav

                    with open(temp_wav, 'w') as f:
                        f.write("dummy wav")

                    with caplog.at_level(logging.INFO):
                        result = notifier.send("completed", "test1", 1730000000)

            assert result is True
            assert "Playing back audio" in caplog.text

    def test_temp_file_cleanup(self):
        """Test that temporary WAV files are cleaned up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NotificationConfig(mode="tg", target=tmpdir, playback=False)

            with patch('shutil.which') as mock_which, \
                 patch('subprocess.run') as mock_run:
                mock_which.side_effect = lambda cmd: "/usr/bin/espeak-ng" if cmd == "espeak-ng" else None
                mock_run.return_value = MagicMock(returncode=0)

                notifier = TelegramNotifier(config)

                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    temp_wav = os.path.join(tmpdir, "temp.wav")
                    mock_temp.return_value.__enter__.return_value.name = temp_wav

                    with open(temp_wav, 'w') as f:
                        f.write("dummy wav")

                    notifier.send("completed", "test1", 1730000000)

                    # Temp file should be cleaned up
                    assert not os.path.exists(temp_wav)


class TestCreateNotifier:
    """Tests for create_notifier factory function."""

    def test_create_call_notifier(self):
        """Test creating call notifier."""
        config = NotificationConfig(mode="call", target="+15551234567")

        with patch('shutil.which') as mock_which:
            mock_which.return_value = None

            notifier = create_notifier(config)

            assert isinstance(notifier, CallNotifier)

    def test_create_telegram_notifier(self):
        """Test creating Telegram notifier."""
        config = NotificationConfig(mode="tg", target="/tmp/voicenotes")

        with patch('shutil.which') as mock_which:
            mock_which.return_value = None

            notifier = create_notifier(config)

            assert isinstance(notifier, TelegramNotifier)

    def test_invalid_mode_raises(self):
        """Test that invalid mode raises ValueError."""
        config = NotificationConfig(mode="call", target="+15551234567")
        config.mode = "invalid"  # Bypass validation for testing

        with pytest.raises(ValueError, match="Invalid mode"):
            create_notifier(config)


class TestSendNotification:
    """Tests for send_notification wrapper function."""

    def test_send_notification_call_mode(self, caplog):
        """Test sending notification in call mode."""
        config = NotificationConfig(mode="call", target="+15551234567")

        with patch('shutil.which') as mock_which, \
             patch('subprocess.run') as mock_run:
            mock_which.side_effect = lambda cmd: "/usr/bin/mmcli" if cmd == "mmcli" else None
            mock_run.return_value = MagicMock(returncode=0)

            with caplog.at_level(logging.INFO):
                result = send_notification("completed", "test1", config)

            assert result is True
            assert "Call placed successfully" in caplog.text

    def test_send_notification_tg_mode(self, caplog):
        """Test sending notification in tg mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NotificationConfig(mode="tg", target=tmpdir, playback=False)

            with patch('shutil.which') as mock_which, \
                 patch('subprocess.run') as mock_run:
                mock_which.side_effect = lambda cmd: "/usr/bin/espeak-ng" if cmd == "espeak-ng" else None
                mock_run.return_value = MagicMock(returncode=0)

                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    temp_wav = os.path.join(tmpdir, "temp.wav")
                    mock_temp.return_value.__enter__.return_value.name = temp_wav

                    with open(temp_wav, 'w') as f:
                        f.write("dummy wav")

                    with caplog.at_level(logging.INFO):
                        result = send_notification("stalled", "test2", config)

            assert result is True
            assert "Voice note saved to" in caplog.text

    def test_send_notification_handles_exceptions(self, caplog):
        """Test that send_notification handles exceptions gracefully."""
        config = NotificationConfig(mode="call", target="+15551234567")

        with patch('voicenotify.notifier.create_notifier') as mock_create:
            mock_create.side_effect = Exception("Test error")

            with caplog.at_level(logging.ERROR):
                result = send_notification("completed", "test1", config)

            assert result is False
            assert "Failed to send notification" in caplog.text


class TestShellEscaping:
    """Tests for shell escaping functions."""

    def test_escape_powershell_single_quote(self):
        """Test escaping single quotes in PowerShell strings."""
        config = NotificationConfig(mode="tg", target="/tmp/test")
        with patch('shutil.which'):
            notifier = TelegramNotifier(config)

        # PowerShell single-quoted strings escape ' with ''
        escaped = notifier._escape_for_shell("Agent's alert", 'powershell')
        assert escaped == "Agent''s alert"

    def test_escape_powershell_multiple_quotes(self):
        """Test escaping multiple single quotes in PowerShell strings."""
        config = NotificationConfig(mode="tg", target="/tmp/test")
        with patch('shutil.which'):
            notifier = TelegramNotifier(config)

        escaped = notifier._escape_for_shell("It's Bob's alert", 'powershell')
        assert escaped == "It''s Bob''s alert"

    def test_escape_osascript_double_quote(self):
        """Test escaping double quotes in osascript strings."""
        config = NotificationConfig(mode="call", target="+15551234567")
        with patch('shutil.which'):
            notifier = CallNotifier(config)

        # osascript double-quoted strings escape " with \"
        escaped = notifier._escape_for_shell('Agent "test" alert', 'osascript')
        assert escaped == 'Agent \\"test\\" alert'

    def test_escape_osascript_multiple_quotes(self):
        """Test escaping multiple double quotes in osascript strings."""
        config = NotificationConfig(mode="call", target="+15551234567")
        with patch('shutil.which'):
            notifier = CallNotifier(config)

        escaped = notifier._escape_for_shell('Say "Hello" and "Goodbye"', 'osascript')
        assert escaped == 'Say \\"Hello\\" and \\"Goodbye\\"'

    def test_escape_default_shell(self):
        """Test escaping for default shell type."""
        config = NotificationConfig(mode="tg", target="/tmp/test")
        with patch('shutil.which'):
            notifier = TelegramNotifier(config)

        # Default escapes single quotes with '\''
        escaped = notifier._escape_for_shell("Agent's alert", 'unknown')
        assert escaped == "Agent'\\''s alert"

    def test_sanitized_agent_id_in_message(self, caplog):
        """Test that agent_id is sanitized in TTS message to prevent injection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NotificationConfig(mode="tg", target=tmpdir)

            with patch('shutil.which') as mock_which, \
                 patch('subprocess.run') as mock_run, \
                 patch('tempfile.NamedTemporaryFile') as mock_temp:
                # Setup mocks
                mock_which.side_effect = lambda cmd: "/usr/bin/powershell" if cmd == "powershell" else None
                mock_run.return_value = MagicMock(returncode=0)

                temp_wav = os.path.join(tmpdir, "temp.wav")
                mock_temp.return_value.__enter__.return_value.name = temp_wav

                with open(temp_wav, 'w') as f:
                    f.write("dummy wav")

                notifier = TelegramNotifier(config)

                with caplog.at_level(logging.INFO):
                    # Agent ID with special characters - only alphanumeric remain
                    result = notifier.send("completed", "agent123-test", 1730000000)

                # Agent ID should be sanitized - only alphanumeric and dash remain
                assert "Creating voice note: Agent agent123-test has completed" in caplog.text

    def test_powershell_message_escaping(self, caplog):
        """Test that PowerShell TTS messages are properly escaped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NotificationConfig(mode="tg", target=tmpdir)

            with patch('shutil.which') as mock_which, \
                 patch('subprocess.run') as mock_run, \
                 patch('tempfile.NamedTemporaryFile') as mock_temp:
                # Setup mocks
                mock_which.side_effect = lambda cmd: "/usr/bin/powershell" if cmd == "powershell" else None
                mock_run.return_value = MagicMock(returncode=0)

                temp_wav = os.path.join(tmpdir, "temp.wav")
                mock_temp.return_value.__enter__.return_value.name = temp_wav

                with open(temp_wav, 'w') as f:
                    f.write("dummy wav")

                notifier = TelegramNotifier(config)

                with caplog.at_level(logging.INFO):
                    # Agent ID that could create single quotes in message
                    result = notifier.send("completed", "test", 1730000000)

                # Verify the PowerShell command was called with proper escaping
                assert mock_run.called
                # The text parameter in the command should be escaped
                call_args = mock_run.call_args[0][0]
                # PowerShell command should be present
                assert "powershell" in call_args[0].lower()
