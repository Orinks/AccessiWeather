//! Hotkey combos and configurable shortcuts.
//!
//! * The NOAA Weather Radio hotkey's combo parsing from `global_hotkeys.py`
//!   ([`parse_hotkey`], [`normalize_hotkey`]; accepts a Win modifier).
//! * The window/tray shortcuts of `shortcut_preferences.py`
//!   ([`normalize_shortcut_text`], [`resolve_shortcut_binding`], the reserved
//!   list and the legacy-default migration), plus the settings dialog's
//!   `_validate_window_tray_shortcuts` and the load-time clean-up
//!   `AppSettings.from_dict` applies to these four settings.
//!
//! Key codes are wx key codes (letters and digits are their ASCII code,
//! `F1` is 340), as Python hands them to wx.

use crate::py::repr_str;
use crate::settings::{
    AppSettings, DEFAULT_HIDE_MAIN_WINDOW_SHORTCUT, DEFAULT_NOAA_RADIO_HOTKEY,
    DEFAULT_READ_TRAY_INFO_SHORTCUT, DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT,
};

/// wx modifier flags (the same values as Win32's `MOD_*`).
pub const MOD_ALT: u32 = 0x1;
pub const MOD_CONTROL: u32 = 0x2;
pub const MOD_SHIFT: u32 = 0x4;
pub const MOD_WIN: u32 = 0x8;

/// `wx.WXK_F1`; F2..F24 follow it.
pub const WXK_F1: u32 = 340;
pub const WXK_ESCAPE: u32 = 27;
pub const WXK_SPACE: u32 = 32;
pub const WXK_TAB: u32 = 9;
const MAX_FUNCTION_KEY: u32 = 24;

// ---------------------------------------------------------------------------
// global_hotkeys.py
// ---------------------------------------------------------------------------

/// Canonical order and accepted spellings.
const HOTKEY_MODIFIERS: [(&str, u32, &[&str]); 4] = [
    ("Ctrl", MOD_CONTROL, &["ctrl", "control"]),
    ("Alt", MOD_ALT, &["alt"]),
    ("Shift", MOD_SHIFT, &["shift"]),
    ("Win", MOD_WIN, &["win", "super", "cmd", "command"]),
];

/// `parse_hotkey`: `(modifier flags, wx keycode)` for a combo such as
/// `Ctrl+Alt+Shift+R`. At least one modifier is required. The error is
/// Python's `HotkeyParseError` message.
pub fn parse_hotkey(combo: &str) -> Result<(u32, u32), String> {
    let parts: Vec<&str> = combo.split('+').map(str::trim).collect();
    if parts.len() < 2 || parts.iter().any(|p| p.is_empty()) {
        return Err(format!(
            "Hotkey must be modifiers plus a key, got {}",
            repr_str(combo)
        ));
    }
    let (key, modifiers) = parts.split_last().expect("at least two parts");
    let mut flags = 0;
    for part in modifiers {
        let lower = part.to_lowercase();
        let Some((_, flag, _)) = HOTKEY_MODIFIERS
            .iter()
            .find(|(_, _, aliases)| aliases.contains(&lower.as_str()))
        else {
            return Err(format!(
                "Unknown modifier {} in hotkey {}",
                repr_str(part),
                repr_str(combo)
            ));
        };
        flags |= flag;
    }
    let keycode = parse_key(key).ok_or_else(|| {
        format!(
            "Unsupported key {} in hotkey {}",
            repr_str(key),
            repr_str(combo)
        )
    })?;
    Ok((flags, keycode))
}

fn parse_key(key: &str) -> Option<u32> {
    let upper = key.to_uppercase();
    let mut chars = upper.chars();
    if let (Some(c), None) = (chars.next(), chars.next()) {
        if c.is_alphabetic() || c.is_ascii_digit() {
            return Some(c as u32);
        }
    }
    function_key_number(&upper)
        .filter(|n| (1..=MAX_FUNCTION_KEY).contains(n))
        .map(|n| WXK_F1 + n - 1)
}

/// `F<digits>` → the number (Python's `startswith("F") and [1:].isdigit()`).
fn function_key_number(upper: &str) -> Option<u32> {
    let digits = upper.strip_prefix('F')?;
    if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    // A huge number is simply out of range.
    Some(digits.parse().unwrap_or(u32::MAX))
}

/// `normalize_hotkey`: the canonical spelling, e.g. `Ctrl+Alt+Shift+R`.
pub fn normalize_hotkey(combo: &str) -> Result<String, String> {
    let (flags, keycode) = parse_hotkey(combo)?;
    let mut parts: Vec<String> = HOTKEY_MODIFIERS
        .iter()
        .filter(|(_, flag, _)| flags & flag != 0)
        .map(|(label, _, _)| label.to_string())
        .collect();
    parts.push(format_key(keycode));
    Ok(parts.join("+"))
}

