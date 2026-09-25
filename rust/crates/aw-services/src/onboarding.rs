//! First-run onboarding and the portable key hint (`app_startup_guidance.py`)
//! as a state machine. The UI shows each [`Step`], performs the action it
//! names, and reports the outcome with [`Onboarding::advance`], passing
//! fresh [`Facts`] every time.
//!
//! ```text
//! if should_show_onboarding(..) {
//!     let mut wizard = Onboarding::new(portable);
//!     let mut step = wizard.start(&facts);
//!     while step != Step::Finished {
//!         let response = ui.perform(&step);
//!         step = wizard.advance(response, &facts_now());
//!     }
//! }
//! // Finished and "not shown" both: save onboarding_wizard_shown = true
//! // (only after the wizard ran) and run the deferred startup update check.
//! ```

use std::path::PathBuf;

/// `_schedule_startup_guidance_prompts` delays after the main window shows.
pub const AUTO_IMPORT_KEYS_DELAY_MS: u64 = 400;
pub const ONBOARDING_DELAY_MS: u64 = 800;
pub const PORTABLE_HINT_DELAY_MS: u64 = 1400;

/// `_should_show_first_start_onboarding`. While it is true the startup
/// update check waits for the wizard to finish.
pub fn should_show_onboarding(
    force_wizard: bool,
    onboarding_wizard_shown: bool,
    has_locations: bool,
) -> bool {
    force_wizard || (!onboarding_wizard_shown && !has_locations)
}

/// `_maybe_show_portable_missing_keys_hint`: a portable copy with no key
/// bundle and no keys gets [`portable_missing_keys_hint`] once. Whatever the
/// answer, save `portable_missing_api_keys_hint_shown = true`; Yes opens
/// Settings.
pub fn should_show_portable_missing_keys_hint(
    portable: bool,
    hint_shown: bool,
    onboarding_will_show: bool,
    bundle_exists: bool,
    keys_imported_this_session: bool,
) -> bool {
    portable
        && !hint_shown
        && !onboarding_will_show
        && !bundle_exists
        && !keys_imported_this_session
}

