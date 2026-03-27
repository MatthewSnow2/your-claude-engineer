"""Tests for main module."""

import pytest
import io
import sys
import logging
from unittest.mock import patch, MagicMock
from voicenotify.main import main


class TestMain:
    """Tests for main function."""

    def test_valid_event_processing(self, monkeypatch, caplog):
        """Test processing a valid event through main loop."""
        # Mock stdin with a valid event followed by EOF
        mock_stdin = io.StringIO('{"event":"agent.completed","agent_id":"test1","ts":1730000000}\n')

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        with caplog.at_level(logging.INFO):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        assert "Notification required: completed for test1" in caplog.text

    def test_malformed_json_handling(self, monkeypatch, caplog):
        """Test handling of malformed JSON."""
        # Mock stdin with malformed JSON followed by EOF
        mock_stdin = io.StringIO('bad json\n')

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        assert "Failed to parse JSON" in caplog.text

    def test_multiple_events(self, monkeypatch, caplog):
        """Test processing multiple events."""
        # Mock stdin with multiple events
        events = (
            '{"event":"agent.completed","agent_id":"test1","ts":1730000000}\n'
            '{"event":"agent.stalled","agent_id":"test2","ts":1730000001}\n'
        )
        mock_stdin = io.StringIO(events)

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        with caplog.at_level(logging.INFO):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        assert "Notification required: completed for test1" in caplog.text
        assert "Notification required: stalled for test2" in caplog.text

    def test_empty_lines_ignored(self, monkeypatch, caplog):
        """Test that empty lines are ignored."""
        # Mock stdin with empty lines and a valid event
        events = '\n\n{"event":"agent.completed","agent_id":"test1","ts":1730000000}\n'
        mock_stdin = io.StringIO(events)

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        with caplog.at_level(logging.INFO):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        assert "Notification required: completed for test1" in caplog.text

    def test_mixed_valid_and_invalid_events(self, monkeypatch, caplog):
        """Test processing mix of valid and invalid events."""
        # Mock stdin with valid, invalid, and valid events
        events = (
            '{"event":"agent.completed","agent_id":"test1","ts":1730000000}\n'
            'bad json\n'
            '{"event":"agent.stalled","agent_id":"test2","ts":1730000001}\n'
        )
        mock_stdin = io.StringIO(events)

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        with caplog.at_level(logging.INFO):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        # Should process valid events
        assert "Notification required: completed for test1" in caplog.text
        assert "Notification required: stalled for test2" in caplog.text
        # Should log error for invalid event
        assert "Failed to parse JSON" in caplog.text

    def test_config_load_failure(self, monkeypatch, caplog):
        """Test handling of config load failure."""
        # Mock load_config to raise an exception
        with patch('voicenotify.main.load_config') as mock_load:
            mock_load.side_effect = ValueError("Invalid config")

            mock_stdin = io.StringIO('')
            monkeypatch.setattr(sys, 'stdin', mock_stdin)

            with caplog.at_level(logging.ERROR):
                with pytest.raises(SystemExit) as exc_info:
                    main()

            assert exc_info.value.code == 1
            assert "Failed to load configuration" in caplog.text
