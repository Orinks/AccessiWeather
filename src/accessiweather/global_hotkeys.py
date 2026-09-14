"""
System-wide hotkey registration.

Unlike the accelerator table in :mod:`accessiweather.app_shortcuts`, these
hotkeys fire while AccessiWeather has no focus at all -- including while it is
hidden in the system tray.  Windows is the only platform wxWidgets implements
``RegisterHotKey`` on, so everywhere else this degrades to a logged no-op.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

import wx

from .models.config_constants import DEFAULT_NOAA_RADIO_HOTKEY

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_NOAA_RADIO_HOTKEY",
    "GlobalHotkeyManager",
    "HotkeyParseError",
    "is_supported",
    "normalize_hotkey",
    "parse_hotkey",
]

# Canonical order keeps normalized combos stable no matter how the user typed
# them, so a saved setting always round-trips to the same string.
_MODIFIERS: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("Ctrl", wx.MOD_CONTROL, ("ctrl", "control")),
    ("Alt", wx.MOD_ALT, ("alt",)),
    ("Shift", wx.MOD_SHIFT, ("shift",)),
    ("Win", wx.MOD_WIN, ("win", "super", "cmd", "command")),
)
_MODIFIER_LOOKUP = {
    alias: (label, flag) for label, flag, aliases in _MODIFIERS for alias in aliases
}
_MAX_FUNCTION_KEY = 24


class HotkeyParseError(ValueError):
    """Raised when a hotkey string cannot be turned into a wx key binding."""


def parse_hotkey(combo: str) -> tuple[int, int]:
    """
    Return the ``(modifier flags, keycode)`` pair for a combo such as ``Ctrl+Alt+Shift+R``.

    At least one modifier is required: a global hotkey with no modifier would
    swallow that key in every other application on the system.
    """
    if not isinstance(combo, str):
        raise HotkeyParseError(f"Hotkey must be a string, got {type(combo).__name__}")

    parts = [part.strip() for part in combo.split("+")]
    if len(parts) < 2 or any(not part for part in parts):
        raise HotkeyParseError(f"Hotkey must be modifiers plus a key, got {combo!r}")

    flags = 0
    for part in parts[:-1]:
        modifier = _MODIFIER_LOOKUP.get(part.lower())
        if modifier is None:
            raise HotkeyParseError(f"Unknown modifier {part!r} in hotkey {combo!r}")
        flags |= modifier[1]

    return flags, _parse_key(parts[-1], combo)


def _parse_key(key: str, combo: str) -> int:
    """Return the wx keycode for the final segment of a hotkey combo."""
    normalized = key.upper()
    if len(normalized) == 1 and (normalized.isalpha() or normalized.isdigit()):
        return ord(normalized)

    if normalized.startswith("F") and normalized[1:].isdigit():
        number = int(normalized[1:])
        if 1 <= number <= _MAX_FUNCTION_KEY:
            return wx.WXK_F1 + number - 1

    raise HotkeyParseError(f"Unsupported key {key!r} in hotkey {combo!r}")


def normalize_hotkey(combo: str) -> str:
    """Return the canonical spelling of a hotkey combo, e.g. ``Ctrl+Alt+Shift+R``."""
    flags, keycode = parse_hotkey(combo)
    labels = [label for label, flag, _aliases in _MODIFIERS if flags & flag]
    return "+".join([*labels, _format_key(keycode)])


def _format_key(keycode: int) -> str:
    """Return the display spelling of a wx keycode."""
    if wx.WXK_F1 <= keycode <= wx.WXK_F1 + _MAX_FUNCTION_KEY - 1:
        return f"F{keycode - wx.WXK_F1 + 1}"
    return chr(keycode)


def is_supported() -> bool:
    """Return whether this platform can register system-wide hotkeys."""
    return sys.platform == "win32"


class GlobalHotkeyManager:
    """Keeps a single system-wide hotkey in sync with its configured combo."""

    def __init__(
        self,
        window: wx.Window,
        on_trigger: Callable[[], None],
        *,
        hotkey_id: int | None = None,
    ) -> None:
        """Bind the hotkey event on ``window`` and remember its trigger callback."""
        self._window = window
        self._on_trigger = on_trigger
        self.hotkey_id = wx.ID_HIGHEST + 1001 if hotkey_id is None else hotkey_id
        self._registered_combo: str | None = None
        self._bound = False

    @property
    def registered_combo(self) -> str | None:
        """Return the combo currently registered with the OS, or None."""
        return self._registered_combo

    def apply(self, combo: str | None) -> bool:
        """
        Register ``combo``, replacing any previously registered hotkey.

        An empty combo means "disabled" and succeeds without registering.
        Returns whether the requested state was reached.
        """
        self.unregister()

        if not combo or not combo.strip():
            return True

        if not is_supported():
            logger.info("System-wide hotkeys are only supported on Windows; %s ignored", combo)
            return False

        try:
            flags, keycode = parse_hotkey(combo)
        except HotkeyParseError as exc:
            logger.warning("Could not register global hotkey: %s", exc)
            return False

        try:
            registered = bool(self._window.RegisterHotKey(self.hotkey_id, flags, keycode))
        except Exception as exc:
            logger.warning("Registering global hotkey %s failed: %s", combo, exc)
            return False

        if not registered:
            logger.warning("Windows refused global hotkey %s; another app likely owns it", combo)
            return False

        self._bind_once()
        self._registered_combo = normalize_hotkey(combo)
        logger.info("Registered global hotkey %s", self._registered_combo)
        return True

    def unregister(self) -> None:
        """Release the hotkey back to the OS, if one is registered."""
        if self._registered_combo is None:
            return
        try:
            self._window.UnregisterHotKey(self.hotkey_id)
        except Exception as exc:
            logger.debug("Unregistering global hotkey failed: %s", exc)
        self._registered_combo = None

    def _bind_once(self) -> None:
        """Attach the hotkey event handler the first time a combo registers."""
        if self._bound:
            return
        self._window.Bind(wx.EVT_HOTKEY, self._handle_hotkey, id=self.hotkey_id)
        self._bound = True

    def _handle_hotkey(self, _event) -> None:
        """Run the trigger callback, keeping wx's event loop safe from its errors."""
        try:
            self._on_trigger()
        except Exception:
            logger.exception("Global hotkey handler failed")