fn format_key(keycode: u32) -> String {
    if (WXK_F1..WXK_F1 + MAX_FUNCTION_KEY).contains(&keycode) {
        return format!("F{}", keycode - WXK_F1 + 1);
    }
    char::from_u32(keycode)
        .map(String::from)
        .unwrap_or_default()
}

/// `AppSettings._normalized_hotkey`: canonical combo, `""` for disabled,
/// the default for anything unparseable.
pub fn normalized_hotkey_setting(value: &str) -> String {
    if value.trim().is_empty() {
        return String::new();
    }
    normalize_hotkey(value).unwrap_or_else(|_| DEFAULT_NOAA_RADIO_HOTKEY.to_string())
}

// ---------------------------------------------------------------------------
// shortcut_preferences.py
// ---------------------------------------------------------------------------

/// Window/tray shortcut defaults shipped before 0.11.0.
pub const LEGACY_WINDOW_TRAY_SHORTCUT_DEFAULTS: [(&str, &str); 3] = [
    ("shortcut_show_main_window", "Ctrl+Shift+W"),
    ("shortcut_hide_main_window", "Ctrl+Shift+M"),
    ("shortcut_read_tray_info", "Ctrl+Shift+I"),
];

/// What each configurable shortcut does.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WindowTrayAction {
    ShowMainWindow,
    HideMainWindow,
    ReadTrayInfo,
}

/// `ShortcutPreference`.
#[derive(Debug, Clone, Copy)]
pub struct ShortcutPreference {
    pub setting_name: &'static str,
    pub label: &'static str,
    pub default: &'static str,
    pub action: WindowTrayAction,
}

impl ShortcutPreference {
    /// The setting's current value.
    pub fn value<'a>(&self, settings: &'a AppSettings) -> &'a str {
        match self.action {
            WindowTrayAction::ShowMainWindow => &settings.shortcut_show_main_window,
            WindowTrayAction::HideMainWindow => &settings.shortcut_hide_main_window,
            WindowTrayAction::ReadTrayInfo => &settings.shortcut_read_tray_info,
        }
    }

    fn value_mut<'a>(&self, settings: &'a mut AppSettings) -> &'a mut String {
        match self.action {
            WindowTrayAction::ShowMainWindow => &mut settings.shortcut_show_main_window,
            WindowTrayAction::HideMainWindow => &mut settings.shortcut_hide_main_window,
            WindowTrayAction::ReadTrayInfo => &mut settings.shortcut_read_tray_info,
        }
    }
}

/// `WINDOW_TRAY_SHORTCUTS`.
pub const WINDOW_TRAY_SHORTCUTS: [ShortcutPreference; 3] = [
    ShortcutPreference {
        setting_name: "shortcut_show_main_window",
        label: "Show main window shortcut",
        default: DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT,
        action: WindowTrayAction::ShowMainWindow,
    },
    ShortcutPreference {
        setting_name: "shortcut_hide_main_window",
        label: "Hide window shortcut",
        default: DEFAULT_HIDE_MAIN_WINDOW_SHORTCUT,
        action: WindowTrayAction::HideMainWindow,
    },
    ShortcutPreference {
        setting_name: "shortcut_read_tray_info",
        label: "Read tray information shortcut",
        default: DEFAULT_READ_TRAY_INFO_SHORTCUT,
        action: WindowTrayAction::ReadTrayInfo,
    },
];

/// `RESERVED_SHORTCUTS`: shortcut → what it already does.
pub const RESERVED_SHORTCUTS: [(&str, &str); 19] = [
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

pub fn reserved_use(normalized: &str) -> Option<&'static str> {
    RESERVED_SHORTCUTS
        .iter()
        .find(|(combo, _)| *combo == normalized)
        .map(|(_, use_)| *use_)
}

/// `ShortcutBinding`: modifiers in Ctrl, Alt, Shift order plus the key.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ShortcutBinding {
    pub modifiers: Vec<&'static str>,
    pub key: String,
}

impl ShortcutBinding {
    pub fn normalized(&self) -> String {
        let mut parts: Vec<&str> = self.modifiers.clone();
        parts.push(&self.key);
        parts.join("+")
    }

    pub fn has(&self, modifier: &str) -> bool {
        self.modifiers.contains(&modifier)
    }

