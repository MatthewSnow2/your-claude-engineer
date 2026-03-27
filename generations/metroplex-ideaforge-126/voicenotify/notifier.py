"""Notification delivery for VoiceNotify plugin."""

import logging
import os
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from typing import Optional, List

from voicenotify.models import NotificationConfig
from voicenotify.utils import generate_voice_note_filename, sanitize_agent_id


logger = logging.getLogger(__name__)


class BaseNotifier(ABC):
    """Base class for notification delivery."""

    def __init__(self, config: NotificationConfig):
        """Initialize notifier with configuration.

        Args:
            config: Notification configuration
        """
        self.config = config

    def _escape_for_shell(self, text: str, shell_type: str) -> str:
        """Escape text for safe inclusion in shell commands.

        Args:
            text: Text to escape
            shell_type: Type of shell ('powershell' or 'osascript')

        Returns:
            str: Escaped text safe for shell injection
        """
        if shell_type == 'powershell':
            # In PowerShell single-quoted strings, escape ' with ''
            return text.replace("'", "''")
        elif shell_type == 'osascript':
            # In AppleScript/osascript double-quoted strings, escape " with \"
            return text.replace('"', '\\"')
        else:
            # Default: escape single quotes
            return text.replace("'", "'\\''")

    @abstractmethod
    def send(self, event_type: str, agent_id: str, ts: int) -> bool:
        """Send notification for an agent event.

        Args:
            event_type: Event type (e.g., 'completed', 'stalled', 'need_decision')
            agent_id: Agent identifier
            ts: Unix timestamp

        Returns:
            bool: True if notification sent successfully, False otherwise
        """
        pass


class CallNotifier(BaseNotifier):
    """Notifier that places outbound phone calls."""

    # Supported telephony CLI tools in order of preference
    TELEPHONY_TOOLS = [
        ("mmcli", ["mmcli", "-m", "0", "--voice-create-call", "number={target}"]),
        ("termux-telephony-call", ["termux-telephony-call", "{target}"]),
        ("adb", ["adb", "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", "tel:{target}"]),
        ("osascript", ["osascript", "-e", 'tell application "FaceTime" to open location "tel:{target}"']),
    ]

    def __init__(self, config: NotificationConfig):
        """Initialize call notifier.

        Args:
            config: Notification configuration
        """
        super().__init__(config)
        self.telephony_tool = self._detect_telephony_tool()

    def _detect_telephony_tool(self) -> Optional[tuple[str, List[str]]]:
        """Detect available telephony CLI tool.

        Returns:
            Optional[tuple]: (tool_name, command_template) or None if no tool found
        """
        for tool_name, command_template in self.TELEPHONY_TOOLS:
            if shutil.which(tool_name):
                logger.info(f"Detected telephony tool: {tool_name}")
                return (tool_name, command_template)

        logger.warning("No telephony CLI tool found in PATH")
        return None

    def send(self, event_type: str, agent_id: str, ts: int) -> bool:
        """Place outbound phone call.

        Args:
            event_type: Event type
            agent_id: Agent identifier
            ts: Unix timestamp

        Returns:
            bool: True if call placed successfully, False otherwise
        """
        if self.telephony_tool is None:
            logger.error("Cannot place call: no telephony tool available")
            return False

        tool_name, command_template = self.telephony_tool

        # Escape target for osascript to prevent command injection
        target_value = self.config.target
        if tool_name == "osascript":
            target_value = self._escape_for_shell(target_value, 'osascript')

        # Build command with actual target phone number
        command = [
            arg.replace("{target}", target_value)
            for arg in command_template
        ]

        logger.info(f"Placing call to {self.config.target} for agent {agent_id} event {event_type}")

        # Retry up to 2 times on failure
        for attempt in range(3):
            try:
                result = subprocess.run(
                    command,
                    timeout=5.0,
                    capture_output=True,
                    check=False
                )

                if result.returncode == 0:
                    logger.info(f"Call placed successfully (attempt {attempt + 1})")
                    return True

                logger.warning(f"Call failed with return code {result.returncode} (attempt {attempt + 1})")

                if attempt < 2:
                    time.sleep(0.1)

            except subprocess.TimeoutExpired:
                logger.warning(f"Call timed out (attempt {attempt + 1})")
                if attempt < 2:
                    time.sleep(0.1)
                continue
            except Exception as e:
                logger.error(f"Call failed with exception: {e}")
                return False

        logger.error("Call failed after 3 attempts")
        return False


