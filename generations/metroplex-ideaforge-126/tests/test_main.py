"""Tests for main module."""

import pytest
import io
import sys
import signal
import logging
from unittest.mock import patch, MagicMock
from voicenotify.main import main, handle_sighup


class TestMain:
    """Tests for main function."""

    def test_valid_event_processing(self, monkeypatch, caplog):
        """Test processing a valid event through main loop."""
        # Mock stdin with a valid event followed by EOF
        mock_stdin = io.StringIO('{"event":"agent.completed","agent_id":"test1","ts":1730000000}\n')

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        # Mock the notifier to avoid needing telephony/TTS tools
        with patch('voicenotify.main.send_notification') as mock_send:
            mock_send.return_value = True

            with caplog.at_level(logging.INFO):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0
        # Verify send_notification was called
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[0]
        assert call_args[0] == "completed"
        assert call_args[1] == "test1"

    def test_malformed_json_handling(self, monkeypatch, caplog):
        """Test handling of malformed JSON."""
        # Mock stdin with malformed JSON followed by EOF
        mock_stdin = io.StringIO('bad json\n')

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
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
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        # Mock the notifier to avoid needing telephony/TTS tools
        with patch('voicenotify.main.send_notification') as mock_send:
            mock_send.return_value = True

            with caplog.at_level(logging.INFO):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0
        # Verify both events were processed
        assert mock_send.call_count == 2

    def test_empty_lines_ignored(self, monkeypatch, caplog):
        """Test that empty lines are ignored."""
        # Mock stdin with empty lines and a valid event
        events = '\n\n{"event":"agent.completed","agent_id":"test1","ts":1730000000}\n'
        mock_stdin = io.StringIO(events)

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        # Mock the notifier to avoid needing telephony/TTS tools
        with patch('voicenotify.main.send_notification') as mock_send:
            mock_send.return_value = True

            with caplog.at_level(logging.INFO):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0
        # Verify event was processed (empty lines were ignored)
        mock_send.assert_called_once()

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
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        # Mock the notifier to avoid needing telephony/TTS tools
        with patch('voicenotify.main.send_notification') as mock_send:
            mock_send.return_value = True

            with caplog.at_level(logging.INFO):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0
        # Should process 2 valid events
        assert mock_send.call_count == 2
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

    def test_sighup_triggers_config_reload(self, monkeypatch, caplog):
        """Test that SIGHUP triggers config reload."""
        # Mock stdin with a valid event followed by EOF
        mock_stdin = io.StringIO('{"event":"agent.completed","agent_id":"test1","ts":1730000000}\n')

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        # Track config load calls
        config_load_count = {'count': 0}

        def mock_load_config():
            config_load_count['count'] += 1
            from voicenotify.models import NotificationConfig
            # Always use tg mode with directory target
            return NotificationConfig(mode='tg', target="/tmp/test")

        # Mock the notifier and config loading
        with patch('voicenotify.main.load_config', side_effect=mock_load_config) as mock_load, \
             patch('voicenotify.main.send_notification') as mock_send:
            mock_send.return_value = True

            # Start main in a way that we can send signal
            import voicenotify.main as main_module

            # Simulate SIGHUP by directly setting the flag
            with caplog.at_level(logging.INFO):
                # Trigger SIGHUP before processing event
                main_module.config_needs_reload = True

                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0
        # Config should be loaded twice: initial + reload
        assert config_load_count['count'] == 2
        assert "Configuration reloaded" in caplog.text

    def test_sighup_handler_sets_reload_flag(self):
        """Test that SIGHUP handler sets config_needs_reload flag."""
        import voicenotify.main as main_module

        # Reset flag
        main_module.config_needs_reload = False

        # Call handler directly
        handle_sighup(signal.SIGHUP, None)

        # Verify flag was set
        assert main_module.config_needs_reload is True

    def test_sighup_reload_failure_handling(self, monkeypatch, caplog):
        """Test that SIGHUP reload failure doesn't crash the process."""
        # Mock stdin with a valid event followed by EOF
        mock_stdin = io.StringIO('{"event":"agent.completed","agent_id":"test1","ts":1730000000}\n')

        monkeypatch.setattr(sys, 'stdin', mock_stdin)
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")

        # Track config load calls
        config_load_count = {'count': 0}

        def mock_load_config():
            config_load_count['count'] += 1
            from voicenotify.models import NotificationConfig
            # First load succeeds, second fails
            if config_load_count['count'] == 1:
                return NotificationConfig(mode='tg', target="/tmp/test")
            else:
                raise ValueError("Config reload failed")

        # Mock the notifier and config loading
        with patch('voicenotify.main.load_config', side_effect=mock_load_config) as mock_load, \
             patch('voicenotify.main.send_notification') as mock_send:
            mock_send.return_value = True

            # Start main and trigger reload
            import voicenotify.main as main_module

            with caplog.at_level(logging.ERROR):
                # Trigger SIGHUP before processing event
                main_module.config_needs_reload = True

                with pytest.raises(SystemExit) as exc_info:
                    main()

        # Process should continue despite reload failure
        assert exc_info.value.code == 0
        assert "Failed to reload configuration" in caplog.text
        # Event should still be processed
        assert mock_send.call_count == 1
