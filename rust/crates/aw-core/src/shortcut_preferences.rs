//! Configurable window and tray shortcuts (`shortcut_preferences.py`) and the
//! canonical spelling of the NOAA Weather Radio hotkey
//! (`global_hotkeys.normalize_hotkey`).

use crate::settings::{
    DEFAULT_HIDE_MAIN_WINDOW_SHORTCUT, DEFAULT_READ_TRAY_INFO_SHORTCUT,
    DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT,
};

/// `ShortcutPreference`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ShortcutPreference {
    pub setting_name: &'static str,
    pub label: &'static str,
    pub default: &'static str,
}

/// `WINDOW_TRAY_SHORTCUTS`, in validation order.
pub const WINDOW_TRAY_SHORTCUTS: [ShortcutPreference; 3] = [
    ShortcutPreference {
        setting_name: "shortcut_show_main_window",
        label: "Show main window shortcut",
        default: DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT,
    },
    ShortcutPreference {
        setting_name: "shortcut_hide_main_window",
        label: "Hide window shortcut",
        default: DEFAULT_HIDE_MAIN_WINDOW_SHORTCUT,
    },
    ShortcutPreference {
        setting_name: "shortcut_read_tray_info",
        label: "Read tray information shortcut",
        default: DEFAULT_READ_TRAY_INFO_SHORTCUT,
    },
];

/// `RESERVED_SHORTCUTS`: in-app keys a window/tray shortcut may not take.
const RESERVED_SHORTCUTS: [(&str, &str); 19] = [
    ("Alt+F4", "close the window"),
    ("F2", "edit a location"),
    ("Ctrl+R", "refresh the weather"),
    ("Ctrl+L", "add a location"),
    ("Ctrl+D", "remove a location"),
    ("Ctrl+H", "open Weather History"),
    ("Ctrl+1", "focus Current Conditions"),
    ("Ctrl+2", "focus Hourly / Near-Term"),
    ("Ctrl+3", "focus Daily Forecast"),
    ("Ctrl+4", "focus Alerts"),
    ("Ctrl+5", "focus Event Center"),
    ("Ctrl+S", "open Settings"),
    ("Ctrl+Q", "exit AccessiWeather"),
    ("Ctrl+E", "open Explain Conditions"),
    ("Ctrl+T", "open Weather Assistant"),
    ("Ctrl+N", "open NOAA Weather Radio"),
    ("Escape", "hide the window when minimize-to-tray is enabled"),
    ("F5", "refresh the weather"),
    ("F6", "cycle through top-level sections"),
];

/// What a reserved shortcut already does, e.g. "open Settings".
pub fn reserved_shortcut_use(normalized: &str) -> Option<&'static str> {
    RESERVED_SHORTCUTS
        .iter()
        .find(|(combo, _)| *combo == normalized)
        .map(|(_, used_for)| *used_for)
}