    /// Only combos with Ctrl or Alt become system-wide hotkeys.
    pub fn has_ctrl_or_alt(&self) -> bool {
        self.has("Ctrl") || self.has("Alt")
    }

    /// `hotkey_modifiers`: `MOD_*` flags.
    pub fn hotkey_modifiers(&self) -> u32 {
        [
            ("Ctrl", MOD_CONTROL),
            ("Alt", MOD_ALT),
            ("Shift", MOD_SHIFT),
        ]
        .iter()
        .filter(|(m, _)| self.has(m))
        .fold(0, |flags, (_, f)| flags | f)
    }

    /// `key_code`: the wx key code. `None` where Python raises (a key such
    /// as `SS`, which `Ctrl+ß` normalizes to); such a binding is skipped.
    pub fn key_code(&self) -> Option<u32> {
        let mut chars = self.key.chars();
        if let (Some(c), None) = (chars.next(), chars.next()) {
            return Some(c as u32);
        }
        match self.key.as_str() {
            "Escape" => Some(WXK_ESCAPE),
            "Space" => Some(WXK_SPACE),
            "Tab" => Some(WXK_TAB),
            // Normalized function keys are always F1..F24.
            key => function_key_number(key).map(|n| WXK_F1 + n - 1),
        }
    }
}

fn modifier_alias(part: &str) -> Option<&'static str> {
    match part.to_uppercase().as_str() {
        "ALT" | "OPTION" => Some("Alt"),
        "CTRL" | "CONTROL" | "CMD" | "COMMAND" => Some("Ctrl"),
        "SHIFT" => Some("Shift"),
        _ => None,
    }
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
    if let Some(n) = function_key_number(&upper) {
        if (1..=MAX_FUNCTION_KEY).contains(&n) {
            return Ok(format!("F{n}"));
        }
        return Err("Function-key shortcuts must be between F1 and F24.".into());
    }
    Err("Shortcut keys must be letters, numbers, F1-F24, Tab, Space, or Escape.".into())
}

/// `normalize_shortcut_text`: the canonical shortcut, `""` when disabled.
/// The error is the message the settings dialog shows.
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
    let (raw_key, modifier_parts) = parts.split_last().expect("split yields a part");
    let mut modifiers: Vec<&'static str> = Vec::new();
    for part in modifier_parts {
        let Some(modifier) = modifier_alias(part) else {
            return Err(format!(
                "Unknown modifier {}. Use Ctrl, Alt, or Shift.",
                repr_str(part)
            ));
        };
        if modifiers.contains(&modifier) {
            return Err(format!("{modifier} appears more than once."));
        }
        modifiers.push(modifier);
    }
    let key = normalize_key_token(raw_key)?;
    let mut out: Vec<&str> = ["Ctrl", "Alt", "Shift"]
        .into_iter()
        .filter(|m| modifiers.contains(m))
        .collect();
    out.push(&key);
    Ok(out.join("+"))
}

/// `parse_shortcut_text`: `None` when the shortcut is disabled (blank).
pub fn parse_shortcut_text(value: &str) -> Result<Option<ShortcutBinding>, String> {
    let normalized = normalize_shortcut_text(value, true)?;
    if normalized.is_empty() {
        return Ok(None);
    }
    let mut parts: Vec<&str> = normalized.split('+').collect();
    let key = parts.pop().unwrap_or_default().to_string();
    let modifiers = parts
        .into_iter()
        .filter_map(|m| ["Ctrl", "Alt", "Shift"].into_iter().find(|x| *x == m))
        .collect();
    Ok(Some(ShortcutBinding { modifiers, key }))
}

/// `resolve_shortcut_binding`: a malformed preference falls back to `default`.
pub fn resolve_shortcut_binding(value: &str, default: &str) -> Option<ShortcutBinding> {
    parse_shortcut_text(value).unwrap_or_else(|_| parse_shortcut_text(default).ok().flatten())
}

/// The window/tray shortcuts that are active: resolved, and not the same
/// combo as the NOAA Weather Radio hotkey (which wins).
pub fn active_window_tray_bindings(
    settings: &AppSettings,
) -> Vec<(&'static ShortcutPreference, ShortcutBinding)> {
    let radio = resolve_shortcut_binding(&settings.noaa_radio_hotkey, DEFAULT_NOAA_RADIO_HOTKEY);
    WINDOW_TRAY_SHORTCUTS
        .iter()
        .filter_map(|pref| {
            let binding = resolve_shortcut_binding(pref.value(settings), pref.default)?;
            (radio.as_ref() != Some(&binding)).then_some((pref, binding))
        })
        .collect()
}

