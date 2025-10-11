"""
Compatibility adapter for the Sound Pack Manager dialog.

This module re-exports the new modular implementation to preserve existing
imports (tests and callers may import SoundPackManagerDialog from here).
"""

from __future__ import annotations

from .soundpack_manager import SoundPackManagerDialog

__all__ = ["SoundPackManagerDialog"]
