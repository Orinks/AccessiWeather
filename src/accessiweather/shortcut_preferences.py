"""Helpers for configurable window and tray shortcuts."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT = "Ctrl+Shift+W"
DEFAULT_HIDE_MAIN_WINDOW_SHORTCUT = "Ctrl+Shift+M"
DEFAULT_READ_TRAY_INFO_SHORTCUT = "Ctrl+Shift+I"

_MODIFIER_ALIASES = {
    "ALT": "Alt",
    "CTRL": "Ctrl",
    "CONTROL": "Ctrl",
    "CMD": "Ctrl",
    "COMMAND": "Ctrl",
    "OPTION": "Alt",
    "SHIFT": "Shift",
}
_SPECIAL_KEYS = {
    "ESC": "Escape",
    "ESCAPE": "Escape",
    "SPACE": "Space",
    "TAB": "Tab",
}
_VISIBLE_MODIFIER_ORDER = ("Ctrl", "Alt", "Shift")
_ACCELERATOR_MODIFIER_NAMES = {
    "Ctrl": "ACCEL_CTRL",
    "Alt": "ACCEL_ALT",
    "Shift": "ACCEL_SHIFT",
}
_HOTKEY_MODIFIER_NAMES = {
    "Ctrl": ("MOD_CONTROL", "ACCEL_CTRL"),
    "Alt": ("MOD_ALT", "ACCEL_ALT"),
    "Shift": ("MOD_SHIFT", "ACCEL_SHIFT"),
}
_SPECIAL_KEY_CODE_NAMES = {
    "Escape": ("WXK_ESCAPE", 27),
    "Space": ("WXK_SPACE", 32),
    "Tab": ("WXK_TAB", 9),
}


@dataclass(frozen=True)
class ShortcutPreference:
    setting_name: str
    label: str
    default: str
    handler_name: str


@dataclass(frozen=True)
class ShortcutBinding:
    modifiers: tuple[str, ...]
    key: str

    @property
    def normalized(self) -> str:
        parts = [*self.modifiers, self.key]
        return "+".join(parts)

    def accelerator_flags(self, wx_module) -> int:
        flags = getattr(wx_module, "ACCEL_NORMAL", 0)
        for modifier in self.modifiers:
            flags |= getattr(wx_module, _ACCELERATOR_MODIFIER_NAMES[modifier], 0)
        return flags

    def hotkey_modifiers(self, wx_module) -> int:
        flags = 0
        for modifier in self.modifiers:
            primary_name, fallback_name = _HOTKEY_MODIFIER_NAMES[modifier]
            flags |= getattr(wx_module, primary_name, getattr(wx_module, fallback_name, 0))
        return flags

    def key_code(self, wx_module) -> int:
        if len(self.key) == 1:
            return ord(self.key)
        if self.key.startswith("F") and self.key[1:].isdigit():
            f_key_name = f"WXK_{self.key}"
            value = getattr(wx_module, f_key_name, None)
            if value is None:
                raise ValueError(f"{self.key} is not available in this wx build.")
            return value
        if self.key in _SPECIAL_KEY_CODE_NAMES:
            attr_name, fallback = _SPECIAL_KEY_CODE_NAMES[self.key]
            return getattr(wx_module, attr_name, fallback)
        raise ValueError(f"Unsupported shortcut key {self.key!r}.")


WINDOW_TRAY_SHORTCUTS: tuple[ShortcutPreference, ...] = (
    ShortcutPreference(
        setting_name="shortcut_show_main_window",
        label="Show main window shortcut",
        default=DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT,
        handler_name="_on_show_main_window_shortcut",
    ),
    ShortcutPreference(
        setting_name="shortcut_hide_main_window",
        label="Hide window shortcut",
        default=DEFAULT_HIDE_MAIN_WINDOW_SHORTCUT,
        handler_name="_on_hide_main_window_shortcut",
    ),
    ShortcutPreference(
        setting_name="shortcut_read_tray_info",
        label="Read tray information shortcut",
        default=DEFAULT_READ_TRAY_INFO_SHORTCUT,
        handler_name="_on_read_tray_info_shortcut",
    ),
)

WINDOW_TRAY_SHORTCUT_DEFAULTS = {
    preference.setting_name: preference.default for preference in WINDOW_TRAY_SHORTCUTS
}

RESERVED_SHORTCUTS = {
    "Ctrl+R": "refresh the weather",
    "Ctrl+L": "add a location",
    "Ctrl+D": "remove a location",
    "Ctrl+H": "open Weather History",
    "Ctrl+1": "focus Current Conditions",
    "Ctrl+2": "focus Hourly / Near-Term",
    "Ctrl+3": "focus Daily Forecast",
    "Ctrl+4": "focus Alerts",
    "Ctrl+5": "focus Event Center",
    "Ctrl+S": "open Settings",
    "Ctrl+Q": "exit AccessiWeather",
    "Ctrl+E": "open Explain Conditions",
    "Ctrl+T": "open Weather Assistant",
    "Ctrl+Shift+R": "open NOAA Weather Radio",
    "Escape": "hide the window when minimize-to-tray is enabled",
    "F5": "refresh the weather",
    "F6": "cycle through top-level sections",
}


def normalize_shortcut_text(value: str | None, *, allow_empty: bool = True) -> str:
    """Return a canonical shortcut string, or an empty string when disabled."""
    text = str(value or "").strip()
    if not text:
        if allow_empty:
            return ""
        raise ValueError("Shortcut cannot be blank.")

    parts = [part.strip() for part in text.split("+")]
    if not all(parts):
        raise ValueError("Use '+' only between modifiers and the key, for example Ctrl+Shift+W.")

    raw_key = parts[-1]
    modifier_parts = parts[:-1]
    modifiers: list[str] = []
    seen_modifiers: set[str] = set()
    for part in modifier_parts:
        normalized_modifier = _MODIFIER_ALIASES.get(part.upper())
        if normalized_modifier is None:
            raise ValueError(f"Unknown modifier {part!r}. Use Ctrl, Alt, or Shift.")
        if normalized_modifier in seen_modifiers:
            raise ValueError(f"{normalized_modifier} appears more than once.")
        seen_modifiers.add(normalized_modifier)
        modifiers.append(normalized_modifier)

    normalized_key = _normalize_key_token(raw_key)
    ordered_modifiers = [name for name in _VISIBLE_MODIFIER_ORDER if name in modifiers]
    return "+".join([*ordered_modifiers, normalized_key])


def parse_shortcut_text(value: str | None) -> ShortcutBinding | None:
    """Parse a canonical or user-entered shortcut string."""
    normalized = normalize_shortcut_text(value, allow_empty=True)
    if not normalized:
        return None
    parts = normalized.split("+")
    return ShortcutBinding(modifiers=tuple(parts[:-1]), key=parts[-1])


def resolve_shortcut_binding(value: str | None, *, default: str) -> ShortcutBinding | None:
    """Parse a user preference, falling back to the default when malformed."""
    try:
        return parse_shortcut_text(value)
    except ValueError:
        return parse_shortcut_text(default)


def _normalize_key_token(token: str) -> str:
    token = token.strip()
    if not token:
        raise ValueError("Shortcut needs a key after the modifiers.")

    special = _SPECIAL_KEYS.get(token.upper())
    if special is not None:
        return special

    if len(token) == 1 and token.isalnum():
        return token.upper()

    upper_token = token.upper()
    if upper_token.startswith("F") and upper_token[1:].isdigit():
        number = int(upper_token[1:])
        if 1 <= number <= 24:
            return f"F{number}"
        raise ValueError("Function-key shortcuts must be between F1 and F24.")

    raise ValueError("Shortcut keys must be letters, numbers, F1-F24, Tab, Space, or Escape.")