/// `migrate_legacy_window_tray_shortcuts`: shortcuts still on a pre-0.11
/// default move to the current default, or are blanked when that combo is
/// already taken. Returns the settings that changed.
pub fn migrate_legacy_window_tray_shortcuts(settings: &mut AppSettings) -> Vec<&'static str> {
    let mut taken: Vec<String> = Vec::new();
    if !settings.noaa_radio_hotkey.is_empty() {
        taken.push(settings.noaa_radio_hotkey.clone());
    }
    for (pref, (_, legacy)) in WINDOW_TRAY_SHORTCUTS
        .iter()
        .zip(LEGACY_WINDOW_TRAY_SHORTCUT_DEFAULTS)
    {
        let value = pref.value(settings);
        if !value.is_empty() && value != legacy {
            taken.push(value.to_string());
        }
    }
    let mut changed = Vec::new();
    for (pref, (_, legacy)) in WINDOW_TRAY_SHORTCUTS
        .iter()
        .zip(LEGACY_WINDOW_TRAY_SHORTCUT_DEFAULTS)
    {
        if pref.value(settings) != legacy {
            continue;
        }
        let replacement = if taken.iter().any(|t| t == pref.default) {
            String::new()
        } else {
            taken.push(pref.default.to_string());
            pref.default.to_string()
        };
        *pref.value_mut(settings) = replacement;
        changed.push(pref.setting_name);
    }
    changed
}

/// The clean-up `AppSettings.from_dict` gives these settings on load:
/// canonical spellings (unusable values fall back to their defaults), then
/// the legacy-default migration.
pub fn normalize_shortcut_settings(settings: &mut AppSettings) {
    settings.noaa_radio_hotkey = normalized_hotkey_setting(&settings.noaa_radio_hotkey);
    for pref in &WINDOW_TRAY_SHORTCUTS {
        let value = pref.value_mut(settings);
        *value = normalize_shortcut_text(value, true).unwrap_or_else(|_| pref.default.into());
    }
    migrate_legacy_window_tray_shortcuts(settings);
}

/// Outcome of the settings dialog's `_validate_window_tray_shortcuts`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ShortcutValidation {
    /// The canonical text the dialog writes back into each field
    /// (`WINDOW_TRAY_SHORTCUTS` order); `None` for fields it did not reach.
    pub normalized: [Option<String>; 3],
    /// `(setting_name, message)` for the first field that fails.
    pub error: Option<(&'static str, String)>,
}

