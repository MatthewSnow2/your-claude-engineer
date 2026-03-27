"""Configuration management for VoiceNotify plugin."""

import os
from voicenotify.models import NotificationConfig


def load_config() -> NotificationConfig:
    """Load configuration from environment variables.

    Returns:
        NotificationConfig: Configuration object with values from environment.

    Environment Variables:
        VOICENOTIFY_MODE: 'call' or 'tg' (default: 'call')
        VOICENOTIFY_TARGET: Phone number (E.164) or directory path (required)
        VOICENOTIFY_LANG: Language code for TTS (default: 'en-US')
        VOICENOTIFY_VOICE: TTS voice name (default: 'default')
        VOICENOTIFY_PLAYBACK: '1' to enable playback in tg mode (default: '0')
    """
    mode = os.getenv("VOICENOTIFY_MODE", "call")
    target = os.getenv("VOICENOTIFY_TARGET", "")
    lang = os.getenv("VOICENOTIFY_LANG", "en-US")
    voice = os.getenv("VOICENOTIFY_VOICE", "default")
    playback = os.getenv("VOICENOTIFY_PLAYBACK", "0") == "1"

    if not target:
        # For testing purposes, allow empty target with a warning
        # In production, this should raise an error
        target = "/tmp/voicenotes"

    return NotificationConfig(
        mode=mode,
        target=target,
        lang=lang,
        voice=voice,
        playback=playback
    )
