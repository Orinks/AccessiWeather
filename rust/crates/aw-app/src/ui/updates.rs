//! Update checks: Help > Check for Updates (`ui/main_window_commands.py`
//! `_on_check_updates`), the automatic check (`app_lifecycle.py`
//! `_check_for_updates_on_startup`), the "Update Available" dialog
//! (`ui/dialogs/update_dialog.py`) and the download and restart
//! (`_download_and_apply_update`).

use std::cell::RefCell;
use std::mem::ManuallyDrop;
use std::path::Path;
use std::sync::Mutex;
use std::time::Duration;

use aw_services::update::{self, messages, UpdateError, UpdateInfo, UpdateService};
use aw_services::update_restart::{apply_update, can_auto_apply};
use wxdragon::prelude::*;

use super::main_window::{main_frame, message_box};
use crate::app::{post_to_ui, with_state};

/// A `wx.MessageBox` call: message, caption and style.
type Message = (String, &'static str, MessageDialogStyle);

const DIALOG_SIZE: (i32, i32) = (500, 420);
const WHATS_NEW_LABEL: &str = "What's new:";
const DOWNLOAD_LABEL: &str = "&Download Update";
const CANCEL_LABEL: &str = "&Cancel";

thread_local! {
    static PROGRESS_DIALOG: RefCell<Option<ProgressDialog>> = const { RefCell::new(None) };
}

/// The newest progress not yet shown, and whether a UI update is queued or
/// running. Coalescing keeps at most one update in flight, so the finished
/// download is never handled inside the progress dialog's own `Update`.
struct Progress {
    latest: Option<(u32, String)>,
    queued: bool,
}

static PROGRESS: Mutex<Progress> = Mutex::new(Progress {
    latest: None,
    queued: false,
});

fn info() -> MessageDialogStyle {
    MessageDialogStyle::OK | MessageDialogStyle::IconInformation
}

fn error() -> MessageDialogStyle {
    MessageDialogStyle::OK | MessageDialogStyle::IconError
}

fn show((message, caption, style): Message) -> i32 {
    match main_frame() {
        Some(frame) => message_box(&frame, &message, caption, style),
        None => ID_CANCEL,
    }
}

fn nightly_date() -> Option<String> {
    crate::lifecycle::build_tag().and_then(|tag| update::parse_nightly_date(&tag))
}

/// Check GitHub for a newer build on the configured channel. `manual` is
/// Help > Check for Updates: every outcome gets a message box. Otherwise it
/// is the startup/periodic check: silent unless an update is available, and
/// skipped when running from source, when automatic checks are off, or on a
/// nightly channel without a build tag.
pub(crate) fn check_for_updates(manual: bool) {
    let Some(state) = with_state() else { return };
    let settings = state.borrow().config.settings.clone();
    let from_source = aw_services::is_running_from_source();
    if manual {
        if from_source {
            show(running_from_source_message());
            return;
        }
        begin_busy_cursor(None);
    } else {
        if !update::should_run_automatic_check(
            from_source,
            &settings,
            crate::lifecycle::build_tag().as_deref(),
        ) {
            return;
        }
        tracing::info!(
            "Auto-update check starting (channel={})",
            settings.update_channel
        );
    }
    let channel = settings.update_channel;
    std::thread::Builder::new()
        .name("aw-update-check".into())
        .spawn(move || {
            let nightly = nightly_date();
            let result = UpdateService::new().and_then(|service| {
                service.check_for_updates(
                    &crate::lifecycle::app_version(),
                    nightly.as_deref(),
                    &channel,
                )
            });
            post_to_ui(move || finish_check(manual, result, nightly.as_deref(), &channel));
        })
        .expect("spawn update check thread");
}

fn finish_check(
    manual: bool,
    result: Result<Option<UpdateInfo>, UpdateError>,
    nightly: Option<&str>,
    channel: &str,
) {
    if manual {
        end_busy_cursor();
    }
    match result {
        Ok(Some(info)) => {
            if !manual {
                tracing::info!(
                    "Update available: {} ({})",
                    info.version,
                    messages::channel_label(info.is_nightly)
                );
            }
            on_update_available(info);
        }
        Ok(None) if manual => {
            show(no_update_message(
                nightly,
                channel,
                &crate::lifecycle::app_version(),
            ));
        }
        Ok(None) => tracing::info!("Auto-update check: no updates available"),
        Err(e) if manual => {
            show(check_failed_message(&e.to_string()));
        }
        Err(e) => tracing::warn!("Startup update check failed: {e}"),
    }
}

fn running_from_source_message() -> Message {
    (
        messages::RUNNING_FROM_SOURCE.into(),
        messages::RUNNING_FROM_SOURCE_TITLE,
        info(),
    )
}

fn no_update_message(nightly: Option<&str>, channel: &str, version: &str) -> Message {
    (
        messages::no_update(nightly, channel, update::display_version(version, nightly)),
        messages::NO_UPDATES_TITLE,
        info(),
    )
}

fn check_failed_message(error_text: &str) -> Message {
    (
        messages::check_failed(error_text),
        messages::CHECK_FAILED_TITLE,
        error(),
    )
}

/// Show the "Update Available" dialog for `info`; Download Update starts the
/// download. The lifecycle's own checks can call this directly.
pub(crate) fn on_update_available(info: UpdateInfo) {
    let Some(frame) = main_frame() else { return };
    let nightly = nightly_date();
    let version = crate::lifecycle::app_version();
    offer_update(
        &frame,
        update::display_version(&version, nightly.as_deref()),
        info,
    );
}

/// The "Update Available" dialog over `parent` (Settings > Updates passes
/// itself), then `app._download_and_apply_update` on Download Update.
pub(crate) fn offer_update(parent: &dyn WxWidget, current_version: &str, info: UpdateInfo) {
    let label = messages::channel_label(info.is_nightly);
    if show_update_dialog(
        parent,
        current_version,
        &info.version,
        label,
        &info.release_notes,
    ) {
        download_and_apply_update(info);
    }
}

fn update_dialog_title(channel_label: &str) -> String {
    format!("{channel_label} Update Available")
}

fn update_dialog_header(current_version: &str, new_version: &str, channel_label: &str) -> String {
    format!(
        "A new {channel_label} update is available!\n\
         Current: {current_version}  \u{2192}  Latest: {new_version}"
    )
}

/// `UpdateAvailableDialog`: true when the user chose Download Update.
fn show_update_dialog(
    parent: &dyn WxWidget,
    current_version: &str,
    new_version: &str,
    channel_label: &str,
    release_notes: &str,
) -> bool {
    let dialog = Dialog::builder(parent, &update_dialog_title(channel_label))
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();
    let header = StaticText::builder(&dialog)
        .with_label(&update_dialog_header(
            current_version,
            new_version,
            channel_label,
        ))
        .build();
    sizer.add(&header, 0, SizerFlag::All | SizerFlag::Expand, 10);
    let changelog_label = StaticText::builder(&dialog)
        .with_label(WHATS_NEW_LABEL)
        .build();
    sizer.add(&changelog_label, 0, SizerFlag::Left | SizerFlag::Right, 10);
    let changelog = TextCtrl::builder(&dialog)
        .with_value(&update::format_release_notes(release_notes))
        .with_style(
            TextCtrlStyle::MultiLine
                | TextCtrlStyle::ReadOnly
                | TextCtrlStyle::Rich2
                | TextCtrlStyle::DontWrap,
        )
        .build();
    sizer.add(&changelog, 1, SizerFlag::All | SizerFlag::Expand, 10);

    let buttons = StdDialogButtonSizerBuilder::new().build();
    let download = Button::builder(&dialog)
        .with_id(ID_OK)
        .with_label(DOWNLOAD_LABEL)
        .build();
    download.set_default();
    let cancel = Button::builder(&dialog)
        .with_id(ID_CANCEL)
        .with_label(CANCEL_LABEL)
        .build();
    buttons.add_button(&download);
    buttons.add_button(&cancel);
    buttons.realize();
    sizer.add_sizer(&buttons, 0, SizerFlag::All | SizerFlag::Expand, 10);
    dialog.set_sizer(sizer, true);

    dialog.set_size(Size::new(DIALOG_SIZE.0, DIALOG_SIZE.1));
    dialog.center();
    // Screen readers start reading the notes from the top.
    changelog.set_focus();
    changelog.set_insertion_point(0);
    let result = dialog.show_modal();
    dialog.destroy();
    result == ID_OK
}

/// Run `f` on the open progress dialog without holding a borrow across wx
/// calls (`Update` dispatches events). The copy must never drop: dropping
/// any `ProgressDialog` destroys it.
fn with_progress_dialog(f: impl FnOnce(&ProgressDialog)) {
    let dialog =
        PROGRESS_DIALOG.with(|p| p.borrow().as_ref().map(|d| ManuallyDrop::new(d.clone())));
    if let Some(dialog) = dialog {
        f(&dialog);
    }
}

fn close_progress_dialog() {
    let dialog = PROGRESS_DIALOG.with(|p| p.borrow_mut().take());
    drop(dialog);
}

fn show_latest_progress() {
    let latest = PROGRESS
        .lock()
        .unwrap_or_else(|e| e.into_inner())
        .latest
        .take();
    if let Some((percent, text)) = latest {
        with_progress_dialog(|d| {
            d.update(percent as i32, Some(&text));
        });
    }
    let mut progress = PROGRESS.lock().unwrap_or_else(|e| e.into_inner());
    if progress.latest.is_some() {
        post_to_ui(show_latest_progress);
    } else {
        progress.queued = false;
    }
}

fn report_progress(downloaded: u64, total: u64) {
    let Some(update) = messages::download_progress(downloaded, total) else {
        return;
    };
    let mut progress = PROGRESS.lock().unwrap_or_else(|e| e.into_inner());
    progress.latest = Some(update);
    if !progress.queued {
        progress.queued = true;
        post_to_ui(show_latest_progress);
    }
}

fn wait_for_progress_updates() {
    while PROGRESS.lock().unwrap_or_else(|e| e.into_inner()).queued {
        std::thread::sleep(Duration::from_millis(20));
    }
}

/// `_download_and_apply_update`: download with a progress dialog, then
/// restart into the update or say where the file was saved.
fn download_and_apply_update(info: UpdateInfo) {
    let Some(frame) = main_frame() else { return };
    let dialog = ProgressDialog::builder(
        &frame,
        messages::DOWNLOADING_TITLE,
        &messages::downloading(&info.artifact_name),
        100,
    )
    .with_style(
        ProgressDialogStyle::AppModal
            | ProgressDialogStyle::AutoHide
            | ProgressDialogStyle::CanAbort,
    )
    .build();
    PROGRESS_DIALOG.with(|p| *p.borrow_mut() = Some(dialog));
    std::thread::Builder::new()
        .name("aw-update-download".into())
        .spawn(move || {
            let result = UpdateService::new().and_then(|service| {
                service.download_update(&info, &std::env::temp_dir(), report_progress)
            });
            wait_for_progress_updates();
            post_to_ui(move || {
                close_progress_dialog();
                match result {
                    Ok(path) => confirm_apply(&path),
                    Err(e) => {
                        tracing::error!("Error downloading update: {e}");
                        show(download_error_message(&e.to_string()));
                    }
                }
            });
        })
        .expect("spawn update download thread");
}

fn download_error_message(error_text: &str) -> Message {
    (
        messages::download_failed(error_text),
        messages::DOWNLOAD_ERROR_TITLE,
        error(),
    )
}

fn manual_update_message(path: &Path) -> Message {
    (
        messages::manual_update(path),
        messages::MANUAL_UPDATE_TITLE,
        info(),
    )
}

fn apply_message() -> Message {
    (
        messages::APPLY.into(),
        messages::APPLY_TITLE,
        MessageDialogStyle::YesNo | MessageDialogStyle::IconQuestion,
    )
}

fn confirm_apply(path: &Path) {
    if !can_auto_apply(path) {
        show(manual_update_message(path));
        return;
    }
    if show(apply_message()) != ID_YES {
        return;
    }
    // Close the window first so nothing keeps the install's files open.
    if let Some(frame) = main_frame() {
        frame.close(true);
    }
    if let Err(e) = apply_update(path) {
        tracing::error!("Failed to apply update: {e}");
    }
}

#[cfg(test)]
mod tests {
    //! Golden parity with the Python update dialog and flows, generated by
    //! `rust/tools/golden/miscui.py`.

    use serde_json::{json, Value};

    use super::*;
    use crate::ui::golden_miscui::{golden, message_json, wx};

    #[test]
    fn update_dialog_matches_python() {
        let g = golden();
        for case in g["update_dialogs"].as_array().unwrap() {
            let s = |k: &str| case[k].as_str().unwrap();
            let label = s("channel_label");
            assert_eq!(update_dialog_title(label), s("title"));
            assert_eq!(case["resizable"], true);
            assert_eq!(case["size"], json!([DIALOG_SIZE.0, DIALOG_SIZE.1]));
            let text = |value: String| {
                json!({"kind": "text", "name": "text", "value": value, "hint": "",
                    "multiline": true, "readonly": true, "rich2": true,
                    "dont_wrap": true, "no_vscroll": false})
            };
            let button = |id: i32, label: &str| json!({"kind": "button", "id": id, "label": label, "name": "button"});
            assert_eq!(
                case["controls"],
                json!([
                    {"kind": "label", "label": update_dialog_header(s("current_version"), s("new_version"), label)},
                    {"kind": "label", "label": WHATS_NEW_LABEL},
                    text(update::format_release_notes(s("release_notes"))),
                    button(ID_OK, DOWNLOAD_LABEL),
                    button(ID_CANCEL, CANCEL_LABEL),
                ])
            );
            assert_eq!(case["default"], DOWNLOAD_LABEL);
            assert_eq!(case["focus"], true);
            assert_eq!(case["insertion_point"], 0);
        }
    }

    #[test]
    fn check_flow_matches_python() {
        let g = golden();
        let wx = wx(&g);
        assert_eq!(ID_OK, wx["ID_OK"]);
        assert_eq!(ID_CANCEL, wx["ID_CANCEL"]);
        assert_eq!(ID_YES, wx["ID_YES"]);
        for case in g["check_updates"].as_array().unwrap() {
            let events = case["events"].as_array().unwrap();
            if case["name"] == "source" {
                assert_eq!(events[0], message_json(&running_from_source_message()));
                continue;
            }
            assert_eq!(events[0], json!(["begin_busy_cursor"]));
            assert_eq!(events[1], json!(["end_busy_cursor"]));
            let version = case["version"].as_str().unwrap();
            let channel = case["channel"].as_str().unwrap();
            let nightly = case["build_tag"]
                .as_str()
                .and_then(update::parse_nightly_date);
            let args = &case["check_args"][0];
            assert_eq!(args["current_nightly_date"], json!(nightly));
            assert_eq!(args["channel"], channel);
            let expected = if let Some(error_text) = case["error"].as_str() {
                message_json(&check_failed_message(error_text))
            } else if let Some(update) = case["update"].as_array() {
                let current = update::display_version(version, nightly.as_deref());
                json!(["update_dialog", {
                    "current_version": current,
                    "new_version": update[0],
                    "channel_label": messages::channel_label(update[1].as_bool().unwrap()),
                    "release_notes": events[2][1]["release_notes"],
                }])
            } else {
                message_json(&no_update_message(nightly.as_deref(), channel, version))
            };
            assert_eq!(events[2], expected, "{}", case["name"]);
        }
    }

    #[test]
    fn download_flow_matches_python() {
        let g = golden();
        let wx = wx(&g);
        let style = ProgressDialogStyle::AppModal
            | ProgressDialogStyle::AutoHide
            | ProgressDialogStyle::CanAbort;
        let expected_style = wx["PD_APP_MODAL"] | wx["PD_AUTO_HIDE"] | wx["PD_CAN_ABORT"];
        assert_eq!(style.bits() as i32, expected_style);
        let path = Path::new(r"C:\Users\Test\AppData\Local\Temp\accessiweather-windows-x86_64.zip");
        for case in g["downloads"].as_array().unwrap() {
            let mut expected: Vec<Value> = vec![json!([
                "progress_dialog",
                messages::DOWNLOADING_TITLE,
                messages::downloading("accessiweather-windows-x86_64.zip"),
                100,
                expected_style
            ])];
            for pair in case["progress_pairs"].as_array().unwrap() {
                let (d, t) = (pair[0].as_u64().unwrap(), pair[1].as_u64().unwrap());
                if let Some((percent, text)) = messages::download_progress(d, t) {
                    expected.push(json!(["progress_update", percent, text]));
                }
            }
            expected.push(json!(["progress_destroy"]));
            match case["name"].as_str().unwrap() {
                "manual_install" => expected.push(message_json(&manual_update_message(path))),
                "download_error" => expected.push(message_json(&download_error_message(
                    case["error"].as_str().unwrap(),
                ))),
                name => {
                    expected.push(message_json(&apply_message()));
                    if name == "apply_accepted" {
                        expected.push(json!(["apply_update", path.display().to_string()]));
                    }
                }
            }
            assert_eq!(case["events"], Value::from(expected), "{}", case["name"]);
        }
    }
}