/// `_validate_window_tray_shortcuts`: `values` are the three field texts in
/// `WINDOW_TRAY_SHORTCUTS` order, `radio_hotkey` the radio hotkey field.
pub fn validate_window_tray_shortcuts(radio_hotkey: &str, values: [&str; 3]) -> ShortcutValidation {
    let mut seen: Vec<(String, &str)> = Vec::new();
    if let Ok(radio) = normalize_hotkey(radio_hotkey) {
        seen.push((radio, "NOAA Weather Radio hotkey"));
    }
    let mut normalized: [Option<String>; 3] = Default::default();
    for (i, pref) in WINDOW_TRAY_SHORTCUTS.iter().enumerate() {
        let fail = |message: String| Some((pref.setting_name, message));
        let value = match normalize_shortcut_text(values[i], true) {
            Ok(v) => v,
            Err(e) => {
                let error = fail(format!("{}: {e}", pref.label));
                return ShortcutValidation { normalized, error };
            }
        };
        normalized[i] = Some(value.clone());
        if value.is_empty() {
            continue;
        }
        let modifiers = &value.split('+').collect::<Vec<_>>()[..];
        let modifiers = &modifiers[..modifiers.len() - 1];
        let error = if !modifiers.iter().any(|m| *m == "Ctrl" || *m == "Alt") {
            fail(format!(
                "{} must include Ctrl or Alt to avoid capturing typing keys.",
                pref.label
            ))
        } else if let Some(use_) = reserved_use(&value) {
            fail(format!(
                "{} cannot use {value} because that shortcut already {use_}.",
                pref.label
            ))
        } else if let Some((_, existing)) = seen.iter().find(|(s, _)| *s == value) {
            fail(format!(
                "{} duplicates {existing} ({value}). Choose a different shortcut or leave one field blank.",
                pref.label
            ))
        } else {
            None
        };
        if error.is_some() {
            return ShortcutValidation { normalized, error };
        }
        seen.push((value, pref.label));
    }
    ShortcutValidation {
        normalized,
        error: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    fn golden(name: &str) -> Value {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../testdata/golden/lifecycle")
            .join(name);
        let text =
            std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        serde_json::from_str(&text).unwrap()
    }

    fn ok_or_err(result: Result<String, String>) -> Value {
        match result {
            Ok(v) => serde_json::json!({ "ok": v }),
            Err(e) => serde_json::json!({ "error": e }),
        }
    }

    #[test]
    fn hotkeys_match_python() {
        for case in golden("hotkeys.json").as_array().unwrap() {
            let combo = case["combo"].as_str().unwrap();
            let parsed = match parse_hotkey(combo) {
                Ok((flags, key)) => serde_json::json!({ "ok": [flags, key] }),
                Err(e) => serde_json::json!({ "error": e }),
            };
            assert_eq!(parsed, case["parse"], "parse {combo:?}");
            assert_eq!(
                ok_or_err(normalize_hotkey(combo)),
                case["normalize"],
                "normalize {combo:?}"
            );
            assert_eq!(
                normalized_hotkey_setting(combo),
                case["setting"],
                "setting {combo:?}"
            );
        }
    }

    #[test]
    fn shortcuts_match_python() {
        for case in golden("shortcuts.json").as_array().unwrap() {
            let text = case["text"].as_str().unwrap();
            assert_eq!(
                ok_or_err(normalize_shortcut_text(text, true)),
                case["normalize"],
                "normalize {text:?}"
            );
            assert_eq!(
                ok_or_err(normalize_shortcut_text(text, false)),
                case["normalize_strict"],
                "strict {text:?}"
            );
            let resolved =
                resolve_shortcut_binding(text, DEFAULT_SHOW_MAIN_WINDOW_SHORTCUT).map(|b| {
                    serde_json::json!({
                        "normalized": b.normalized(),
                        "modifiers": b.hotkey_modifiers(),
                        "key_code": b.key_code(),
                    })
                });
            assert_eq!(
                resolved.unwrap_or(Value::Null),
                case["resolved"],
                "resolve {text:?}"
            );
        }
    }

    #[test]
    fn validation_matches_python() {
        for case in golden("validation.json").as_array().unwrap() {
            let radio = case["radio"].as_str().unwrap();
            let values: Vec<&str> = case["values"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_str().unwrap())
                .collect();
            let result = validate_window_tray_shortcuts(radio, [values[0], values[1], values[2]]);
            let error = result
                .error
                .map(|(name, message)| serde_json::json!([name, message]))
                .unwrap_or(Value::Null);
            assert_eq!(error, case["error"], "{case}");
            assert_eq!(
                serde_json::to_value(&result.normalized).unwrap(),
                case["normalized"],
                "{case}"
            );
        }
    }

    #[test]
    fn load_normalization_matches_python() {
        for case in golden("settings_load.json").as_array().unwrap() {
            let mut settings = AppSettings::default();
            let input = &case["input"];
            settings.noaa_radio_hotkey = input["noaa_radio_hotkey"].as_str().unwrap().into();
            settings.shortcut_show_main_window =
                input["shortcut_show_main_window"].as_str().unwrap().into();
            settings.shortcut_hide_main_window =
                input["shortcut_hide_main_window"].as_str().unwrap().into();
            settings.shortcut_read_tray_info =
                input["shortcut_read_tray_info"].as_str().unwrap().into();
            normalize_shortcut_settings(&mut settings);
            let out = &case["output"];
            assert_eq!(
                settings.noaa_radio_hotkey, out["noaa_radio_hotkey"],
                "{case}"
            );
            assert_eq!(
                settings.shortcut_show_main_window, out["shortcut_show_main_window"],
                "{case}"
            );
            assert_eq!(
                settings.shortcut_hide_main_window, out["shortcut_hide_main_window"],
                "{case}"
            );
            assert_eq!(
                settings.shortcut_read_tray_info, out["shortcut_read_tray_info"],
                "{case}"
            );
        }
    }

    #[test]
    fn radio_combo_wins_over_a_window_shortcut() {
        let mut settings = AppSettings {
            shortcut_hide_main_window: "Ctrl+Alt+Shift+R".into(),
            ..Default::default()
        };
        let actions: Vec<_> = active_window_tray_bindings(&settings)
            .into_iter()
            .map(|(p, _)| p.action)
            .collect();
        assert_eq!(
            actions,
            [
                WindowTrayAction::ShowMainWindow,
                WindowTrayAction::ReadTrayInfo
            ]
        );
        // A radio hotkey the shortcut parser rejects (Win) resolves to the
        // radio default, as in Python.
        settings.noaa_radio_hotkey = "Win+Alt+R".into();
        assert_eq!(active_window_tray_bindings(&settings).len(), 2);
    }
}
