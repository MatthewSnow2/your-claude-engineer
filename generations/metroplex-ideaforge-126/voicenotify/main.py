"""Main entry point for VoiceNotify MCP Plugin."""

import sys
import signal
import logging
from voicenotify.config import load_config
from voicenotify.event_hook import parse_event, process_event
from voicenotify.notifier import send_notification


# Configure logging to match expected format
logging.basicConfig(
    format='[%(levelname)s] %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True


def handle_sigint(signum, frame):
    """Handle SIGINT (Ctrl-C) for graceful shutdown."""
    global running
    logger.info("Shutting down...")
    running = False


def main():
    """Main event loop - listen for events on stdin."""
    global running

    # Set up signal handler for clean shutdown
    signal.signal(signal.SIGINT, handle_sigint)

    # Load configuration
    try:
        config = load_config()
        logger.info(f"VoiceNotify started in {config.mode} mode")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Main event loop - read from stdin line by line
    try:
        while running:
            try:
                # Read line from stdin (blocking)
                line = sys.stdin.readline()

                # EOF reached
                if not line:
                    break

                # Strip whitespace
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Parse and validate event
                event = parse_event(line)

                if event is None:
                    # Error already logged by parse_event
                    continue

                # Process event and send notification
                event_type = process_event(event)
                send_notification(event_type, event.agent_id, config)

            except KeyboardInterrupt:
                # Handle Ctrl-C gracefully
                break
            except Exception as e:
                logger.error(f"Unexpected error processing event: {e}")
                continue

    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
        sys.exit(1)

    logger.info("Shutdown complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
