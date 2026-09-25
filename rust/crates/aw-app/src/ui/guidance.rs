//! First-run guidance after the main window appears (`app_startup_guidance.py`):
//! the portable key bundle import, the first-start onboarding wizard (driven
//! by `aw_services::onboarding`), the portable missing-keys hint, and the
//! startup update check that waits for the wizard.

use std::cell::Cell;
use std::path::Path;
use std::sync::OnceLock;
use std::time::Duration;

use aw_services::import_export::{self, SystemKeyring};
use aw_services::onboarding::{
    self, Buttons, Dialog as GuidanceDialog, Facts, Icon, Onboarding, Response, Step,
};
use aw_store::secrets::{self, BUNDLE_FILE_NAMES, PORTABLE_PASSPHRASE_KEY};
use wxdragon::prelude::*;

use super::main_window::{self as mw, main_frame};
use super::{locations, refresh, updates};
use crate::app::{post_to_ui, save, save_api_key, with_state, Shared};
use crate::portable_keys;

/// The prompts `_schedule_startup_guidance_prompts` queues after startup.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum GuidanceStage {
    /// `_maybe_auto_import_keys_file` (portable key bundle).
    AutoImportKeys,
    /// `_maybe_show_first_start_onboarding`.
    Onboarding,
    /// `_maybe_show_portable_missing_keys_hint`.
    PortableHint,
}

impl GuidanceStage {
    pub(crate) const ALL: [GuidanceStage; 3] = [
        GuidanceStage::AutoImportKeys,
        GuidanceStage::Onboarding,
        GuidanceStage::PortableHint,
    ];

    /// Milliseconds after the main window is shown.
    pub(crate) fn delay_ms(self) -> u64 {
        match self {
            GuidanceStage::AutoImportKeys => onboarding::AUTO_IMPORT_KEYS_DELAY_MS,
            GuidanceStage::Onboarding => onboarding::ONBOARDING_DELAY_MS,
            GuidanceStage::PortableHint => onboarding::PORTABLE_HINT_DELAY_MS,
        }
    }
}

thread_local! {
    /// `_startup_update_check_deferred`.
    static UPDATE_CHECK_DEFERRED: Cell<bool> = const { Cell::new(false) };
}

/// `_schedule_startup_guidance_prompts`: run every stage at its delay.
/// `force_wizard` is `--wizard`.
#[allow(dead_code)] // Called by the startup sequence.
pub(crate) fn schedule_startup_guidance_prompts(force_wizard: bool) {
    std::thread::Builder::new()
        .name("aw-guidance".into())
        .spawn(move || {
            let mut elapsed = 0;
            for stage in GuidanceStage::ALL {
                std::thread::sleep(Duration::from_millis(stage.delay_ms() - elapsed));
                elapsed = stage.delay_ms();
                post_to_ui(move || run_startup_guidance(stage, force_wizard));
            }
        })
        .expect("spawn guidance thread");
}

/// Run one startup guidance prompt now. Smoke runs never show them.
pub(crate) fn run_startup_guidance(stage: GuidanceStage, force_wizard: bool) {
    let (Some(state), Some(frame)) = (with_state(), main_frame()) else {
        return;
    };
    if state.borrow().smoke {
        return;
    }
    match stage {
        GuidanceStage::AutoImportKeys => maybe_auto_import_keys_file(&frame, &state),
        GuidanceStage::Onboarding => {
            maybe_show_first_start_onboarding(&frame, &state, force_wizard)
        }
        GuidanceStage::PortableHint => {
            maybe_show_portable_missing_keys_hint(&frame, &state, force_wizard)
        }
    }
}

/// `_check_for_updates_after_startup_guidance`: the startup update check,
/// now or once the onboarding wizard closes.
#[allow(dead_code)] // Called by the startup sequence.
pub(crate) fn check_for_updates_after_startup_guidance(force_wizard: bool) {
    let deferred =
        with_state().is_some_and(|s| should_show_first_start_onboarding(&s, force_wizard));
    UPDATE_CHECK_DEFERRED.with(|d| d.set(deferred));
    if !deferred {
        updates::check_for_updates(false);
    }
}

/// `_run_deferred_startup_update_check`.
fn run_deferred_startup_update_check() {
    if UPDATE_CHECK_DEFERRED.with(|d| d.replace(false)) {
        updates::check_for_updates(false);
    }
}

