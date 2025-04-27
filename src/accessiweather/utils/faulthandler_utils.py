"""Faulthandler utilities for AccessiWeather.

This module provides utilities for capturing segmentation faults and other
critical errors using Python's faulthandler module.
"""

import faulthandler
import logging
import os
import sys
from pathlib import Path
from typing import Optional, TextIO, Union

logger = logging.getLogger(__name__)

# Global variable to keep track of the log file
_fault_log_file: Optional[TextIO] = None


def enable_faulthandler(
    log_file_path: Optional[Union[str, Path]] = None,
    all_threads: bool = True,
    register_all_signals: bool = False,
) -> Path:
    """Enable faulthandler with logging to both console and file.

    Args:
        log_file_path: Path to the log file. If None, a file will be created in
            the user's AccessiWeather_logs directory.
        all_threads: Whether to dump tracebacks for all threads (default: True)

    Returns:
        Path to the log file
    """
    global _fault_log_file

    # Close any existing file
    if _fault_log_file is not None:
        try:
            _fault_log_file.close()
        except Exception as e:
            logger.warning(f"Error closing existing fault log file: {e}")
        _fault_log_file = None

    # Enable faulthandler for stderr (console output)
    faulthandler.enable(file=sys.stderr, all_threads=all_threads)

    # Register for common signals if requested
    if register_all_signals and sys.platform != "win32":
        try:
            import signal

            # Check if the signals are available
            if hasattr(signal, "SIGUSR1") and hasattr(signal, "SIGUSR2"):
                # Use getattr to avoid mypy errors
                sigusr1 = getattr(signal, "SIGUSR1")
                sigusr2 = getattr(signal, "SIGUSR2")
                for sig in (sigusr1, sigusr2):
                    if hasattr(faulthandler, "register"):
                        faulthandler.register(sig, file=sys.stderr, all_threads=all_threads)
                logger.info("Registered faulthandler for user signals")
            else:
                logger.warning("User signals (SIGUSR1, SIGUSR2) not available on this platform")
        except (ImportError, AttributeError) as e:
            logger.warning(f"Could not register signal handlers: {e}")

    # Create log file path if not provided
    if log_file_path is None:
        log_dir = Path.home() / "AccessiWeather_logs"
        log_dir.mkdir(exist_ok=True)
        log_file_path = log_dir / "faulthandler.log"
    else:
        log_file_path = Path(log_file_path)

    # Create parent directories if they don't exist
    log_file_path.parent.mkdir(exist_ok=True, parents=True)

    try:
        # Open the log file in append mode
        _fault_log_file = open(log_file_path, "a", encoding="utf-8")

        # Write a header to the log file
        _fault_log_file.write("\n" + "=" * 80 + "\n")
        _fault_log_file.write(f"Faulthandler enabled at {log_file_path}\n")
        _fault_log_file.write("=" * 80 + "\n")
        _fault_log_file.flush()

        # Enable faulthandler for the log file
        faulthandler.enable(file=_fault_log_file, all_threads=all_threads)

        logger.info(f"Faulthandler enabled, logging to {log_file_path}")
        return log_file_path

    except Exception as e:
        logger.error(f"Failed to enable faulthandler with file logging: {e}")
        # Ensure faulthandler is at least enabled for stderr
        faulthandler.enable(file=sys.stderr, all_threads=all_threads)
        return Path(os.devnull)


def dump_traceback(all_threads: bool = True) -> None:
    """Manually dump the current Python traceback.

    This is useful for debugging deadlocks or other issues where you want
    to see the current state of all threads.

    Args:
        all_threads: Whether to dump tracebacks for all threads (default: True)
    """
    # Dump to stderr
    faulthandler.dump_traceback(file=sys.stderr, all_threads=all_threads)

    # Dump to log file if available
    global _fault_log_file
    if _fault_log_file is not None:
        try:
            _fault_log_file.write("\n" + "=" * 80 + "\n")
            _fault_log_file.write("Manual traceback dump:\n")
            _fault_log_file.write("=" * 80 + "\n")
            _fault_log_file.flush()
            faulthandler.dump_traceback(file=_fault_log_file, all_threads=all_threads)
            _fault_log_file.flush()
        except Exception as e:
            logger.error(f"Failed to dump traceback to log file: {e}")


def register_signal_handler(signum: int, all_threads: bool = True, chain: bool = True) -> None:
    """Register a signal handler to dump the traceback when the signal is received.

    Args:
        signum: Signal number to register for
        all_threads: Whether to dump tracebacks for all threads (default: True)
        chain: Whether to call the previous signal handler (default: True)
    """
    # Register for stderr
    try:
        if hasattr(faulthandler, "register"):
            faulthandler.register(signum, file=sys.stderr, all_threads=all_threads, chain=chain)

            # Register for log file if available
            global _fault_log_file
            if _fault_log_file is not None:
                faulthandler.register(
                    signum, file=_fault_log_file, all_threads=all_threads, chain=chain
                )

            logger.info(f"Registered faulthandler for signal {signum}")
        else:
            logger.warning("faulthandler.register is not available on this platform")
    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to register faulthandler for signal {signum}: {e}")


def disable_faulthandler() -> None:
    """Disable faulthandler and close the log file."""
    faulthandler.disable()

    global _fault_log_file
    if _fault_log_file is not None:
        try:
            _fault_log_file.close()
        except Exception as e:
            logger.warning(f"Error closing fault log file: {e}")
        _fault_log_file = None

    logger.info("Faulthandler disabled")
