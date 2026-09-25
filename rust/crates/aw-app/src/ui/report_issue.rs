//! Help > Report Issue (`ui/dialogs/report_issue_dialog.py`): a pre-filled
//! GitHub issue opened in the browser. The URL and system info come from
//! `aw_services::report_issue`.

use aw_services::report_issue::{self, ISSUE_TYPES, TITLE_REQUIRED_TITLE};
use wxdragon::prelude::*;

use super::main_window::message_box;

const TITLE: &str = "Report Issue";
const SIZE: (i32, i32) = (500, 400);
const TYPE_LABEL: &str = "Issue Type:";
const TITLE_LABEL: &str = "Title:";
const TITLE_HINT: &str = "Brief summary of the issue";
const DESCRIPTION_LABEL: &str = "Description:";
const INFO_LABEL: &str = "System info (auto-collected):";
const INFO_MIN_HEIGHT: i32 = 60;
const SUBMIT_LABEL: &str = "Open in Browser";
const CANCEL_LABEL: &str = "Cancel";

/// `wx.TextCtrl.SetHint` on a single-line control, which wxMSW implements
/// as the edit control's cue banner (shown even while focused).
#[cfg(windows)]
fn set_hint(ctrl: &TextCtrl, hint: &str) {
    #[link(name = "user32")]
    extern "system" {
        fn SendMessageW(
            hwnd: *mut std::ffi::c_void,
            msg: u32,
            wparam: usize,
            lparam: isize,
        ) -> isize;
    }
    const EM_SETCUEBANNER: u32 = 0x1501;
    let wide: Vec<u16> = hint.encode_utf16().chain(Some(0)).collect();
    // SAFETY: a live edit control handle and a NUL-terminated UTF-16 string
    // that outlives the synchronous call.
    unsafe {
        SendMessageW(
            ctrl.get_handle(),
            EM_SETCUEBANNER,
            1,
            wide.as_ptr() as isize,
        );
    }
}

#[cfg(not(windows))]
fn set_hint(_ctrl: &TextCtrl, _hint: &str) {}

/// Show the dialog modally over `parent`.
pub(crate) fn show_report_issue_dialog(parent: &Frame) {
    let dialog = Dialog::builder(parent, TITLE)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();

    let type_label = StaticText::builder(&dialog).with_label(TYPE_LABEL).build();
    let type_choice = Choice::builder(&dialog)
        .with_choices(ISSUE_TYPES.iter().map(|s| s.to_string()).collect())
        .build();
    type_choice.set_selection(0);

    let title_label = StaticText::builder(&dialog).with_label(TITLE_LABEL).build();
    let title_input = TextCtrl::builder(&dialog).build();
    set_hint(&title_input, TITLE_HINT);

    // Python also sets a hint on the description; wx draws a multi-line
    // hint as grey text only while the empty field is unfocused, and
    // wxDragon does not expose that.
    let desc_label = StaticText::builder(&dialog)
        .with_label(DESCRIPTION_LABEL)
        .build();
    let desc_input = TextCtrl::builder(&dialog)
        .with_style(TextCtrlStyle::MultiLine)
        .build();

    let info_label = StaticText::builder(&dialog).with_label(INFO_LABEL).build();
    let info_text = TextCtrl::builder(&dialog)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly)
        .build();
    info_text.set_value(&report_issue::system_info());

    let submit = Button::builder(&dialog)
        .with_id(ID_OK)
        .with_label(SUBMIT_LABEL)
        .build();
    let cancel = Button::builder(&dialog)
        .with_id(ID_CANCEL)
        .with_label(CANCEL_LABEL)
        .build();

    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let type_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    type_sizer.add(
        &type_label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        5,
    );
    type_sizer.add(&type_choice, 1, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&type_sizer, 0, SizerFlag::Expand | SizerFlag::All, 10);
    let field = SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom;
    main_sizer.add(&title_label, 0, SizerFlag::Left | SizerFlag::Right, 10);
    main_sizer.add(&title_input, 0, field, 10);
    main_sizer.add(&desc_label, 0, SizerFlag::Left | SizerFlag::Right, 10);
    main_sizer.add(&desc_input, 1, field, 10);
    main_sizer.add(&info_label, 0, SizerFlag::Left | SizerFlag::Right, 10);
    main_sizer.add(&info_text, 0, field, 10);
    info_text.set_min_size(Size::new(-1, INFO_MIN_HEIGHT));
    let buttons = StdDialogButtonSizerBuilder::new().build();
    buttons.add_button(&submit);
    buttons.add_button(&cancel);
    buttons.realize();
    main_sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 10);
    dialog.set_sizer(main_sizer, true);

    submit.on_click(move |e| {
        // Handled here: the default OK handling would close the dialog.
        e.event.skip(false);
        let url = report_issue::build_issue_url(
            type_choice.get_selection().unwrap_or(0) as usize,
            &title_input.get_value(),
            &desc_input.get_value(),
            &info_text.get_value(),
        );
        match url {
            Ok(url) => {
                aw_services::open_in_shell(url);
                dialog.end_modal(ID_OK);
            }
            Err(message) => {
                message_box(
                    &dialog,
                    message,
                    TITLE_REQUIRED_TITLE,
                    MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
                );
                title_input.set_focus();
            }
        }
    });
    cancel.on_click(move |e| {
        e.event.skip(false);
        dialog.end_modal(ID_CANCEL);
    });
    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            dialog.end_modal(ID_CANCEL);
        } else {
            e.skip(true);
        }
    });

    dialog.set_size(Size::new(SIZE.0, SIZE.1));
    dialog.center();
    dialog.show_modal();
    dialog.destroy();
}