/// `_should_show_first_start_onboarding`.
fn should_show_first_start_onboarding(state: &Shared, force_wizard: bool) -> bool {
    if main_frame().is_none() {
        return false;
    }
    let st = state.borrow();
    if force_wizard {
        tracing::debug!("Wizard forced via --wizard flag");
    }
    onboarding::should_show_onboarding(
        force_wizard,
        st.config.settings.onboarding_wizard_shown,
        !st.config.locations.is_empty(),
    )
}

/// `refresh_runtime_settings`: imported keys and settings reach the weather
/// client, the notifier and the alert settings.
fn refresh_runtime_settings() {
    super::settings_actions::refresh_runtime_settings();
}

/// `_maybe_auto_import_keys_file`: a portable copy imports its key bundle
/// with the cached passphrase, or asks for it.
fn maybe_auto_import_keys_file(frame: &Frame, state: &Shared) {
    let paths = state.borrow().paths.clone();
    if !paths.portable || portable_keys::keys_imported_this_session() {
        return;
    }
    if secrets::find_bundle(&paths.config_dir).is_none() {
        return;
    }
    let needs_passphrase =
        portable_keys::import_silently(&paths, &mut state.borrow_mut().config.settings);
    if !needs_passphrase || portable_keys::prompt(frame, state) {
        refresh_runtime_settings();
        refresh::refresh_weather_async(true);
    }
}

/// `_maybe_show_portable_missing_keys_hint`.
fn maybe_show_portable_missing_keys_hint(frame: &Frame, state: &Shared, force_wizard: bool) {
    let (portable, hint_shown, config_dir) = {
        let st = state.borrow();
        (
            st.paths.portable,
            st.config.settings.portable_missing_api_keys_hint_shown,
            st.paths.config_dir.clone(),
        )
    };
    let show = onboarding::should_show_portable_missing_keys_hint(
        portable,
        hint_shown,
        should_show_first_start_onboarding(state, force_wizard),
        secrets::find_bundle(&config_dir).is_some(),
        portable_keys::keys_imported_this_session(),
    );
    if !show {
        return;
    }
    let response = show_dialog(frame, &onboarding::portable_missing_keys_hint());
    {
        let mut st = state.borrow_mut();
        st.config.settings.portable_missing_api_keys_hint_shown = true;
        let _ = save(&st);
    }
    if response == Response::Yes {
        locations::on_settings();
    }
}

/// `_maybe_show_first_start_onboarding`.
fn maybe_show_first_start_onboarding(frame: &Frame, state: &Shared, force_wizard: bool) {
    if !should_show_first_start_onboarding(state, force_wizard) {
        run_deferred_startup_update_check();
        return;
    }
    let mut wizard = Onboarding::new(state.borrow().paths.portable);
    let mut step = wizard.start(&facts(state));
    while step != Step::Finished {
        let response = perform(frame, state, step);
        step = wizard.advance(response, &facts(state));
    }
    {
        let mut st = state.borrow_mut();
        st.config.settings.onboarding_wizard_shown = true;
        let _ = save(&st);
    }
    run_deferred_startup_update_check();
}

/// `is_keyring_available`: a set/get/delete round trip, probed once.
fn keyring_available() -> bool {
    static AVAILABLE: OnceLock<bool> = OnceLock::new();
    *AVAILABLE.get_or_init(|| {
        const PROBE_KEY: &str = "__accessiweather_keyring_probe__";
        const PROBE_VALUE: &str = "probe";
        let ok = secrets::set_password(PROBE_KEY, PROBE_VALUE)
            && secrets::get_password(PROBE_KEY).as_deref() == Some(PROBE_VALUE);
        secrets::delete_password(PROBE_KEY);
        ok
    })
}

/// `_has_saved_api_key`: the in-memory settings when portable, else the keyring.
fn has_saved_api_key(state: &Shared, name: &str) -> bool {
    let mut st = state.borrow_mut();
    if st.paths.portable {
        return secrets::api_key_mut(&mut st.config.settings, name)
            .is_some_and(|v| !v.trim().is_empty());
    }
    secrets::get_password(name).is_some_and(|v| !v.trim().is_empty())
}

fn facts(state: &Shared) -> Facts {
    let (portable, has_locations) = {
        let st = state.borrow();
        (st.paths.portable, !st.config.locations.is_empty())
    };
    Facts {
        has_locations,
        // Only installed copies ask, as in Python.
        keyring_available: portable || keyring_available(),
        has_openrouter_key: has_saved_api_key(state, "openrouter_api_key"),
        has_pirate_weather_key: has_saved_api_key(state, "pirate_weather_api_key"),
        portable_keys_imported_this_session: portable_keys::keys_imported_this_session(),
    }
}

