//! The startup check for a saved OpenRouter model that no longer exists
//! (`_validate_ai_model_deferred` and `_show_invalid_model_warning` in
//! `app_initialization.py`).

use aw_ai::models::{invalid_model_warning, validate_and_get_fallback};
use aw_ai::provider::{startup_model_to_validate, DEFAULT_FREE_MODEL};
use wxdragon::prelude::*;

use super::locations;
use super::main_window::{main_frame, message_box};
use crate::app::{post_to_ui, save, with_state};

const CAPTION: &str = "AI Model Not Found";
const RESET_LABEL: &str = "Reset to Default";
const OPEN_SETTINGS_LABEL: &str = "Open Settings";
const RESET_CAPTION: &str = "Model Reset";

fn reset_confirmation() -> String {
    format!("AI model has been reset to: {DEFAULT_FREE_MODEL}")
}

fn reset_failed(error: &str) -> String {
    format!("Failed to reset model: {error}\n\nPlease update it manually in Settings.")
}

/// `_validate_ai_model_deferred`: look the model up off the UI thread and
/// ask about it only when it is gone. Runs 500 ms after the initial load.
pub(crate) fn validate_ai_model_deferred() {
    let Some(state) = with_state() else { return };
    let Some(model) = startup_model_to_validate(&state.borrow().config.settings).map(String::from)
    else {
        return;
    };
    std::thread::Builder::new()
        .name("aw-model-check".into())
        .spawn(move || {
            if validate_and_get_fallback(&model).1 {
                post_to_ui(move || show_invalid_model_warning(&model));
            }
        })
        .expect("spawn model check thread");
}

/// `_show_invalid_model_warning`: reset to the free router, or open Settings.
fn show_invalid_model_warning(invalid_model: &str) {
    let (Some(frame), Some(state)) = (main_frame(), with_state()) else {
        return;
    };
    let dialog = MessageDialog::builder(&frame, &invalid_model_warning(invalid_model), CAPTION)
        .with_style(MessageDialogStyle::YesNo | MessageDialogStyle::IconWarning)
        .build();
    dialog.set_yes_no_labels(RESET_LABEL, OPEN_SETTINGS_LABEL);
    if dialog.show_modal() != ID_YES {
        locations::on_settings();
        return;
    }
    let saved = {
        let mut st = state.borrow_mut();
        st.config.settings.ai_model_preference = DEFAULT_FREE_MODEL.to_string();
        save(&st)
    };
    match saved {
        Ok(()) => {
            tracing::info!("Reset AI model to default: {DEFAULT_FREE_MODEL}");
            message_box(
                &frame,
                &reset_confirmation(),
                RESET_CAPTION,
                MessageDialogStyle::OK | MessageDialogStyle::IconInformation,
            );
        }
        Err(e) => {
            tracing::error!("Failed to reset AI model: {e}");
            message_box(
                &frame,
                &reset_failed(&e.to_string()),
                "Error",
                MessageDialogStyle::OK | MessageDialogStyle::IconError,
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::{json, Value};

    use super::*;

    #[test]
    fn invalid_model_question_matches_python() {
        let g: Value =
            serde_json::from_str(include_str!("../../../../testdata/golden/aiui/cases.json"))
                .unwrap();
        for case in g["invalid_model"].as_array().unwrap() {
            assert_eq!(case["message"], invalid_model_warning("removed/model"));
            assert_eq!(case["caption"], CAPTION);
            assert_eq!(case["yes_no"], true);
            assert_eq!(case["icon_warning"], true);
            assert_eq!(case["labels"], json!([RESET_LABEL, OPEN_SETTINGS_LABEL]));
            let yes = case["answer"] == "yes";
            assert_eq!(case["opened_settings"], !yes);
            if yes {
                assert_eq!(
                    case["confirmation"],
                    json!([reset_confirmation(), RESET_CAPTION])
                );
                assert_eq!(case["saved_model"], DEFAULT_FREE_MODEL);
            }
        }
    }
}
