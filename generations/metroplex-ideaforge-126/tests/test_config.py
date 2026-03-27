"""Tests for config module."""

import os
import pytest
from voicenotify.config import load_config
from voicenotify.models import NotificationConfig


class TestLoadConfig:
    """Tests for load_config function."""

    def test_default_config(self, monkeypatch):
        """Test loading config with default values."""
        # Clear all VOICENOTIFY_ env vars
        for key in list(os.environ.keys()):
            if key.startswith("VOICENOTIFY_"):
                monkeypatch.delenv(key, raising=False)

        # Set only required target (valid phone number for call mode)
        monkeypatch.setenv("VOICENOTIFY_TARGET", "+15551234567")

        config = load_config()

        assert config.mode == "call"
        assert config.target == "+15551234567"
        assert config.lang == "en-US"
        assert config.voice == "default"
        assert config.playback is False

    def test_custom_config(self, monkeypatch):
        """Test loading config with custom values."""
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/custom/path")
        monkeypatch.setenv("VOICENOTIFY_LANG", "fr-FR")
        monkeypatch.setenv("VOICENOTIFY_VOICE", "custom-voice")
        monkeypatch.setenv("VOICENOTIFY_PLAYBACK", "1")

        config = load_config()

        assert config.mode == "tg"
        assert config.target == "/custom/path"
        assert config.lang == "fr-FR"
        assert config.voice == "custom-voice"
        assert config.playback is True

    def test_call_mode_config(self, monkeypatch):
        """Test loading config in call mode."""
        monkeypatch.setenv("VOICENOTIFY_MODE", "call")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "+15551234567")

        config = load_config()

        assert config.mode == "call"
        assert config.target == "+15551234567"

    def test_playback_disabled_by_default(self, monkeypatch):
        """Test that playback is disabled by default."""
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")
        monkeypatch.delenv("VOICENOTIFY_PLAYBACK", raising=False)

        config = load_config()

        assert config.playback is False

    def test_playback_enabled_with_1(self, monkeypatch):
        """Test that playback is enabled with value '1'."""
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")
        monkeypatch.setenv("VOICENOTIFY_PLAYBACK", "1")

        config = load_config()

        assert config.playback is True

    def test_playback_disabled_with_0(self, monkeypatch):
        """Test that playback is disabled with value '0'."""
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")
        monkeypatch.setenv("VOICENOTIFY_PLAYBACK", "0")

        config = load_config()

        assert config.playback is False

    def test_playback_disabled_with_other_value(self, monkeypatch):
        """Test that playback is disabled with non-'1' value."""
        monkeypatch.setenv("VOICENOTIFY_MODE", "tg")
        monkeypatch.setenv("VOICENOTIFY_TARGET", "/tmp/test")
        monkeypatch.setenv("VOICENOTIFY_PLAYBACK", "yes")

        config = load_config()

        assert config.playback is False

    def test_empty_target_raises(self, monkeypatch):
        """Test that missing target raises ValueError."""
        for key in list(os.environ.keys()):
            if key.startswith("VOICENOTIFY_"):
                monkeypatch.delenv(key, raising=False)

        # Should raise ValueError when target is not set
        with pytest.raises(ValueError, match="VOICENOTIFY_TARGET environment variable must be set"):
            load_config()
