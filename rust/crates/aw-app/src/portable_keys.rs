//! Portable mode API keys: the encrypted `api-keys.keys` bundle, imported
//! silently with the passphrase cached in the keyring or after a prompt,
//! as `AccessiWeatherApp._maybe_auto_import_keys_file` does.

use std::sync::atomic::{AtomicBool, Ordering};

use aw_core::settings::AppSettings;
use aw_store::secrets::{self, PORTABLE_PASSPHRASE_KEY};
use aw_store::Paths;
use wxdragon::prelude::*;

use crate::app::Shared;

/// `_portable_keys_imported_this_session`.
static IMPORTED_THIS_SESSION: AtomicBool = AtomicBool::new(false);

pub(crate) fn keys_imported_this_session() -> bool {
    IMPORTED_THIS_SESSION.load(Ordering::SeqCst)
}

pub(crate) fn set_keys_imported_this_session() {
    IMPORTED_THIS_SESSION.store(true, Ordering::SeqCst);
}

/// Try the cached passphrase. Returns true when a bundle exists but still
/// needs a passphrase from the user.
pub(crate) fn import_silently(paths: &Paths, settings: &mut AppSettings) -> bool {
    let Some(bundle) = secrets::find_bundle(&paths.config_dir) else {
        return false;
    };
    let cached = secrets::get_password(PORTABLE_PASSPHRASE_KEY)
        .unwrap_or_default()
        .trim()
        .to_string();
    if cached.is_empty() {
        return true;
    }
    match import(paths, &bundle, &cached, settings) {
        Ok(()) => {
            set_keys_imported_this_session();
            tracing::info!("Portable API keys auto-imported silently.");
            false
        }
        Err(e) => {
            tracing::warn!("Silent auto-import failed: {e}");
            secrets::delete_password(PORTABLE_PASSPHRASE_KEY);
            true
        }
    }
}

fn import(
    paths: &Paths,
    bundle: &std::path::Path,
    passphrase: &str,
    settings: &mut AppSettings,
) -> Result<(), secrets::SecretsError> {
    let keys = secrets::read_bundle(bundle, passphrase)?;
    secrets::apply(settings, &keys);
    // Keep the canonical file present for the next machine or clean keyring.
    let dest = paths.config_dir.join(secrets::BUNDLE_FILE_NAMES[0]);
    if let Err(e) = secrets::write_bundle(&dest, &secrets::collect(settings), passphrase) {
        tracing::warn!("Failed to write api-keys.keys after import: {e}");
    }
    Ok(())
}

/// Ask for the bundle passphrase until it works or the user gives up.
/// Returns true when keys were imported.
pub(crate) fn prompt(parent: &Frame, state: &Shared) -> bool {
    let paths = state.borrow().paths.clone();
    let Some(bundle) = secrets::find_bundle(&paths.config_dir) else {
        return false;
    };
    loop {
        let dlg = TextEntryDialog::builder(
            parent,
            "An encrypted API key bundle was found. Enter your passphrase to import your keys.",
            "Import API keys",
        )
        .with_style(
            TextEntryDialogStyle::Ok
                | TextEntryDialogStyle::Cancel
                | TextEntryDialogStyle::Password,
        )
        .build();
        let ok = dlg.show_modal() == ID_OK;
        let passphrase = dlg.get_value().unwrap_or_default().trim().to_string();
        dlg.destroy();
        if !ok || passphrase.is_empty() {
            return false;
        }
        let imported = import(
            &paths,
            &bundle,
            &passphrase,
            &mut state.borrow_mut().config.settings,
        );
        match imported {
            Ok(()) => {
                set_keys_imported_this_session();
                secrets::set_password(PORTABLE_PASSPHRASE_KEY, &passphrase);
                let done = MessageDialog::builder(
                    parent,
                    "API keys imported successfully. They are now active.",
                    "Keys imported",
                )
                .with_style(MessageDialogStyle::OK | MessageDialogStyle::IconInformation)
                .build();
                done.show_modal();
                done.destroy();
                return true;
            }
            Err(e) => tracing::warn!("Auto-import of API keys failed: {e}"),
        }
        let retry = MessageDialog::builder(
            parent,
            "The passphrase was incorrect or the key bundle could not be read.\n\n\
             Would you like to try again?",
            "Import failed",
        )
        .with_style(MessageDialogStyle::YesNo | MessageDialogStyle::IconWarning)
        .build();
        retry.set_yes_no_labels("Try again", "Skip");
        let again = retry.show_modal() == ID_YES;
        retry.destroy();
        if !again {
            return false;
        }
    }
}
