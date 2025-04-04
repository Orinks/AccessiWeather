"""Data migration utilities for AccessiWeather

This module provides utilities for migrating data from the old package name
to the new package name.
"""

import os
import shutil
import logging
# Unused imports commented out:
# import json
# from typing import Optional

logger = logging.getLogger(__name__)


def migrate_config_directory(
    old_dir: str = "~/.noaa_weather_app",
    new_dir: str = "~/.accessiweather"
) -> bool:
    """Migrate data from old config directory to new config directory
    
    Args:
        old_dir: Path to old config directory
        new_dir: Path to new config directory
        
    Returns:
        True if migration was successful or not needed, False if it failed
    """
    # Expand user paths
    old_dir = os.path.expanduser(old_dir)
    new_dir = os.path.expanduser(new_dir)
    
    # Check if old directory exists
    if not os.path.exists(old_dir):
        logger.info(f"Old config dir {old_dir} not found, skipping migration")
        return True
    
    # Check if new directory already has data
    if os.path.exists(new_dir) and os.listdir(new_dir):
        logger.info(f"New config dir {new_dir} has data, skipping migration")
        return True
    
    # Create new directory if it doesn't exist
    os.makedirs(new_dir, exist_ok=True)
    
    try:
        # Copy all files from old directory to new directory
        for filename in os.listdir(old_dir):
            old_file = os.path.join(old_dir, filename)
            new_file = os.path.join(new_dir, filename)
            
            if os.path.isfile(old_file):
                shutil.copy2(old_file, new_file)
                logger.info(f"Migrated {filename} from {old_dir} to {new_dir}")
            elif os.path.isdir(old_file):
                shutil.copytree(old_file, new_file, dirs_exist_ok=True)
                logger.info(f"Migrated dir {filename} to {new_dir}")
        
        logger.info(f"Successfully migrated data from {old_dir} to {new_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed migration from {old_dir} to {new_dir}: {e}")
        return False
