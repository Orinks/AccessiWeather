//! In-window keyboard shortcuts: the accelerator table from
//! `AppShortcutsMixin._setup_accelerators` (`app_shortcuts.py`) and
//! `MainWindowUIMixin._setup_escape_accelerator`.
//!
//! wxDragon has no accelerator tables. Shortcuts that also appear in a menu
//! label (Ctrl+S, Ctrl+Q, Ctrl+L, F2, Ctrl+D, F5, Ctrl+E, Ctrl+H, Ctrl+N,
//! Ctrl+T) are handled by the menu bar's own accelerators, which route to the
//! same commands; the rest are matched here from EVT_CHAR_HOOK with the exact
//! modifier state a Win32 accelerator requires. Alt+F4 is the native close.
//! The configurable tray/window shortcuts belong to the global hotkey work.

use wxdragon::prelude::{WXK_ESCAPE, WXK_F6};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Shortcut {
    /// Ctrl+R.
    Refresh,
    /// Ctrl+1..Ctrl+5.
    FocusSection(usize),
    /// F6.
    CycleSections,
    /// Escape: minimize to tray when enabled.
    Escape,
}

pub(crate) fn match_shortcut(key: i32, ctrl: bool, alt: bool, shift: bool) -> Option<Shortcut> {
    match (ctrl, alt, shift) {
        (true, false, false) => match u8::try_from(key).ok()? {
            b'R' | b'r' => Some(Shortcut::Refresh),
            n @ b'1'..=b'5' => Some(Shortcut::FocusSection(usize::from(n - b'0'))),
            _ => None,
        },
        (false, false, false) => match key {
            WXK_F6 => Some(Shortcut::CycleSections),
            WXK_ESCAPE => Some(Shortcut::Escape),
            _ => None,
        },
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_exact_modifiers_match() {
        assert_eq!(
            match_shortcut('R' as i32, true, false, false),
            Some(Shortcut::Refresh)
        );
        assert_eq!(
            match_shortcut('3' as i32, true, false, false),
            Some(Shortcut::FocusSection(3))
        );
        assert_eq!(match_shortcut('6' as i32, true, false, false), None);
        assert_eq!(match_shortcut('R' as i32, true, false, true), None);
        assert_eq!(match_shortcut('1' as i32, true, true, false), None);
        assert_eq!(match_shortcut('R' as i32, false, false, false), None);
        assert_eq!(
            match_shortcut(WXK_F6, false, false, false),
            Some(Shortcut::CycleSections)
        );
        assert_eq!(match_shortcut(WXK_F6, false, false, true), None);
        assert_eq!(
            match_shortcut(WXK_ESCAPE, false, false, false),
            Some(Shortcut::Escape)
        );
    }
}