class TelegramNotifier(BaseNotifier):
    """Notifier that generates voice notes for Telegram."""

    # Supported TTS engines with their command templates
    TTS_ENGINES = [
        ("say", ["say", "-o", "{output}", "-v", "{voice}", "{text}"]),  # macOS
        ("espeak-ng", ["espeak-ng", "-w", "{output}", "{text}"]),  # Linux
        ("pico2wave", ["pico2wave", "-w", "{output}", "-l", "{lang}", "{text}"]),  # Linux (alternative)
        ("powershell", ["powershell", "-Command", "Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.SetOutputToWaveFile('{output}'); $synth.Speak('{text}'); $synth.Dispose()"]),  # Windows
    ]

    def __init__(self, config: NotificationConfig):
        """Initialize Telegram notifier.

        Args:
            config: Notification configuration
        """
        super().__init__(config)
        self.tts_engine = self._detect_tts_engine()

    def _detect_tts_engine(self) -> Optional[tuple[str, List[str]]]:
        """Detect available TTS engine.

        Returns:
            Optional[tuple]: (engine_name, command_template) or None if no engine found
        """
        for engine_name, command_template in self.TTS_ENGINES:
            if shutil.which(engine_name):
                logger.info(f"Detected TTS engine: {engine_name}")
                return (engine_name, command_template)

        logger.warning("No TTS engine found in PATH")
        return None

    def _synthesize_speech(self, text: str, output_path: str) -> bool:
        """Synthesize speech to WAV file.

        Args:
            text: Text to synthesize
            output_path: Path to output WAV file

        Returns:
            bool: True if synthesis succeeded, False otherwise
        """
        if self.tts_engine is None:
            logger.error("Cannot synthesize speech: no TTS engine available")
            return False

        engine_name, command_template = self.tts_engine

        # Escape text for PowerShell to prevent command injection
        text_value = text
        if engine_name == "powershell":
            text_value = self._escape_for_shell(text, 'powershell')

        # Build command with actual parameters
        command = []
        for arg in command_template:
            arg = arg.replace("{output}", output_path)
            arg = arg.replace("{text}", text_value)
            arg = arg.replace("{voice}", self.config.voice)
            arg = arg.replace("{lang}", self.config.lang)
            command.append(arg)

        logger.info(f"Synthesizing speech with {engine_name}")

        try:
            result = subprocess.run(
                command,
                timeout=10.0,
                capture_output=True,
                check=False
            )

            if result.returncode == 0:
                logger.info("Speech synthesis succeeded")
                return True

            logger.error(f"Speech synthesis failed with return code {result.returncode}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("Speech synthesis timed out")
            return False
        except Exception as e:
            logger.error(f"Speech synthesis failed with exception: {e}")
            return False

    def _convert_to_ogg(self, wav_path: str, ogg_path: str) -> bool:
        """Convert WAV file to Ogg Vorbis format.

        Args:
            wav_path: Path to input WAV file
            ogg_path: Path to output OGG file

        Returns:
            bool: True if conversion succeeded, False otherwise
        """
        # Check if ffmpeg is available
        if shutil.which("ffmpeg"):
            command = [
                "ffmpeg", "-i", wav_path,
                "-c:a", "libvorbis",
                "-ar", "16000",
                "-ac", "1",
                "-y",  # Overwrite output file
                ogg_path
            ]

            try:
                result = subprocess.run(
                    command,
                    timeout=10.0,
                    capture_output=True,
                    check=False
                )

                if result.returncode == 0:
                    logger.info("Converted WAV to Ogg Vorbis")
                    return True

                logger.warning(f"ffmpeg conversion failed with return code {result.returncode}")
                return False

            except subprocess.TimeoutExpired:
                logger.error("ffmpeg conversion timed out")
                return False
            except Exception as e:
                logger.error(f"ffmpeg conversion failed: {e}")
                return False
        else:
            # Fallback: just copy WAV file with .ogg extension
            logger.warning("ffmpeg not available, saving as WAV with .ogg extension")
            try:
                shutil.copy2(wav_path, ogg_path)
                return True
            except Exception as e:
                logger.error(f"Failed to copy WAV file: {e}")
                return False

    def _playback_audio(self, audio_path: str) -> bool:
        """Play back audio file locally.

        Args:
            audio_path: Path to audio file

        Returns:
            bool: True if playback succeeded, False otherwise
        """
        # Detect available audio player
        players = [
            ("afplay", ["afplay", audio_path]),  # macOS
            ("paplay", ["paplay", audio_path]),  # Linux (PulseAudio)
            ("aplay", ["aplay", audio_path]),  # Linux (ALSA)
            ("mpg123", ["mpg123", audio_path]),  # Cross-platform
            ("ffplay", ["ffplay", "-nodisp", "-autoexit", audio_path]),  # Cross-platform
        ]

        for player_name, command in players:
            if shutil.which(player_name):
                logger.info(f"Playing back audio with {player_name}")
                try:
                    subprocess.run(
                        command,
                        timeout=30.0,
                        capture_output=True,
                        check=False
                    )
                    return True
                except Exception as e:
                    logger.warning(f"Playback with {player_name} failed: {e}")
                    continue

        logger.warning("No audio player found for playback")
        return False

    def send(self, event_type: str, agent_id: str, ts: int) -> bool:
        """Generate and save voice note.

        Args:
            event_type: Event type
            agent_id: Agent identifier
            ts: Unix timestamp

        Returns:
            bool: True if voice note created successfully, False otherwise
        """
        if self.tts_engine is None:
            logger.error("Cannot create voice note: no TTS engine available")
            return False

        # Create target directory if it doesn't exist
        try:
            os.makedirs(self.config.target, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create target directory {self.config.target}: {e}")
            return False

        # Generate filename
        try:
            filename = generate_voice_note_filename(ts, agent_id, f"agent.{event_type}")
            output_path = os.path.join(self.config.target, filename)
        except ValueError as e:
            logger.error(f"Failed to generate filename: {e}")
            return False

        # Sanitize agent_id to prevent command injection
        safe_agent_id = sanitize_agent_id(agent_id)

        # Synthesize message
        message = f"Agent {safe_agent_id} has {event_type}"
        logger.info(f"Creating voice note: {message}")

        # Create temporary WAV file
        temp_wav = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_wav = f.name

            # Synthesize speech to WAV
            if not self._synthesize_speech(message, temp_wav):
                return False

            # Convert to Ogg Vorbis
            if not self._convert_to_ogg(temp_wav, output_path):
                return False

            logger.info(f"Voice note saved to {output_path}")

            # Optional playback
            if self.config.playback:
                self._playback_audio(output_path)

            return True

        finally:
            # Clean up temporary WAV file
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                    logger.debug(f"Cleaned up temporary file {temp_wav}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_wav}: {e}")


def create_notifier(config: NotificationConfig) -> BaseNotifier:
    """Factory function to create appropriate notifier based on config.

    Args:
        config: Notification configuration

    Returns:
        BaseNotifier: Notifier instance (CallNotifier or TelegramNotifier)

    Raises:
        ValueError: If mode is invalid
    """
    if config.mode == "call":
        return CallNotifier(config)
    elif config.mode == "tg":
        return TelegramNotifier(config)
    else:
        raise ValueError(f"Invalid mode: {config.mode}")


def send_notification(event_type: str, agent_id: str, config: NotificationConfig) -> bool:
    """Send notification for an agent event.

    Args:
        event_type: Event type (e.g., 'completed', 'stalled', 'need_decision')
        agent_id: Agent identifier
        config: Notification configuration

    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    try:
        notifier = create_notifier(config)
        ts = int(time.time())
        return notifier.send(event_type, agent_id, ts)
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False
