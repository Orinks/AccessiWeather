"""Memory tracking utilities for debugging wxPython memory issues.

This module provides utilities for tracking memory usage and identifying
potential memory leaks in wxPython applications.
"""

import gc
import logging
import sys
import tracemalloc
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import wx

logger = logging.getLogger(__name__)


class MemoryTracker:
    """Track memory usage and identify potential memory leaks."""

    def __init__(self):
        """Initialize the memory tracker."""
        self.tracemalloc_enabled = False
        self.tracked_objects: Dict[int, Any] = {}
        self.tracked_types: Set[type] = set()

    def start(self):
        """Start tracking memory usage."""
        # Enable tracemalloc if available
        try:
            tracemalloc.start()
            self.tracemalloc_enabled = True
            logger.info("Tracemalloc enabled")
        except Exception as e:
            logger.warning(f"Failed to enable tracemalloc: {e}")
            self.tracemalloc_enabled = False

        # Force garbage collection
        gc.collect()

    def stop(self):
        """Stop tracking memory usage."""
        if self.tracemalloc_enabled:
            try:
                tracemalloc.stop()
                logger.info("Tracemalloc disabled")
            except Exception as e:
                logger.warning(f"Failed to disable tracemalloc: {e}")

        # Clear tracked objects
        self.tracked_objects.clear()
        self.tracked_types.clear()

    def take_snapshot(self) -> Optional[tracemalloc.Snapshot]:
        """Take a snapshot of current memory usage.

        Returns:
            A tracemalloc snapshot if tracemalloc is enabled, None otherwise
        """
        if self.tracemalloc_enabled:
            try:
                return tracemalloc.take_snapshot()
            except Exception as e:
                logger.warning(f"Failed to take tracemalloc snapshot: {e}")
        return None

    def compare_snapshots(
        self, snapshot1: tracemalloc.Snapshot, snapshot2: tracemalloc.Snapshot, top_n: int = 10
    ):
        """Compare two memory snapshots and log the differences.

        Args:
            snapshot1: First snapshot
            snapshot2: Second snapshot
            top_n: Number of top differences to log
        """
        if not self.tracemalloc_enabled:
            logger.warning("Tracemalloc not enabled, cannot compare snapshots")
            return

        # Compare snapshots
        try:
            stats = snapshot2.compare_to(snapshot1, "lineno")
            logger.info(f"Top {top_n} memory differences:")
            for stat in stats[:top_n]:
                logger.info(f"{stat}")
        except Exception as e:
            logger.warning(f"Failed to compare tracemalloc snapshots: {e}")

    def track_object(self, obj: Any, name: str = None):
        """Track a specific object to monitor its lifecycle.

        Args:
            obj: Object to track
            name: Optional name for the object
        """
        obj_id = id(obj)
        obj_name = name or f"{type(obj).__name__}_{obj_id}"
        self.tracked_objects[obj_id] = (obj, obj_name)
        logger.debug(f"Tracking object {obj_name} (id={obj_id})")

    def track_type(self, obj_type: type):
        """Track all instances of a specific type.

        Args:
            obj_type: Type to track
        """
        self.tracked_types.add(obj_type)
        logger.debug(f"Tracking all instances of {obj_type.__name__}")

    def check_tracked_objects(self):
        """Check if tracked objects still exist and log their status."""
        # Check individual tracked objects
        for obj_id, (obj_ref, obj_name) in list(self.tracked_objects.items()):
            try:
                # This will raise an exception if the object has been garbage collected
                obj_type = type(obj_ref)
                logger.debug(
                    f"Object {obj_name} (id={obj_id}, type={obj_type.__name__}) still exists"
                )
            except Exception:
                logger.debug(f"Object {obj_name} (id={obj_id}) has been garbage collected")
                del self.tracked_objects[obj_id]

    def count_objects_by_type(self) -> Dict[str, int]:
        """Count objects by type.

        Returns:
            Dictionary mapping type names to counts
        """
        counts = defaultdict(int)
        for obj in gc.get_objects():
            counts[type(obj).__name__] += 1
        return dict(counts)

    def log_object_counts(self, top_n: int = 20):
        """Log counts of objects by type.

        Args:
            top_n: Number of top types to log
        """
        counts = self.count_objects_by_type()
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        logger.info(f"Top {top_n} object types by count:")
        for type_name, count in sorted_counts[:top_n]:
            logger.info(f"{type_name}: {count}")

    def find_wx_objects(self) -> List[Tuple[wx.Object, str]]:
        """Find all wxPython objects in memory.

        Returns:
            List of (object, type_name) tuples
        """
        wx_objects = []
        for obj in gc.get_objects():
            if isinstance(obj, wx.Object):
                wx_objects.append((obj, type(obj).__name__))
        return wx_objects

    def log_wx_objects(self):
        """Log all wxPython objects in memory."""
        wx_objects = self.find_wx_objects()
        logger.info(f"Found {len(wx_objects)} wxPython objects in memory")

        # Count by type
        type_counts = defaultdict(int)
        for _, type_name in wx_objects:
            type_counts[type_name] += 1

        # Log counts by type
        logger.info("wxPython objects by type:")
        for type_name, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"{type_name}: {count}")


# Global instance for convenience
memory_tracker = MemoryTracker()


def start_tracking():
    """Start tracking memory usage."""
    memory_tracker.start()


def stop_tracking():
    """Stop tracking memory usage."""
    memory_tracker.stop()


def log_memory_stats():
    """Log memory statistics."""
    memory_tracker.log_object_counts()
    memory_tracker.log_wx_objects()


def track_object(obj: Any, name: str = None):
    """Track a specific object to monitor its lifecycle."""
    memory_tracker.track_object(obj, name)


def track_type(obj_type: type):
    """Track all instances of a specific type."""
    memory_tracker.track_type(obj_type)
