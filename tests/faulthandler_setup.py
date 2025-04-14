"""Faulthandler setup for tests.

This module enables faulthandler for all tests to help debug segmentation faults.
Import this module at the top of any test file that might encounter segmentation faults.
"""

import atexit
import faulthandler
import os

# Enable faulthandler to debug segmentation faults
faulthandler.enable()

# Create a log directory for faulthandler output
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# Create a log file for faulthandler output
log_file_path = os.path.join(log_dir, "faulthandler.log")
fault_log = open(log_file_path, "w")
faulthandler.enable(file=fault_log)

# Register a cleanup function to close the log file
atexit.register(fault_log.close)
