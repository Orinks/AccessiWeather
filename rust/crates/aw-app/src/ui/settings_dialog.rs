//! The Settings dialog, ported from `ui/dialogs/settings_dialog.py`
//! (`SettingsDialogSimple`, `show_settings_dialog`) and its mixins:
//! `settings_dialog_core.py` (layout, load, save, unsaved changes),
//! `settings_dialog_handlers.py` (buttons), `settings_dialog_transfer.py`
//! (settings and encrypted key export/import) and
//! `settings_dialog_portable.py` (portable key bundle, config copy).
//! Control values live in `settings_form`, pages in `settings_tabs`, the
//! small modals in `settings_modals`, and backend work in `settings_actions`.

use std::cell::{Cell, RefCell};
use std::path::{Path, PathBuf};
use std::rc::Rc;

use aw_core::display::tray::TaskbarIconUpdater;
use aw_services::import_export;
use aw_services::update::{self, messages, UpdateService};
use aw_store::secrets::{self, PORTABLE_PASSPHRASE_KEY};
use serde_json::{Map, Value};
use wxdragon::prelude::*;

use super::main_window::message_box;
use super::settings_actions::{self as actions, TrayPreviewContext};
use super::settings_form::{apply_settings_dict, SettingsForm};
use super::settings_tabs::{self, Controls, ADVANCED_PAGE, TAB_LABELS};
use super::{
    model_browser_dialog, settings_modals, soundpack_manager, tray_text_format_dialog, updates,
};
use crate::app::{post_to_ui, save, save_api_key, Shared};
use crate::screen_reader::announce;

/// `API_KEYS_TRANSFER_NOTE`.
const API_KEYS_TRANSFER_NOTE: &str = "API keys are not included here. API keys stay in this machine's secure keyring by default. To transfer them, use 'Export API keys (encrypted)' and then 'Import API keys (encrypted)'.";
const KEYS_WILDCARD: &str = "Encrypted bundle (*.keys)|*.keys|Legacy bundle (*.awkeys)|*.awkeys";
const JSON_WILDCARD: &str = "JSON files (*.json)|*.json";

const INFO: MessageDialogStyle = MessageDialogStyle::OK.union(MessageDialogStyle::IconInformation);
const WARNING: MessageDialogStyle = MessageDialogStyle::OK.union(MessageDialogStyle::IconWarning);
const ERROR: MessageDialogStyle = MessageDialogStyle::OK.union(MessageDialogStyle::IconError);
const ASK: MessageDialogStyle = MessageDialogStyle::YesNo.union(MessageDialogStyle::IconQuestion);

struct SettingsDialog {
    dialog: Dialog,
    frame: Frame,
    notebook: Notebook,
    c: Controls,
    state: Shared,
    form: RefCell<SettingsForm>,
    /// `_pw_key_cleared` and friends, in `GUARDED_API_KEYS` order: the user
    /// edited that key field since the last load.
    cleared: [Cell<bool>; 4],
    /// `_loaded_tab_values`.
    loaded_values: RefCell<Option<Map<String, Value>>>,
}

thread_local! {
    static DIALOG: RefCell<Option<Rc<SettingsDialog>>> = const { RefCell::new(None) };
}

/// The open Settings dialog, for results posted from worker threads.
fn open_dialog() -> Option<Rc<SettingsDialog>> {
    DIALOG.with(|d| d.borrow().clone())
}