/// Do what one wizard step asks and report the outcome.
fn perform(frame: &Frame, state: &Shared, step: Step) -> Response {
    match step {
        Step::Dialog(dialog) => show_dialog(frame, &dialog),
        Step::Secret { title, message } => {
            prompt_secret(frame, &title, &message).map_or(Response::Cancel, Response::Text)
        }
        Step::ChooseFile { title, wildcard } => Response::File(choose_file(frame, title, wildcard)),
        Step::AddLocation => {
            locations::on_add_location();
            Response::Done
        }
        Step::ImportSettings(path) => Response::Success(import_settings(state, &path)),
        Step::ImportApiKeys { path, passphrase } => {
            Response::Success(import_api_keys(state, &path, &passphrase))
        }
        Step::OpenUrl(url) => {
            if !aw_services::open_in_shell(url) {
                tracing::warn!("Failed opening API key page {url}");
            }
            Response::Done
        }
        Step::SaveApiKey { name, value } => {
            save_api_key(&mut state.borrow_mut(), name, &value);
            Response::Done
        }
        Step::OpenSettings { tab } => {
            locations::open_settings(tab);
            Response::Done
        }
        Step::WriteKeyBundle { keys, passphrase } => {
            Response::Success(write_key_bundle(state, keys, &passphrase))
        }
        Step::Finished => Response::Done,
    }
}

fn message_style(buttons: Buttons, icon: Icon) -> MessageDialogStyle {
    let buttons = match buttons {
        Buttons::Ok => MessageDialogStyle::OK,
        Buttons::YesNo(..) => MessageDialogStyle::YesNo,
        Buttons::YesNoCancel(..) => MessageDialogStyle::YesNo | MessageDialogStyle::Cancel,
    };
    buttons
        | match icon {
            Icon::Information => MessageDialogStyle::IconInformation,
            Icon::Warning => MessageDialogStyle::IconWarning,
            Icon::Error => MessageDialogStyle::IconError,
        }
}

/// A `wx.MessageDialog` with the step's custom button labels.
fn show_dialog(frame: &Frame, dialog: &GuidanceDialog) -> Response {
    let dlg = MessageDialog::builder(frame, &dialog.message, &dialog.title)
        .with_style(message_style(dialog.buttons, dialog.icon))
        .build();
    match dialog.buttons {
        Buttons::Ok => {}
        Buttons::YesNo(yes, no) => dlg.set_yes_no_labels(yes, no),
        Buttons::YesNoCancel(yes, no, cancel) => {
            // `SetYesNoCancelLabels`: wxDragon lacks it, but it is exactly
            // these two calls (the OK label is unused without an OK button).
            dlg.set_yes_no_labels(yes, no);
            dlg.set_ok_cancel_labels("", cancel);
        }
    }
    match dlg.show_modal() {
        ID_YES => Response::Yes,
        ID_NO => Response::No,
        ID_OK => Response::Ok,
        _ => Response::Cancel,
    }
}

fn secret_style() -> TextEntryDialogStyle {
    TextEntryDialogStyle::Ok | TextEntryDialogStyle::Cancel | TextEntryDialogStyle::Password
}

/// `_prompt_optional_secret`: `None` when cancelled.
fn prompt_secret(frame: &Frame, title: &str, message: &str) -> Option<String> {
    let dlg = TextEntryDialog::builder(frame, message, title)
        .with_style(secret_style())
        .build();
    (dlg.show_modal() == ID_OK).then(|| dlg.get_value().unwrap_or_default())
}

fn file_style() -> FileDialogStyle {
    FileDialogStyle::Open | FileDialogStyle::FileMustExist
}

fn choose_file(frame: &Frame, title: &str, wildcard: &str) -> Option<std::path::PathBuf> {
    let dlg = FileDialog::builder(frame)
        .with_message(title)
        .with_wildcard(wildcard)
        .with_style(file_style())
        .build();
    if dlg.show_modal() != ID_OK {
        return None;
    }
    dlg.get_path().map(Into::into)
}

/// `_refresh_after_onboarding_import`.
fn refresh_after_onboarding_import(state: &Shared) {
    refresh_runtime_settings();
    mw::populate_locations();
    if !state.borrow().config.locations.is_empty() {
        refresh::refresh_weather_async(true);
    }
}