#[cfg(test)]
mod tests {
    //! Golden parity with the Python dialog (`rust/tools/golden/miscui.py`).

    use serde_json::json;

    use aw_services::report_issue::TITLE_REQUIRED;

    use super::*;
    use crate::ui::golden_miscui::golden;

    #[test]
    fn report_issue_dialog_matches_python() {
        let g = &golden()["report_issue"];
        assert_eq!(g["title"], TITLE);
        assert_eq!(g["resizable"], true);
        assert_eq!(g["size"], json!([SIZE.0, SIZE.1]));
        let text = |hint: &str, multiline: bool, readonly: bool, value: Option<&str>| {
            json!({"kind": "text", "name": "text", "value": value, "hint": hint,
                "multiline": multiline, "readonly": readonly, "rich2": false,
                "dont_wrap": false, "no_vscroll": false})
        };
        let python_description_hint =
            "Describe the issue or feature request.\nFor bugs: What happened? What did you expect?";
        assert_eq!(
            g["controls"],
            json!([
                {"kind": "label", "label": TYPE_LABEL},
                {"kind": "choice", "name": "choice", "items": ISSUE_TYPES, "selection": 0},
                {"kind": "label", "label": TITLE_LABEL},
                text(TITLE_HINT, false, false, Some("")),
                {"kind": "label", "label": DESCRIPTION_LABEL},
                text(python_description_hint, true, false, Some("")),
                {"kind": "label", "label": INFO_LABEL},
                text("", true, true, None),
                {"kind": "button", "id": ID_OK, "label": SUBMIT_LABEL, "name": "button"},
                {"kind": "button", "id": ID_CANCEL, "label": CANCEL_LABEL, "name": "button"},
            ])
        );
        assert_eq!(g["info_min_height"], INFO_MIN_HEIGHT);
        assert_eq!(g["default"], json!(null));
        // The third line names the edition instead of the Python version.
        assert_eq!(
            g["system_info_lines"],
            json!(["- App Version", "- OS", "- Python"])
        );
        let info = report_issue::system_info();
        let lines: Vec<&str> = info.lines().map(|l| l.split(':').next().unwrap()).collect();
        assert_eq!(lines, ["- App Version", "- OS", "- Edition"]);
        assert_eq!(
            g["empty_title_events"],
            json!([[
                "message_box",
                TITLE_REQUIRED,
                TITLE_REQUIRED_TITLE,
                (MessageDialogStyle::OK | MessageDialogStyle::IconWarning).bits()
            ]])
        );
    }
}
