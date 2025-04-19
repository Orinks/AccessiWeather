"""Force exit utility for AccessiWeather.

This module provides a direct force exit utility for AccessiWeather.
"""

import logging
import os
import sys
import threading
import time

logger = logging.getLogger(__name__)


def force_exit_after_delay(delay=0.5):
    """Force exit the application after a delay.
    
    Args:
        delay (float): Delay in seconds before forcing exit
    """
    logger.warning(f"Scheduling force exit after {delay} seconds")
    
    def _force_exit():
        logger.warning("Force exiting application with os._exit(0)")
        os._exit(0)
    
    # Schedule the force exit
    exit_timer = threading.Timer(delay, _force_exit)
    exit_timer.daemon = True
    exit_timer.start()
    
    # Also try sys.exit as a backup
    def _sys_exit():
        logger.warning("Attempting sys.exit(0) as backup")
        sys.exit(0)
    
    # Schedule sys.exit after a slightly shorter delay
    sys_exit_timer = threading.Timer(delay * 0.8, _sys_exit)
    sys_exit_timer.daemon = True
    sys_exit_timer.start()


def install_exit_handler():
    """Install a global exit handler that will be called when the application exits."""
    import atexit
    
    def _exit_handler():
        logger.warning("atexit handler called, forcing exit")
        force_exit_after_delay(0.1)
    
    atexit.register(_exit_handler)