fn import_settings(state: &Shared, path: &Path) -> bool {
    let imported = {
        let mut st = state.borrow_mut();
        let config_file = st.paths.config_file();
        import_export::import_settings(&mut st.config, path, &config_file)
    };
    if imported {
        refresh_after_onboarding_import(state);
    }
    imported
}

/// `_write_keys_file_after_import`: keep `api-keys.keys` beside a portable copy.
fn write_keys_file_after_import(state: &Shared, passphrase: &str) {
    let mut st = state.borrow_mut();
    let dest = st.paths.config_dir.join(BUNDLE_FILE_NAMES[0]);
    import_export::export_encrypted_api_keys(
        &mut st.config.settings,
        &SystemKeyring,
        &dest,
        passphrase,
    );
}

fn import_api_keys(state: &Shared, path: &Path, passphrase: &str) -> bool {
    let portable = state.borrow().paths.portable;
    let imported = import_export::import_encrypted_api_keys(
        &mut state.borrow_mut().config.settings,
        &mut SystemKeyring,
        path,
        passphrase,
        portable,
    );
    if !imported {
        return false;
    }
    if portable {
        portable_keys::set_keys_imported_this_session();
        secrets::set_password(PORTABLE_PASSPHRASE_KEY, passphrase);
        write_keys_file_after_import(state, passphrase);
    }
    refresh_after_onboarding_import(state);
    true
}

/// The wizard's portable step 4: put the keys in memory and encrypt them
/// into `api-keys.keys`.
fn write_key_bundle(state: &Shared, keys: Vec<(&'static str, String)>, passphrase: &str) -> bool {
    let written = {
        let mut st = state.borrow_mut();
        for (name, value) in keys {
            if let Some(field) = secrets::api_key_mut(&mut st.config.settings, name) {
                *field = value;
            }
        }
        let bundle = st.paths.config_dir.join(BUNDLE_FILE_NAMES[0]);
        import_export::export_encrypted_api_keys(
            &mut st.config.settings,
            &SystemKeyring,
            &bundle,
            passphrase,
        )
    };
    if written {
        portable_keys::set_keys_imported_this_session();
        secrets::set_password(PORTABLE_PASSPHRASE_KEY, passphrase);
    }
    written
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ui::golden_miscui::{golden, wx};

    /// Every onboarding box is `wx.OK`, `wx.YES_NO` or `wx.YES_NO | wx.CANCEL`
    /// plus one icon; entries and file pickers use Python's exact styles.
    #[test]
    fn styles_are_pythons() {
        let wx = wx(&golden());
        let bits = |s: MessageDialogStyle| s.bits() as i32;
        let cases = [
            (
                Buttons::Ok,
                Icon::Information,
                wx["OK"] | wx["ICON_INFORMATION"],
            ),
            (Buttons::Ok, Icon::Warning, wx["OK"] | wx["ICON_WARNING"]),
            (Buttons::Ok, Icon::Error, wx["OK"] | wx["ICON_ERROR"]),
            (
                Buttons::YesNo("a", "b"),
                Icon::Information,
                wx["YES_NO"] | wx["ICON_INFORMATION"],
            ),
            (
                Buttons::YesNoCancel("a", "b", "c"),
                Icon::Information,
                wx["YES_NO"] | wx["CANCEL"] | wx["ICON_INFORMATION"],
            ),
        ];
        for (buttons, icon, expected) in cases {
            assert_eq!(bits(message_style(buttons, icon)), expected, "{buttons:?}");
        }
        assert_eq!(
            secret_style().bits() as i32,
            wx["OK"] | wx["CANCEL"] | wx["TE_PASSWORD"]
        );
        assert_eq!(
            file_style().bits() as i32,
            wx["FD_OPEN"] | wx["FD_FILE_MUST_EXIST"]
        );
        assert_eq!(
            (ID_YES, ID_NO, ID_OK, ID_CANCEL),
            (wx["ID_YES"], wx["ID_NO"], wx["ID_OK"], wx["ID_CANCEL"])
        );
    }

    #[test]
    fn stages_run_at_pythons_delays() {
        let delays: Vec<u64> = GuidanceStage::ALL.iter().map(|s| s.delay_ms()).collect();
        assert_eq!(delays, [400, 800, 1400]);
    }
}