/// `show_settings_dialog`: true when the user saved. `tab` opens a page by
/// its label ("General", "AI", ...).
pub(crate) fn show_settings_dialog(parent: &Frame, state: &Shared, tab: Option<&str>) -> bool {
    let dialog = Dialog::builder(parent, "Settings")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(760, 640)
        .build();

    // `_create_ui`
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();
    for intro in [
        "Review preferences by category. Changes are saved when you choose Save Settings.",
        "Everyday preferences appear first. Maintenance, backup, and reset tools are grouped on the Advanced tab.",
    ] {
        let text = StaticText::builder(&dialog).with_label(intro).build();
        text.wrap(620);
        main_sizer.add(
            &text,
            0,
            SizerFlag::Left | SizerFlag::Right | SizerFlag::Top | SizerFlag::Expand,
            10,
        );
    }
    let notebook = Notebook::builder(&dialog).build();
    let portable = state.borrow().paths.portable;
    let packs = actions::available_sound_packs(aw_audio::player().soundpacks_dir());
    let pack_names: Vec<String> = packs.iter().map(|p| p.name.clone()).collect();
    let c = settings_tabs::build(&notebook, &pack_names, portable);
    main_sizer.add(&notebook, 1, SizerFlag::Expand | SizerFlag::All, 10);

    let button_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    button_sizer.add_stretch_spacer(1);
    let ok = Button::builder(&dialog)
        .with_id(ID_OK)
        .with_label("Save Settings")
        .build();
    let cancel = Button::builder(&dialog)
        .with_id(ID_CANCEL)
        .with_label("Cancel")
        .build();
    button_sizer.add(&ok, 0, SizerFlag::Right, 10);
    button_sizer.add(&cancel, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(
        &button_sizer,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );
    dialog.set_sizer(main_sizer, true);
    dialog.set_min_size(Size::new(700, 580));
    dialog.set_affirmative_id(ID_OK);
    dialog.set_escape_id(ID_CANCEL);
    ok.set_default();

    let d = Rc::new(SettingsDialog {
        dialog,
        frame: *parent,
        notebook,
        c,
        state: state.clone(),
        form: RefCell::new(SettingsForm::new(packs)),
        cleared: Default::default(),
        loaded_values: RefCell::new(None),
    });
    d.load_settings();
    d.bind(ok, cancel);
    if let Some(index) = tab.and_then(|t| TAB_LABELS.iter().position(|l| *l == t)) {
        d.notebook.set_selection(index);
    }

    DIALOG.with(|slot| *slot.borrow_mut() = Some(d.clone()));
    let saved = d.dialog.show_modal() == ID_OK;
    DIALOG.with(|slot| slot.borrow_mut().take());
    d.dialog.destroy();
    saved
}

impl SettingsDialog {
    fn bind(self: &Rc<Self>, ok: Button, cancel: Button) {
        let c = self.c;
        ok.on_click({
            let d = self.clone();
            move |e| {
                e.event.skip(false);
                d.on_ok();
            }
        });
        // Escape and the close box click Cancel too.
        cancel.on_click({
            let d = self.clone();
            move |e| {
                e.event.skip(false);
                d.on_cancel();
            }
        });

        c.taskbar_icon_text_enabled
            .on_toggled(move |e| c.update_taskbar_text_controls_state(e.is_checked()));
        c.taskbar_icon_text_format_dialog
            .on_click(call(self, Self::on_edit_taskbar_text_format));
        c.advanced_timing
            .on_click(call(self, Self::on_alert_advanced));

        c.sound_pack
            .on_selection_changed(call(self, Self::on_sound_pack_changed));
        c.play_sample.on_click(call(self, Self::on_test_sound));
        c.manage_sound_packs
            .on_click(call(self, Self::on_manage_soundpacks));
        c.configure_event_sounds
            .on_click(call(self, Self::on_configure_event_sounds));

        c.data_source
            .on_selection_changed(call(self, Self::on_data_source_changed));
        c.configure_source_settings
            .on_click(call(self, Self::on_configure_source_settings));
        for (i, key) in [
            c.pirate_weather.key,
            c.airnow_key,
            c.openrouter_key,
            c.venice_key,
        ]
        .into_iter()
        .enumerate()
        {
            let d = self.clone();
            key.on_text_changed(move |_| d.cleared[i].set(true));
        }
        c.pirate_weather.get_key.on_click(|_| {
            actions::open_url("https://pirate-weather.apiable.io/signup");
        });
        c.pirate_weather
            .validate_key
            .on_click(call(self, Self::on_validate_pw_api_key));
        c.get_airnow_key.on_click(|_| {
            actions::open_url("https://docs.airnowapi.org/account/request/");
        });
        c.validate_airnow_key
            .on_click(call(self, Self::on_validate_airnow_api_key));

        c.ai_provider.on_selection_changed(move |_| {
            c.apply_provider_visibility(c.ai_provider.get_selection().map_or(0, |i| i as usize));
        });
        c.validate_openrouter_key
            .on_click(call(self, Self::on_validate_openrouter_key));
        c.browse_models.on_click(call(self, Self::on_browse_models));
        c.validate_venice_key
            .on_click(call(self, Self::on_validate_venice_key));
        c.get_venice_key
            .on_click(call(self, Self::on_get_venice_key));
        c.browse_venice_models
            .on_click(call(self, Self::on_browse_venice_models));
        c.reset_prompt
            .on_click(move |_| c.custom_prompt.set_value(""));

        c.check_updates.on_click(call(self, Self::on_check_updates));

        c.minimize_tray.on_toggled(move |e| {
            // `_update_minimize_on_startup_state`
            c.minimize_on_startup.enable(e.is_checked());
            if !e.is_checked() {
                c.minimize_on_startup.set_value(false);
            }
        });
        c.export_settings
            .on_click(call(self, Self::on_export_settings));
        c.import_settings
            .on_click(call(self, Self::on_import_settings));
        c.export_api_keys
            .on_click(call(self, Self::on_export_encrypted_api_keys));
        c.import_api_keys
            .on_click(call(self, Self::on_import_encrypted_api_keys));
        c.open_config_dir
            .on_click(call(self, Self::on_open_config_dir));
        c.open_installed_config_dir
            .on_click(call(self, Self::on_open_installed_config_dir));
        if let Some(copy) = c.copy_installed_config {
            copy.on_click(call(self, Self::on_copy_installed_config_to_portable));
        }
        c.open_soundpacks_dir
            .on_click(call(self, Self::on_open_soundpacks_dir));
        c.reset_defaults
            .on_click(call(self, Self::on_reset_defaults));
        c.full_reset.on_click(call(self, Self::on_full_reset));
    }

    /// `wx.MessageBox`. Python passes no parent, so wx picks the active
    /// window: this dialog once it is on screen, the main window before.
    fn message(&self, text: &str, caption: &str, style: MessageDialogStyle) -> i32 {
        if self.dialog.is_shown() {
            message_box(&self.dialog, text, caption, style)
        } else {
            message_box(&self.frame, text, caption, style)
        }
    }

    fn portable(&self) -> bool {
        self.state.borrow().paths.portable
    }

    fn config_dir(&self) -> PathBuf {
        self.state.borrow().paths.config_dir.clone()
    }

    // ------------------------------------------------------------------
    // Load, collect, save (`settings_dialog_core.py`)
    // ------------------------------------------------------------------

    /// `_load_settings`.
    fn load_settings(&self) {
        let settings = self.state.borrow().config.settings.clone();
        let actual = crate::lifecycle::is_startup_enabled();
        if actual != settings.startup_enabled {
            tracing::info!(
                "Startup setting differs from OS registration: configured={}, actual={actual}",
                settings.startup_enabled
            );
        }
        {
            let mut form = self.form.borrow_mut();
            form.load(&settings, actual);
            self.c.push(&form);
        }
        for flag in &self.cleared {
            flag.set(false);
        }
        let values = self.collect_values();
        *self.loaded_values.borrow_mut() = Some(values);
    }

    /// `_collect_tab_values`, showing the "Invalid hotkey" warning as the
    /// General tab does while collecting.
    fn collect_values(&self) -> Map<String, Value> {
        let (values, warning) = {
            let mut form = self.form.borrow_mut();
            self.c.pull(&mut form);
            form.collect()
        };
        if let Some(warning) = warning {
            self.message(&warning, "Invalid hotkey", WARNING);
        }
        values
    }

    /// `_has_unsaved_changes`.
    fn has_unsaved_changes(&self) -> bool {
        let current = self.collect_values();
        self.loaded_values
            .borrow()
            .as_ref()
            .is_some_and(|loaded| *loaded != current)
    }

    /// `_on_cancel`: ask before discarding edits.
    fn on_cancel(&self) {
        if self.has_unsaved_changes() {
            let answer = message_box(
                &self.dialog,
                "You have unsaved changes. Save them before closing Settings?",
                "Unsaved Changes",
                MessageDialogStyle::YesNo
                    | MessageDialogStyle::Cancel
                    | MessageDialogStyle::IconQuestion,
            );
            if answer == ID_CANCEL {
                return;
            }
            if answer == ID_YES {
                self.on_ok();
                return;
            }
        }
        self.dialog.end_modal(ID_CANCEL);
    }

    /// `_on_ok`.
    fn on_ok(&self) {
        let problem = {
            let mut form = self.form.borrow_mut();
            self.c.pull(&mut form);
            let problem = form.validate_window_tray_shortcuts();
            self.c.push_shortcuts(&form);
            problem
        };
        if let Some((setting, message)) = problem {
            self.message(&message, "Shortcut Problem", WARNING);
            self.focus_settings_control(setting);
            return;
        }
        if self.save_settings() {
            self.dialog.end_modal(ID_OK);
        } else {
            self.message("Failed to save settings.", "Error", ERROR);
        }
    }

    /// `_focus_settings_control`: bring the field's page forward and select
    /// its text so the fix is one keystroke away.
    fn focus_settings_control(&self, setting: &str) {
        self.notebook.set_selection(ADVANCED_PAGE);
        let control = self.c.shortcut_control(setting);
        control.set_focus();
        control.select_all();
    }

    fn cleared_flags(&self) -> [bool; 4] {
        std::array::from_fn(|i| self.cleared[i].get())
    }

    /// `_save_settings`.
    fn save_settings(&self) -> bool {
        let mut values = self.collect_values();
        self.form
            .borrow()
            .guard_api_keys(&mut values, self.cleared_flags());
        if !self.apply_startup_enabled_setting(&mut values) {
            return false;
        }
        let success = self.update_settings(values.clone());
        if success {
            tracing::info!("Settings saved successfully");
            if self.portable() {
                self.maybe_update_portable_bundle_after_save(&values);
            }
        }
        success
    }

    /// `config_manager.update_settings`: API keys to the keyring (installed
    /// mode; portable mode keeps them for the bundle), everything else onto
    /// the settings, then the config file.
    fn update_settings(&self, mut values: Map<String, Value>) -> bool {
        let mut st = self.state.borrow_mut();
        let mut credentials_saved = true;
        if !st.paths.portable {
            for name in secrets::API_KEY_NAMES {
                let Some(value) = values.get(name).and_then(Value::as_str).map(str::to_string)
                else {
                    continue;
                };
                let old = secrets::api_key_mut(&mut st.config.settings, name)
                    .map(|v| v.clone())
                    .unwrap_or_default();
                if save_api_key(&mut st, name, &value) {
                    values.insert(name.to_string(), value.trim().into());
                } else {
                    tracing::error!("Failed to save {name} to secure storage");
                    credentials_saved = false;
                    if let Some(field) = secrets::api_key_mut(&mut st.config.settings, name) {
                        *field = old;
                    }
                    values.remove(name);
                }
            }
        }
        if let Err(e) = apply_settings_dict(&mut st.config.settings, &values) {
            tracing::error!("Failed to save settings: {e}");
            return false;
        }
        save(&st).is_ok() && credentials_saved
    }

    /// `_apply_startup_enabled_setting`: register or unregister launch at
    /// startup when the checkbox changed; false when that failed.
    fn apply_startup_enabled_setting(&self, values: &mut Map<String, Value>) -> bool {
        let Some(desired) = values.get("startup_enabled").and_then(Value::as_bool) else {
            return true;
        };
        let previous = self.form.borrow().state.loaded_startup_enabled;
        if crate::lifecycle::apply_startup_enabled_setting(&self.dialog, desired, previous) {
            self.form.borrow_mut().state.loaded_startup_enabled = desired;
            return true;
        }
        values.insert("startup_enabled".into(), previous.into());
        false
    }

    // ------------------------------------------------------------------
    // Portable key bundle (`settings_dialog_portable.py`)
    // ------------------------------------------------------------------

    /// `_maybe_update_portable_bundle_after_save`: re-encrypt the portable
    /// key bundle, asking for its passphrase when none is cached.
    fn maybe_update_portable_bundle_after_save(&self, values: &Map<String, Value>) {
        let has_keys = values.iter().any(|(k, v)| {
            secrets::API_KEY_NAMES.contains(&k.as_str())
                && v.as_str().is_some_and(|s| !s.is_empty())
        });
        if !has_keys || self.state.borrow().offline {
            return;
        }
        let config_dir = self.config_dir();
        let bundle = secrets::find_bundle(&config_dir);
        let mut passphrase = secrets::get_password(PORTABLE_PASSPHRASE_KEY)
            .unwrap_or_default()
            .trim()
            .to_string();
        if passphrase.is_empty() {
            let message = if bundle.is_some() {
                "Your API keys have been updated.\n\nEnter your bundle passphrase to re-encrypt the portable key bundle, or Cancel to leave the bundle unchanged (keys are active this session only)."
            } else {
                "Your API keys have been updated.\n\nEnter a passphrase to create an encrypted key bundle so your keys persist across launches, or Cancel to skip (keys active this session only)."
            };
            let Some(entered) = self.prompt_passphrase("Portable key bundle", message) else {
                return;
            };
            secrets::set_password(PORTABLE_PASSPHRASE_KEY, &entered);
            passphrase = entered;
        }
        let path = bundle.unwrap_or_else(|| config_dir.join(secrets::BUNDLE_FILE_NAMES[0]));
        let exported =
            actions::export_encrypted_api_keys(&mut self.state.borrow_mut(), &path, &passphrase);
        if exported {
            tracing::info!("Portable key bundle updated after settings save.");
        } else {
            self.message(
                "No API keys found to export. Keys are active this session but won't persist.",
                "Bundle update skipped",
                WARNING,
            );
        }
    }

    /// `_on_copy_installed_config_to_portable`.
    fn on_copy_installed_config_to_portable(&self) {
        let portable_dir = self.config_dir();
        let installed_dir = import_export::installed_config_dir().unwrap_or_default();
        if let Err(reason) = import_export::check_installed_config(&installed_dir) {
            self.message(
                &format!(
                    "Nothing to transfer from installed config.\n{}\n\nDetails: {reason}",
                    installed_dir.display()
                ),
                "Nothing to copy",
                WARNING,
            );
            return;
        }
        let same = match (installed_dir.canonicalize(), portable_dir.canonicalize()) {
            (Ok(a), Ok(b)) => a == b,
            _ => installed_dir == portable_dir,
        };
        if same {
            self.message(
                "Installed and portable config directories are the same location.\n\nNo copy is needed.",
                "Nothing to copy",
                INFO,
            );
            return;
        }
        let answer = self.message(
            "Copy settings and locations from installed config to this portable config?\n\nOnly core config files are copied. Cache files are skipped and will regenerate.\n\nExisting files in portable config with the same name will be overwritten.",
            "Copy installed config to portable",
            ASK,
        );
        if answer != ID_YES {
            return;
        }
        let _ = save(&self.state.borrow());

        let copied =
            actions::copy_installed_config(&self.state.borrow(), &installed_dir, &portable_dir);
        let copied = match copied {
            Ok(copied) => copied,
            Err(e) => {
                tracing::error!("Failed to copy installed config to portable: {e}");
                self.message(&format!("Failed to copy config: {e}"), "Copy failed", ERROR);
                return;
            }
        };
        if copied.is_empty() {
            self.message(
                "Nothing to transfer from installed config.\n\nNo transferable config files were found.",
                "Nothing to copy",
                WARNING,
            );
            return;
        }
        if let Err(problems) = import_export::validate_portable_copy(&installed_dir, &portable_dir)
        {
            let details: Vec<String> = problems.iter().map(|m| format!("• {m}")).collect();
            self.message(
                &format!(
                    "Config copy completed, but validation found problems.\n\nPortable data may be incomplete.\n\n{}",
                    details.join("\n")
                ),
                "Copy incomplete",
                WARNING,
            );
            return;
        }
        let reloaded = actions::reload_config(&mut self.state.borrow_mut())
            .and_then(|()| import_export::portable_copy_summary(&portable_dir));
        let summary = match reloaded {
            Ok(summary) => summary,
            Err(e) => {
                tracing::error!("Failed to copy installed config to portable: {e}");
                self.message(&format!("Failed to copy config: {e}"), "Copy failed", ERROR);
                return;
            }
        };
        self.load_settings();
        let copied_list: Vec<String> = copied.iter().map(|n| format!("• {n}")).collect();
        self.message(
            &format!(
                "Copied these config item(s):\n{}\n\nCopied settings summary:\n{}\n\nFrom:\n{}\n\nTo:\n{}",
                copied_list.join("\n"),
                summary.join("\n"),
                installed_dir.display(),
                portable_dir.display()
            ),
            "Copy complete",
            INFO,
        );
        self.offer_api_key_export_after_copy(&portable_dir);
    }

    /// `_offer_api_key_export_after_copy`.
    fn offer_api_key_export_after_copy(&self, portable_dir: &Path) {
        let answer = self.message(
            "Config copied. Your API keys are stored in the system keyring and were not copied.\n\nWould you like to export them to an encrypted bundle now so they work in portable mode?",
            "Export API keys?",
            ASK,
        );
        if answer != ID_YES {
            self.message(
                "You can export API keys later from Settings > Advanced > Export API keys (encrypted).",
                "API keys not exported",
                INFO,
            );
            return;
        }
        let Some(passphrase) = self.prompt_passphrase(
            "Export API keys (encrypted)",
            "Enter a passphrase to encrypt your API keys.",
        ) else {
            return;
        };
        let Some(confirm) =
            self.prompt_passphrase("Confirm passphrase", "Re-enter the passphrase to confirm.")
        else {
            return;
        };
        if passphrase != confirm {
            self.message(
                "Passphrases do not match. API keys were not exported.",
                "Export cancelled",
                WARNING,
            );
            return;
        }
        let path = portable_dir.join(secrets::BUNDLE_FILE_NAMES[0]);
        if actions::export_encrypted_api_keys(&mut self.state.borrow_mut(), &path, &passphrase) {
            self.message(
                &format!("API keys exported to:\n{}", path.display()),
                "Export complete",
                INFO,
            );
        } else {
            self.message(
                "No API keys found to export. You can add keys in Settings > Data Sources or Settings > AI and export later.",
                "No keys to export",
                WARNING,
            );
        }
    }

    // ------------------------------------------------------------------
    // Export / import (`settings_dialog_transfer.py`)
    // ------------------------------------------------------------------

    /// `_prompt_passphrase`: masked entry; `None` when cancelled or blank.
    fn prompt_passphrase(&self, title: &str, message: &str) -> Option<String> {
        let dlg = TextEntryDialog::builder(&self.dialog, message, title)
            .with_style(
                TextEntryDialogStyle::Ok
                    | TextEntryDialogStyle::Cancel
                    | TextEntryDialogStyle::Password,
            )
            .build();
        let ok = dlg.show_modal() == ID_OK;
        let value = dlg.get_value().unwrap_or_default().trim().to_string();
        dlg.destroy();
        (ok && !value.is_empty()).then_some(value)
    }

    fn file_dialog(
        &self,
        title: &str,
        wildcard: &str,
        default_file: Option<&str>,
    ) -> Option<PathBuf> {
        let mut builder = FileDialog::builder(&self.dialog)
            .with_message(title)
            .with_wildcard(wildcard);
        builder = match default_file {
            Some(file) => builder
                .with_default_file(file)
                .with_style(FileDialogStyle::Save | FileDialogStyle::OverwritePrompt),
            None => builder.with_style(FileDialogStyle::Open | FileDialogStyle::FileMustExist),
        };
        let dlg = builder.build();
        let path = (dlg.show_modal() == ID_OK)
            .then(|| dlg.get_path())
            .flatten()
            .map(PathBuf::from);
        dlg.destroy();
        path
    }

    /// `_on_export_encrypted_api_keys`.
    fn on_export_encrypted_api_keys(&self) {
        let Some(passphrase) = self.prompt_passphrase(
            "Export API keys (encrypted)",
            "Enter a passphrase to encrypt exported API keys.",
        ) else {
            return;
        };
        let Some(confirm) = self.prompt_passphrase(
            "Confirm passphrase",
            "Re-enter the passphrase to confirm encrypted export.",
        ) else {
            return;
        };
        if passphrase != confirm {
            self.message("Passphrases do not match.", "Export Cancelled", WARNING);
            return;
        }
        let Some(path) = self.file_dialog(
            "Export API keys (encrypted)",
            KEYS_WILDCARD,
            Some("accessiweather_api_keys.keys"),
        ) else {
            return;
        };
        if actions::export_encrypted_api_keys(&mut self.state.borrow_mut(), &path, &passphrase) {
            self.message(
                &format!(
                    "Encrypted API key bundle exported successfully to:\n{}",
                    path.display()
                ),
                "Export Complete",
                INFO,
            );
        } else {
            self.message(
                "Failed to export encrypted API keys. Ensure at least one API key is saved.",
                "Export Failed",
                ERROR,
            );
        }
    }

    /// `_on_import_encrypted_api_keys`.
    fn on_import_encrypted_api_keys(&self) {
        let Some(path) = self.file_dialog("Import API keys (encrypted)", KEYS_WILDCARD, None)
        else {
            return;
        };
        let Some(passphrase) = self.prompt_passphrase(
            "Import API keys (encrypted)",
            "Enter the passphrase used when exporting this encrypted bundle.",
        ) else {
            return;
        };
        if actions::import_encrypted_api_keys(&mut self.state.borrow_mut(), &path, &passphrase) {
            self.load_settings();
            self.message(
                "Encrypted API keys imported successfully into this machine's secure keyring.",
                "Import Complete",
                INFO,
            );
        } else {
            self.message(
                "Failed to import encrypted API keys. Check passphrase and bundle file.",
                "Import Failed",
                ERROR,
            );
        }
    }

    /// `_on_export_settings`.
    fn on_export_settings(&self) {
        let Some(path) = self.file_dialog(
            "Export Settings",
            JSON_WILDCARD,
            Some("accessiweather_settings.json"),
        ) else {
            return;
        };
        let exported = import_export::export_settings(&self.state.borrow().config, &path);
        if exported {
            self.message(
                &format!(
                    "Settings exported successfully to:\n{}\n\nNote: {API_KEYS_TRANSFER_NOTE}",
                    path.display()
                ),
                "Export Complete",
                INFO,
            );
        } else {
            self.message(
                "Failed to export settings. Please try again.",
                "Export Failed",
                ERROR,
            );
        }
    }

    /// `_on_import_settings`.
    fn on_import_settings(&self) {
        let Some(path) = self.file_dialog("Import Settings", JSON_WILDCARD, None) else {
            return;
        };
        let answer = self.message(
            &format!(
                "Importing settings will overwrite your current preferences.\n\nYour saved locations will NOT be affected.\n\nImportant: {API_KEYS_TRANSFER_NOTE}\n\nDo you want to continue?"
            ),
            "Confirm Import",
            ASK,
        );
        if answer != ID_YES {
            return;
        }
        let imported = actions::import_settings(&mut self.state.borrow_mut(), &path);
        if imported {
            self.load_settings();
            self.message(
                &format!("Settings imported successfully!\n\nNote: {API_KEYS_TRANSFER_NOTE}"),
                "Import Complete",
                INFO,
            );
        } else {
            self.message(
                "Failed to import settings.\n\nThe file may be invalid or corrupted.",
                "Import Failed",
                ERROR,
            );
        }
    }

    // ------------------------------------------------------------------
    // Buttons (`settings_dialog_handlers.py`)
    // ------------------------------------------------------------------

    /// `_on_edit_taskbar_text_format`.
    fn on_edit_taskbar_text_format(&self) {
        let (weather, temperature_unit, wind_speed_unit) = {
            let mut form = self.form.borrow_mut();
            self.c.pull(&mut form);
            (
                self.state.borrow().current_weather_data.clone(),
                form.selected_temperature_unit().to_string(),
                form.selected_wind_speed_unit().to_string(),
            )
        };
        let initial = self.c.taskbar_icon_text_format.get_value();
        let context = TrayPreviewContext {
            updater: TaskbarIconUpdater {
                text_enabled: true,
                dynamic_enabled: self.c.taskbar_icon_dynamic_enabled.is_checked(),
                format_string: initial.clone(),
                temperature_unit,
                wind_speed_unit,
                ..TaskbarIconUpdater::default()
            },
            location_name: weather.as_ref().map(|w| w.location.name.clone()),
            weather,
        };
        if let Some(format) =
            tray_text_format_dialog::show_tray_text_format_dialog(&self.dialog, context, &initial)
        {
            self.c.taskbar_icon_text_format.set_value(&format);
        }
    }

    /// `_on_alert_advanced`.
    fn on_alert_advanced(&self) {
        let values = {
            let f = self.form.borrow();
            (f.global_cooldown, f.per_alert_cooldown, f.freshness_window)
        };
        if let Some((global, per_alert, freshness)) =
            settings_modals::show_alert_timing_dialog(&self.dialog, values)
        {
            let mut f = self.form.borrow_mut();
            f.global_cooldown = global;
            f.per_alert_cooldown = per_alert;
            f.freshness_window = freshness;
        }
    }

    /// `_on_sound_pack_changed`.
    fn on_sound_pack_changed(&self) {
        let mut form = self.form.borrow_mut();
        form.sound_pack = self.c.sound_pack.get_selection().map(|i| i as usize);
        form.refresh_specific_alert_sounds_control();
        self.c.push_specific_alert_sounds(&form);
    }

    /// `_on_test_sound`.
    fn on_test_sound(&self) {
        let pack = {
            let mut form = self.form.borrow_mut();
            form.sound_pack = self.c.sound_pack.get_selection().map(|i| i as usize);
            form.selected_sound_pack().to_string()
        };
        aw_audio::player().play_sample(&pack);
    }

    /// `_on_manage_soundpacks` then `_refresh_sound_pack_list`.
    fn on_manage_soundpacks(&self) {
        soundpack_manager::open_soundpack_manager(&self.dialog);
        let packs = actions::available_sound_packs(aw_audio::player().soundpacks_dir());
        let mut form = self.form.borrow_mut();
        let current = self
            .c
            .sound_pack
            .get_selection()
            .and_then(|i| form.state.sound_packs.get(i as usize))
            .map_or("default".to_string(), |p| p.id.clone());
        form.sound_pack = packs
            .iter()
            .position(|p| p.id == current)
            .or((!packs.is_empty()).then_some(0));
        form.state.sound_packs = packs;
        self.c.push_sound_packs(&form);
    }

    /// `_on_configure_event_sounds`.
    fn on_configure_event_sounds(&self) {
        let states = self.form.borrow().state.event_sound_states.clone();
        if let Some(updated) = settings_modals::show_event_sounds_dialog(&self.dialog, &states) {
            let mut form = self.form.borrow_mut();
            form.state.event_sound_states = updated;
            self.c
                .event_sounds_summary
                .set_label(&form.event_sound_summary());
        }
    }

    /// `_on_data_source_changed`.
    fn on_data_source_changed(&self) {
        let mut form = self.form.borrow_mut();
        form.data_source = self.c.data_source.get_selection().map_or(0, |i| i as usize);
        self.c.update_api_key_visibility(&form);
    }

    /// `_on_configure_source_settings`.
    fn on_configure_source_settings(&self) {
        let state = self.form.borrow().state.source_settings.clone();
        if let Some(updated) = settings_modals::show_source_settings_dialog(&self.dialog, &state) {
            let mut form = self.form.borrow_mut();
            form.state.source_settings = updated;
            self.c.push_source_settings_summary(&form);
        }
    }

    /// `_on_validate_pw_api_key` / `_on_validate_airnow_api_key`: Python
    /// blocks behind a busy cursor; here the check runs on a worker thread.
    fn validate_provider_key(
        &self,
        key: String,
        provider: &'static str,
        check: fn(&str) -> Result<(), String>,
    ) {
        if key.is_empty() {
            self.message("Please enter an API key first.", "Validation", WARNING);
            return;
        }
        begin_busy_cursor(None);
        std::thread::Builder::new()
            .name("aw-validate-key".into())
            .spawn(move || {
                let result = check(&key);
                post_to_ui(move || {
                    end_busy_cursor();
                    let Some(d) = open_dialog() else { return };
                    match result {
                        Ok(()) => d.message(
                            &format!("{provider} API key is valid!"),
                            "Validation Successful",
                            INFO,
                        ),
                        Err(error) => d.message(
                            &format!("{provider} API key validation failed: {error}"),
                            "Validation Failed",
                            ERROR,
                        ),
                    };
                });
            })
            .expect("spawn key validation thread");
    }

    fn on_validate_pw_api_key(&self) {
        let key = self.c.pirate_weather.key.get_value();
        self.validate_provider_key(key, "Pirate Weather", actions::validate_pirate_weather_key);
    }

    fn on_validate_airnow_api_key(&self) {
        let key = self.c.airnow_key.get_value();
        self.validate_provider_key(key, "AirNow", actions::validate_airnow_key);
    }

    /// `_on_validate_openrouter_key` / `_on_validate_venice_key`: validate
    /// without blocking, and distrust a result for a key edited meanwhile.
    fn validate_ai_key(
        &self,
        field: TextCtrl,
        button: Button,
        provider: &'static str,
        check: fn(&str) -> (bool, String),
    ) {
        let key = field.get_value().trim().to_string();
        if key.is_empty() {
            self.message(
                &format!("Please enter your {provider} API key first."),
                "Validation",
                WARNING,
            );
            field.set_focus();
            return;
        }
        button.enable(false);
        field.set_focus();
        announce(&format!("Validating {provider} key…"));
        std::thread::Builder::new()
            .name("aw-validate-key".into())
            .spawn(move || {
                let (valid, message) = check(&key);
                post_to_ui(move || {
                    let Some(d) = open_dialog() else { return };
                    button.enable(true);
                    let (valid, message) = if field.get_value().trim() != key {
                        let message =
                            "The key changed during validation. Please validate again.".to_string();
                        announce(&message);
                        (false, message)
                    } else {
                        (valid, message)
                    };
                    let (caption, style) = if valid {
                        (format!("{provider} Key Valid"), INFO)
                    } else {
                        (format!("{provider} Validation Failed"), ERROR)
                    };
                    message_box(&d.dialog, &message, &caption, style);
                    button.set_focus();
                });
            })
            .expect("spawn key validation thread");
    }

    fn on_validate_openrouter_key(&self) {
        self.validate_ai_key(
            self.c.openrouter_key,
            self.c.validate_openrouter_key,
            "OpenRouter",
            aw_ai::provider::validate_openrouter_api_key,
        );
    }

    fn on_validate_venice_key(&self) {
        self.validate_ai_key(
            self.c.venice_key,
            self.c.validate_venice_key,
            "Venice",
            aw_ai::provider::validate_venice_api_key,
        );
    }

    /// `AITab._on_get_venice_key`.
    fn on_get_venice_key(&self) {
        if !actions::open_url("https://venice.ai/settings/api") {
            message_box(
                &self.dialog,
                "Could not open your browser. Visit https://venice.ai/settings/api to sign up or manage your Venice API keys.",
                "Open Venice API settings",
                ERROR,
            );
        }
    }

    /// `_on_browse_models`.
    fn on_browse_models(&self) {
        let key = self.c.openrouter_key.get_value();
        let selected = model_browser_dialog::show_model_browser_dialog(
            &self.dialog,
            (!key.is_empty()).then_some(key),
            "openrouter",
        );
        if let Some(model_id) = selected.filter(|m| !m.is_empty()) {
            let mut form = self.form.borrow_mut();
            form.select_browsed_model(&model_id);
            self.c.push_ai_model(&form);
        }
    }

    /// `AITab._on_browse_venice_models`.
    fn on_browse_venice_models(&self) {
        let key = self.c.venice_key.get_value().trim().to_string();
        let selected = model_browser_dialog::show_model_browser_dialog(
            &self.dialog,
            (!key.is_empty()).then_some(key),
            "venice",
        );
        if let Some(model_id) = selected.filter(|m| !m.is_empty()) {
            self.c.venice_model.set_value(&model_id);
        }
    }

    /// `_on_check_updates`.
    fn on_check_updates(&self) {
        if aw_services::is_running_from_source() {
            self.message(
                messages::RUNNING_FROM_SOURCE,
                messages::RUNNING_FROM_SOURCE_TITLE,
                INFO,
            );
            return;
        }
        self.c.update_status.set_label(messages::CHECKING_STATUS);
        let channel = if self.c.update_channel.get_selection() == Some(1) {
            "nightly"
        } else {
            "stable"
        };
        let nightly_date =
            crate::lifecycle::build_tag().and_then(|tag| update::parse_nightly_date(&tag));
        let current_version = nightly_date
            .clone()
            .unwrap_or_else(crate::lifecycle::app_version);
        std::thread::Builder::new()
            .name("aw-update-check".into())
            .spawn(move || {
                let result = UpdateService::new().and_then(|service| {
                    service.check_for_updates(&current_version, nightly_date.as_deref(), channel)
                });
                post_to_ui(move || {
                    let Some(d) = open_dialog() else { return };
                    let status = d.c.update_status;
                    match result {
                        Ok(None) => {
                            let message = messages::no_update(
                                nightly_date.as_deref(),
                                channel,
                                &current_version,
                            );
                            status.set_label(&message);
                            d.message(&message, messages::NO_UPDATES_TITLE, INFO);
                        }
                        Ok(Some(info)) => {
                            status.set_label(&messages::update_available_status(&info.version));
                            updates::offer_update(&d.dialog, &current_version, info);
                        }
                        Err(e) => {
                            tracing::error!("Error checking for updates: {e}");
                            status.set_label(messages::CHECK_FAILED_STATUS);
                            d.message(
                                &messages::check_failed(&e.to_string()),
                                messages::CHECK_FAILED_TITLE,
                                ERROR,
                            );
                        }
                    }
                });
            })
            .expect("spawn update check thread");
    }

    /// `_on_reset_defaults`.
    fn on_reset_defaults(&self) {
        let answer = self.message(
            "Are you sure you want to reset all settings to defaults?\n\nYour saved locations will be preserved.",
            "Confirm Reset",
            ASK,
        );
        if answer != ID_YES {
            return;
        }
        if actions::reset_to_defaults(&mut self.state.borrow_mut()) {
            self.load_settings();
            self.message(
                "Settings have been reset to defaults.\n\nYour locations have been preserved.",
                "Reset Complete",
                INFO,
            );
        } else {
            self.message(
                "Failed to reset settings. Please try again.",
                "Reset Failed",
                ERROR,
            );
        }
    }

    /// `_on_full_reset`: two confirmations, then everything goes.
    fn on_full_reset(&self) {
        let answer = self.message(
            "Are you sure you want to reset ALL application data?\n\nThis will delete:\n• All settings\n• All saved locations\n• All caches\n• Alert history\n\nThis action cannot be undone!",
            "Confirm Full Reset",
            MessageDialogStyle::YesNo | MessageDialogStyle::IconWarning,
        );
        if answer != ID_YES {
            return;
        }
        let answer = self.message(
            "This is your last chance to cancel.\n\nAre you absolutely sure you want to delete all data?",
            "Final Confirmation",
            MessageDialogStyle::YesNo | MessageDialogStyle::IconWarning,
        );
        if answer != ID_YES {
            return;
        }
        if actions::reset_all_data(&mut self.state.borrow_mut()) {
            self.load_settings();
            self.message(
                "All application data has been reset.\n\nThe application will now use default settings.",
                "Reset Complete",
                INFO,
            );
        } else {
            self.message(
                "Failed to reset application data. Please try again.",
                "Reset Failed",
                ERROR,
            );
        }
    }

    /// `_on_open_config_dir`.
    fn on_open_config_dir(&self) {
        let dir = self.config_dir();
        if dir.exists() {
            aw_services::open_in_shell(&dir);
        } else {
            self.message(
                &format!("Config directory not found: {}", dir.display()),
                "Error",
                ERROR,
            );
        }
    }

    /// `_on_open_installed_config_dir`.
    fn on_open_installed_config_dir(&self) {
        let dir = import_export::installed_config_dir().unwrap_or_default();
        if dir.exists() {
            aw_services::open_in_shell(&dir);
        } else {
            self.message(
                &format!("Installed config directory not found: {}", dir.display()),
                "Info",
                INFO,
            );
        }
    }

    /// `_on_open_soundpacks_dir`.
    fn on_open_soundpacks_dir(&self) {
        let dir = aw_audio::player().soundpacks_dir();
        if dir.exists() {
            aw_services::open_in_shell(dir);
        } else {
            self.message(
                &format!("Sound packs directory not found: {}", dir.display()),
                "Error",
                ERROR,
            );
        }
    }
}

/// An event handler that runs `f` on the dialog, whatever the event data.
fn call<E>(d: &Rc<SettingsDialog>, f: fn(&SettingsDialog)) -> impl FnMut(E) + 'static {
    let d = d.clone();
    move |_| f(&d)
}