/// Python's `repr()` of a string, as used in error messages.
pub fn py_repr(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(s.len() + 2);
    out.push(quote);
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if (c as u32) < 0x20 || c as u32 == 0x7f => {
                out.push_str(&format!("\\x{:02x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// `normalize_shortcut_text`: the canonical spelling ("Ctrl+Alt+Shift+W"),
/// "" for a blank field when `allow_empty`, or the user-facing problem.
pub fn normalize_shortcut_text(value: &str, allow_empty: bool) -> Result<String, String> {
    let text = value.trim();
    if text.is_empty() {
        return if allow_empty {
            Ok(String::new())
        } else {
            Err("Shortcut cannot be blank.".into())
        };
    }
    let parts: Vec<&str> = text.split('+').map(str::trim).collect();
    if parts.iter().any(|p| p.is_empty()) {
        return Err(
            "Use '+' only between modifiers and the key, for example Ctrl+Alt+Shift+W.".into(),
        );
    }
    let (raw_key, modifier_parts) = parts.split_last().expect("split yields one part");
    let mut modifiers: Vec<&str> = Vec::new();
    for part in modifier_parts {
        let normalized = match part.to_uppercase().as_str() {
            "ALT" | "OPTION" => "Alt",
            "CTRL" | "CONTROL" | "CMD" | "COMMAND" => "Ctrl",
            "SHIFT" => "Shift",
            _ => {
                return Err(format!(
                    "Unknown modifier {}. Use Ctrl, Alt, or Shift.",
                    py_repr(part)
                ))
            }
        };
        if modifiers.contains(&normalized) {
            return Err(format!("{normalized} appears more than once."));
        }
        modifiers.push(normalized);
    }
    let key = normalize_key_token(raw_key)?;
    let mut out: Vec<String> = ["Ctrl", "Alt", "Shift"]
        .into_iter()
        .filter(|m| modifiers.contains(m))
        .map(String::from)
        .collect();
    out.push(key);
    Ok(out.join("+"))
}

fn normalize_key_token(token: &str) -> Result<String, String> {
    let token = token.trim();
    if token.is_empty() {
        return Err("Shortcut needs a key after the modifiers.".into());
    }
    let upper = token.to_uppercase();
    match upper.as_str() {
        "ESC" | "ESCAPE" => return Ok("Escape".into()),
        "SPACE" => return Ok("Space".into()),
        "TAB" => return Ok("Tab".into()),
        _ => {}
    }
    let mut chars = token.chars();
    if let (Some(c), None) = (chars.next(), chars.next()) {
        if c.is_alphanumeric() {
            return Ok(upper);
        }
    }
    if let Some(digits) = function_key_digits(&upper) {
        return match digits.parse::<u32>() {
            Ok(n @ 1..=24) => Ok(format!("F{n}")),
            _ => Err("Function-key shortcuts must be between F1 and F24.".into()),
        };
    }
    Err("Shortcut keys must be letters, numbers, F1-F24, Tab, Space, or Escape.".into())
}

/// The digits after a leading "F" (`s[1:].isdigit()`).
fn function_key_digits(upper: &str) -> Option<&str> {
    let digits = upper.strip_prefix('F')?;
    (!digits.is_empty() && digits.chars().all(|c| c.is_ascii_digit())).then_some(digits)
}

/// wx.WXK_F1: global hotkey key codes above it are function keys.
const WXK_F1: u32 = 340;
const MAX_FUNCTION_KEY: u32 = 24;

/// `global_hotkeys.normalize_hotkey`: the canonical spelling of a system-wide
/// hotkey ("ctrl+alt+shift+r" -> "Ctrl+Alt+Shift+R"), or the
/// `HotkeyParseError` message. Unlike window shortcuts it needs a modifier
/// and also accepts Win.
pub fn normalize_hotkey(combo: &str) -> Result<String, String> {
    let parts: Vec<&str> = combo.split('+').map(str::trim).collect();
    if parts.len() < 2 || parts.iter().any(|p| p.is_empty()) {
        return Err(format!(
            "Hotkey must be modifiers plus a key, got {}",
            py_repr(combo)
        ));
    }
    let (key, modifier_parts) = parts.split_last().expect("at least two parts");
    // Ctrl, Alt, Shift, Win: canonical order no matter how they were typed.
    let mut flags = [false; 4];
    for part in modifier_parts {
        let index = match part.to_lowercase().as_str() {
            "ctrl" | "control" => 0,
            "alt" => 1,
            "shift" => 2,
            "win" | "super" | "cmd" | "command" => 3,
            _ => {
                return Err(format!(
                    "Unknown modifier {} in hotkey {}",
                    py_repr(part),
                    py_repr(combo)
                ))
            }
        };
        flags[index] = true;
    }
    let keycode = parse_hotkey_key(key).ok_or_else(|| {
        format!(
            "Unsupported key {} in hotkey {}",
            py_repr(key),
            py_repr(combo)
        )
    })?;
    let mut out: Vec<String> = ["Ctrl", "Alt", "Shift", "Win"]
        .into_iter()
        .zip(flags)
        .filter(|(_, on)| *on)
        .map(|(label, _)| label.to_string())
        .collect();
    // `_format_key`: codes in the function-key range print as F-keys.
    out.push(if (WXK_F1..WXK_F1 + MAX_FUNCTION_KEY).contains(&keycode) {
        format!("F{}", keycode - WXK_F1 + 1)
    } else {
        char::from_u32(keycode).unwrap_or_default().to_string()
    });
    Ok(out.join("+"))
}

fn parse_hotkey_key(key: &str) -> Option<u32> {
    let upper = key.to_uppercase();
    let mut chars = upper.chars();
    if let (Some(c), None) = (chars.next(), chars.next()) {
        if c.is_alphabetic() || c.is_ascii_digit() {
            return Some(c as u32);
        }
    }
    let n: u32 = function_key_digits(&upper)?.parse().ok()?;
    (1..=MAX_FUNCTION_KEY)
        .contains(&n)
        .then_some(WXK_F1 + n - 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repr_matches_python_quoting() {
        assert_eq!(py_repr("Hyper"), "'Hyper'");
        assert_eq!(py_repr("it's"), "\"it's\"");
        assert_eq!(py_repr("a'b\"c"), "'a\\'b\"c'");
        assert_eq!(py_repr("tab\there\\"), "'tab\\there\\\\'");
    }
}
