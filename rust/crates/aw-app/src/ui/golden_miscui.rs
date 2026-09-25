//! Shared access to the Help/Debug menu golden data generated from the
//! Python dialogs by `rust/tools/golden/miscui.py`.

use std::collections::HashMap;

use serde_json::{json, Value};
use wxdragon::prelude::MessageDialogStyle;

pub(crate) fn golden() -> Value {
    serde_json::from_str(include_str!(
        "../../../../testdata/golden/miscui/cases.json"
    ))
    .unwrap()
}

/// The wx constants Python used, by name.
pub(crate) fn wx(golden: &Value) -> HashMap<String, i32> {
    serde_json::from_value(golden["wx"].clone()).unwrap()
}

/// A recorded `wx.MessageBox(message, caption, style)` call.
pub(crate) fn message_json(
    (message, caption, style): &(String, &'static str, MessageDialogStyle),
) -> Value {
    json!(["message_box", message, caption, style.bits()])
}