pub fn portable_missing_keys_hint() -> Dialog {
    Dialog {
        title: "Portable setup hint".into(),
        message: "This portable copy has no API keys yet.\n\n\
                  Pirate Weather provider keys can be entered in Settings > Data Sources. \
                  OpenRouter AI keys can be entered in Settings > AI.\n\n\
                  You can also create an encrypted key bundle to carry your keys with the portable install."
            .into(),
        buttons: Buttons::YesNoCancel("Open Settings", "Later", "Cancel"),
        icon: Icon::Information,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Buttons {
    /// A plain OK message box.
    Ok,
    YesNo(&'static str, &'static str),
    YesNoCancel(&'static str, &'static str, &'static str),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Icon {
    Information,
    Warning,
    Error,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Dialog {
    pub title: String,
    pub message: String,
    pub buttons: Buttons,
    pub icon: Icon,
}

/// What the UI does next.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Step {
    /// A message dialog; answer Yes/No/Cancel (Escape is Cancel), or Ok.
    Dialog(Dialog),
    /// A password text entry; answer `Text` (trimmed by the machine) or Cancel.
    Secret { title: String, message: String },
    /// A file-open dialog; answer `File(Some(path))` or `File(None)`.
    ChooseFile {
        title: &'static str,
        wildcard: &'static str,
    },
    /// Run the main window's Add Location flow; answer Done.
    AddLocation,
    /// Import a settings export, then refresh settings, the location list
    /// and (with locations) the weather; answer `Success`.
    ImportSettings(PathBuf),
    /// Import an encrypted key bundle and refresh. On success in portable
    /// mode also remember keys-imported-this-session, cache the passphrase
    /// in the keyring and rewrite `api-keys.keys`. Answer `Success`.
    ImportApiKeys { path: PathBuf, passphrase: String },
    /// Open a web page; answer Done.
    OpenUrl(&'static str),
    /// Installed mode: save the key (`update_settings`); answer Done.
    SaveApiKey { name: &'static str, value: String },
    /// Open Settings on `tab`; answer Done.
    OpenSettings { tab: Option<&'static str> },
    /// Portable mode: put `keys` into the in-memory settings and export the
    /// bundle to `api-keys.keys`; on success remember keys-imported-this-session
    /// and cache the passphrase. Answer `Success`.
    WriteKeyBundle {
        keys: Vec<(&'static str, String)>,
        passphrase: String,
    },
    /// The wizard closed: save `onboarding_wizard_shown = true` and run the
    /// deferred startup update check.
    Finished,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Response {
    Yes,
    No,
    Cancel,
    Ok,
    Text(String),
    File(Option<PathBuf>),
    Success(bool),
    Done,
}

/// The app state the flow reads, current at each `advance`.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Facts {
    pub has_locations: bool,
    pub keyring_available: bool,
    /// `_has_saved_api_key`: in-memory settings when portable, else the keyring.
    pub has_openrouter_key: bool,
    pub has_pirate_weather_key: bool,
    pub portable_keys_imported_this_session: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Key {
    OpenRouter,
    PirateWeather,
}

impl Key {
    fn name(self) -> &'static str {
        match self {
            Key::OpenRouter => "openrouter_api_key",
            Key::PirateWeather => "pirate_weather_api_key",
        }
    }

    fn label(self) -> &'static str {
        match self {
            Key::OpenRouter => "OpenRouter API key",
            Key::PirateWeather => "Pirate Weather provider key",
        }
    }

    fn title(self) -> &'static str {
        match self {
            Key::OpenRouter => "OpenRouter API key (optional)",
            Key::PirateWeather => "Pirate Weather provider key (optional)",
        }
    }

    fn url(self) -> &'static str {
        match self {
            Key::OpenRouter => "https://openrouter.ai/keys",
            Key::PirateWeather => "https://pirateweather.net/",
        }
    }

    fn action(self) -> &'static str {
        match self {
            Key::OpenRouter => "Get OpenRouter API key",
            Key::PirateWeather => "Get Pirate Weather provider key",
        }
    }

    fn saved(self, facts: &Facts) -> bool {
        match self {
            Key::OpenRouter => facts.has_openrouter_key,
            Key::PirateWeather => facts.has_pirate_weather_key,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum State {
    Welcome,
    AddingLocation,
    AskImportSettings,
    ChoosingSettingsFile,
    ImportingSettings,
    SettingsResult,
    AskImportKeys,
    ChoosingKeysFile,
    KeysPassphrase(PathBuf),
    ImportingKeys,
    KeysResult,
    KeyringWarning,
    KeySetup(Key),
    KeyChoice(Key),
    KeyEntry(Key),
    OpeningKeyPage(Key),
    SavingKey(Key),
    OfferTest(Key),
    OpeningSettings(Key),
    BundlePassphrase,
    WritingBundle,
    BundleResult,
    Summary,
    Done,
}

/// The first-start wizard (`_maybe_show_first_start_onboarding`).
#[derive(Debug, Clone)]
pub struct Onboarding {
    portable: bool,
    state: State,
    imported_any: bool,
    wizard_keys: Vec<(&'static str, String)>,
}

fn dialog(title: &str, message: String, buttons: Buttons, icon: Icon) -> Step {
    Step::Dialog(Dialog {
        title: title.into(),
        message,
        buttons,
        icon,
    })
}

fn yes_no(status: bool) -> &'static str {
    if status {
        "Yes"
    } else {
        "No"
    }
}

impl Onboarding {
    pub fn new(portable: bool) -> Self {
        Self {
            portable,
            state: State::Welcome,
            imported_any: false,
            wizard_keys: Vec::new(),
        }
    }

    fn total_steps(&self) -> u32 {
        if self.portable {
            4
        } else {
            3
        }
    }

    /// The welcome dialog.
    pub fn start(&mut self, _facts: &Facts) -> Step {
        self.state = State::Welcome;
        dialog(
            "Getting started",
            format!(
                "Welcome to AccessiWeather.\n\nStep 1 of {}: Add your first location now?\n\n\
                 If you already have settings or API keys to bring over, choose Import existing.\n\n\
                 Choose Configure myself, or press Escape, to close this wizard and set things up later.",
                self.total_steps()
            ),
            Buttons::YesNoCancel("Add location", "Import existing", "Configure myself"),
            Icon::Information,
        )
    }

    pub fn advance(&mut self, response: Response, facts: &Facts) -> Step {
        use Response as R;
        let state = std::mem::replace(&mut self.state, State::Done);
        match (state, response) {
            (State::Welcome, R::Yes) => self.go(State::AddingLocation, Step::AddLocation),
            (State::Welcome, R::No) => self.ask_import_settings(),
            (State::AddingLocation, _) => self.keyring_check(facts),

            (State::AskImportSettings, R::Yes) => self.go(
                State::ChoosingSettingsFile,
                Step::ChooseFile {
                    title: "Import AccessiWeather settings",
                    wildcard: "JSON files (*.json)|*.json",
                },
            ),
            (State::AskImportSettings, R::No) => self.ask_import_keys(),
            (State::ChoosingSettingsFile, R::File(Some(path))) => {
                self.go(State::ImportingSettings, Step::ImportSettings(path))
            }
            (State::ImportingSettings, response) => {
                let step = if response == R::Success(true) {
                    self.imported_any = true;
                    dialog(
                        "Settings imported",
                        "Settings imported successfully. Any saved locations from the backup are ready to use.".into(),
                        Buttons::Ok,
                        Icon::Information,
                    )
                } else {
                    dialog(
                        "Settings import failed",
                        "Failed to import settings. The file may be invalid or corrupted.".into(),
                        Buttons::Ok,
                        Icon::Error,
                    )
                };
                self.go(State::SettingsResult, step)
            }
            (State::SettingsResult, _) => self.ask_import_keys(),

            (State::AskImportKeys, R::Yes) => self.go(
                State::ChoosingKeysFile,
                Step::ChooseFile {
                    title: "Import API keys (encrypted)",
                    wildcard: "Encrypted bundle (*.keys)|*.keys|Legacy bundle (*.awkeys)|*.awkeys",
                },
            ),
            (State::AskImportKeys, R::No) => self.after_import(facts),
            (State::ChoosingKeysFile, R::File(Some(path))) => self.go(
                State::KeysPassphrase(path),
                Step::Secret {
                    title: "Import API keys (encrypted)".into(),
                    message:
                        "Enter the passphrase used when exporting this encrypted API key bundle."
                            .into(),
                },
            ),
            (State::KeysPassphrase(path), R::Text(text)) => {
                let passphrase = crate::py_strip(&text).to_string();
                if passphrase.is_empty() {
                    return self.after_import(facts);
                }
                self.go(
                    State::ImportingKeys,
                    Step::ImportApiKeys { path, passphrase },
                )
            }
            (State::ImportingKeys, response) => {
                let step = if response == R::Success(true) {
                    self.imported_any = true;
                    dialog(
                        "API keys imported",
                        "API keys imported successfully. They are now active.".into(),
                        Buttons::Ok,
                        Icon::Information,
                    )
                } else {
                    dialog(
                        "API key import failed",
                        "Failed to import encrypted API keys. Check the passphrase and bundle file."
                            .into(),
                        Buttons::Ok,
                        Icon::Error,
                    )
                };
                self.go(State::KeysResult, step)
            }
            (State::KeysResult, _) => self.after_import(facts),

            (State::KeyringWarning, _) => self.key_step(Key::OpenRouter, facts),
            (State::KeySetup(key), R::Yes) => self.key_choice(key),
            (State::KeySetup(key), R::No) => self.after_key(key, facts),
            (State::KeyChoice(key), R::Yes) => {
                let message = self.key_message(key);
                self.go(
                    State::KeyEntry(key),
                    Step::Secret {
                        title: key.title().into(),
                        message,
                    },
                )
            }
            (State::KeyChoice(key), R::No) => {
                self.go(State::OpeningKeyPage(key), Step::OpenUrl(key.url()))
            }
            (State::OpeningKeyPage(key), _) => self.key_choice(key),
            (State::KeyEntry(key), R::Text(text)) => {
                let value = crate::py_strip(&text).to_string();
                if value.is_empty() {
                    self.after_key(key, facts)
                } else if self.portable {
                    self.wizard_keys.push((key.name(), value));
                    self.after_key(key, facts)
                } else {
                    self.go(
                        State::SavingKey(key),
                        Step::SaveApiKey {
                            name: key.name(),
                            value,
                        },
                    )
                }
            }
            (State::SavingKey(key), _) => self.go(
                State::OfferTest(key),
                dialog(
                    "Key saved",
                    format!("{} saved. Test key now in Settings > AI?", key.label()),
                    Buttons::YesNo("Test key now", "Later"),
                    Icon::Information,
                ),
            ),
            (State::OfferTest(key), R::Yes) => self.go(
                State::OpeningSettings(key),
                Step::OpenSettings { tab: Some("AI") },
            ),
            (State::OfferTest(key), _) | (State::OpeningSettings(key), _) => {
                self.after_key(key, facts)
            }

            (State::BundlePassphrase, R::Text(text)) => {
                let passphrase = crate::py_strip(&text).to_string();
                if passphrase.is_empty() {
                    return self.go(
                        State::BundleResult,
                        dialog(
                            "Keys not saved",
                            "No passphrase entered \u{2014} API keys will not be saved.".into(),
                            Buttons::Ok,
                            Icon::Warning,
                        ),
                    );
                }
                self.go(
                    State::WritingBundle,
                    Step::WriteKeyBundle {
                        keys: self.wizard_keys.clone(),
                        passphrase,
                    },
                )
            }
            (State::WritingBundle, response) => {
                let step = if response == R::Success(true) {
                    dialog(
                        "Keys saved",
                        "API keys saved to encrypted bundle. They are now active.".into(),
                        Buttons::Ok,
                        Icon::Information,
                    )
                } else {
                    dialog(
                        "Bundle write failed",
                        "Failed to save the key bundle. Keys will not persist after this session."
                            .into(),
                        Buttons::Ok,
                        Icon::Warning,
                    )
                };
                self.go(State::BundleResult, step)
            }
            (State::BundleResult, _) => self.summary(facts),
            // The summary's OK, Configure myself, Escape, a cancelled file or text prompt.
            _ => self.finish(),
        }
    }

    fn go(&mut self, state: State, step: Step) -> Step {
        self.state = state;
        step
    }

    fn finish(&mut self) -> Step {
        self.state = State::Done;
        Step::Finished
    }

    fn ask_import_settings(&mut self) -> Step {
        self.go(
            State::AskImportSettings,
            dialog(
                "Import settings",
                "Import a settings backup now? This can restore preferences and saved locations.\n\n\
                 Choose Configure myself, or press Escape, to close this wizard."
                    .into(),
                Buttons::YesNoCancel("Import settings", "Skip settings", "Configure myself"),
                Icon::Information,
            ),
        )
    }

    fn ask_import_keys(&mut self) -> Step {
        self.go(
            State::AskImportKeys,
            dialog(
                "Import API keys",
                "Import an encrypted API key bundle now?\n\n\
                 Choose Configure myself, or press Escape, to close this wizard."
                    .into(),
                Buttons::YesNoCancel("Import API keys", "Skip API keys", "Configure myself"),
                Icon::Information,
            ),
        )
    }

    /// After the import questions: done if they brought a location along,
    /// otherwise on to the key steps.
    fn after_import(&mut self, facts: &Facts) -> Step {
        if self.imported_any && facts.has_locations {
            self.summary(facts)
        } else {
            self.keyring_check(facts)
        }
    }

    fn keyring_check(&mut self, facts: &Facts) -> Step {
        if !self.portable && !facts.keyring_available {
            return self.go(
                State::KeyringWarning,
                dialog(
                    "Secure storage unavailable",
                    "Your system keyring is not available.\n\n\
                     API keys you enter cannot be stored securely on this machine. On Linux, \
                     installing a keyring backend (e.g. gnome-keyring or KWallet) is recommended.\n\n\
                     You can still enter keys now; if portable mode is enabled with an encrypted \
                     bundle they will be saved there \u{2014} otherwise they will be lost on exit."
                        .into(),
                    Buttons::Ok,
                    Icon::Warning,
                ),
            );
        }
        self.key_step(Key::OpenRouter, facts)
    }

    fn key_message(&self, key: Key) -> String {
        let (step, what) = match key {
            Key::OpenRouter => (2, "OpenRouter API key"),
            Key::PirateWeather => (3, "Pirate Weather provider key"),
        };
        format!(
            "Step {step} of {}: Enter your {what} now, or leave blank to skip.",
            self.total_steps()
        )
    }

    fn key_step(&mut self, key: Key, facts: &Facts) -> Step {
        if key.saved(facts) {
            return self.after_key(key, facts);
        }
        let message = format!(
            "{}\n\nChoose Set up now to enter or get a key, Skip this key to keep going, \
             or Configure myself to close the wizard.",
            self.key_message(key)
        );
        self.go(
            State::KeySetup(key),
            dialog(
                key.title(),
                message,
                Buttons::YesNoCancel("Set up now", "Skip this key", "Configure myself"),
                Icon::Information,
            ),
        )
    }

    fn key_choice(&mut self, key: Key) -> Step {
        let message = format!(
            "{}\n\nChoose Enter key to type it now, {}, or Configure myself to close the wizard.",
            self.key_message(key),
            key.action()
        );
        self.go(
            State::KeyChoice(key),
            dialog(
                key.title(),
                message,
                Buttons::YesNoCancel("Enter key", key.action(), "Configure myself"),
                Icon::Information,
            ),
        )
    }

    fn after_key(&mut self, key: Key, facts: &Facts) -> Step {
        match key {
            Key::OpenRouter => self.key_step(Key::PirateWeather, facts),
            Key::PirateWeather if self.portable && !self.wizard_keys.is_empty() => {
                let total = self.total_steps();
                self.go(
                    State::BundlePassphrase,
                    Step::Secret {
                        title: format!("Step {total} of {total}: Secure your API keys"),
                        message: "Enter a passphrase to encrypt your API keys into a portable bundle.\n\
                                  This bundle travels with the app so your keys work on any machine.\n\n\
                                  Leave blank to skip (keys will not be saved)."
                            .into(),
                    },
                )
            }
            Key::PirateWeather => self.summary(facts),
        }
    }

    /// `_show_onboarding_readiness_summary`.
    fn summary(&mut self, facts: &Facts) -> Step {
        let mut lines = vec![
            "Setup summary:".to_string(),
            format!("- Location configured: {}", yes_no(facts.has_locations)),
            format!("- OpenRouter key set: {}", yes_no(facts.has_openrouter_key)),
            format!(
                "- Pirate Weather provider key set: {}",
                yes_no(facts.has_pirate_weather_key)
            ),
        ];
        if self.portable {
            lines.push(format!(
                "- Portable key bundle created: {}",
                yes_no(facts.portable_keys_imported_this_session)
            ));
        }
        self.go(
            State::Summary,
            dialog(
                "Onboarding readiness",
                lines.join("\n"),
                Buttons::Ok,
                Icon::Information,
            ),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decisions() {
        assert!(should_show_onboarding(false, false, false));
        assert!(!should_show_onboarding(false, true, false));
        assert!(!should_show_onboarding(false, false, true));
        assert!(should_show_onboarding(true, true, true));
        assert!(should_show_portable_missing_keys_hint(
            true, false, false, false, false
        ));
        assert!(!should_show_portable_missing_keys_hint(
            false, false, false, false, false
        ));
        assert!(!should_show_portable_missing_keys_hint(
            true, false, false, true, false
        ));
        assert!(!should_show_portable_missing_keys_hint(
            true, false, true, false, false
        ));
    }

    #[test]
    fn escape_on_welcome_closes_the_wizard() {
        let mut w = Onboarding::new(false);
        let facts = Facts::default();
        assert!(matches!(w.start(&facts), Step::Dialog(_)));
        assert_eq!(w.advance(Response::Cancel, &facts), Step::Finished);
    }
}
