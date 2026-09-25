//! Modeless progress dialog for pack downloads and sharing, ported from
//! `ui/dialogs/progress_dialog.py`.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use wxdragon::prelude::*;

use super::main_window::keep_timer;
use super::soundpack_manager::{bold, label};
use crate::app::post_to_ui;

/// `ProgressDialog`. The widgets are thread-safe handles, so a worker thread
/// keeps a clone and posts its updates to the UI thread, exactly like the
/// Python `wx.CallAfter` updates.
#[derive(Clone)]
pub(super) struct ProgressDialog {
    pub dialog: Dialog,
    status_label: StaticText,
    gauge: Gauge,
    detail_label: StaticText,
    cancel_btn: Button,
    cancelled: Arc<AtomicBool>,
}

impl ProgressDialog {
    /// Build (not yet shown) on the UI thread; show with `dialog.show(true)`.
    pub fn new(parent: &dyn WxWidget, title: &str, message: &str) -> Self {
        let dialog = Dialog::builder(parent, title)
            .with_style(DialogStyle::DefaultDialogStyle)
            .with_size(450, 180)
            .build();
        let panel = Panel::builder(&dialog).build();
        let sizer = BoxSizer::builder(Orientation::Vertical).build();

        let status_label = label(&panel, message);
        bold(&status_label, None);
        sizer.add(&status_label, 0, SizerFlag::All | SizerFlag::Expand, 10);

        let gauge = Gauge::builder(&panel)
            .with_range(100)
            .with_size(Size::new(-1, 25))
            .build();
        sizer.add(
            &gauge,
            0,
            SizerFlag::Left | SizerFlag::Right | SizerFlag::Expand,
            10,
        );

        let detail_label = label(&panel, "Initializing...");
        sizer.add(&detail_label, 0, SizerFlag::All | SizerFlag::Expand, 10);

        let btn_sizer = BoxSizer::builder(Orientation::Horizontal).build();
        btn_sizer.add_stretch_spacer(1);
        let cancel_btn = Button::builder(&panel)
            .with_id(ID_CANCEL)
            .with_label("Cancel")
            .build();
        btn_sizer.add(&cancel_btn, 0, SizerFlag::empty(), 0);
        btn_sizer.add_stretch_spacer(1);
        sizer.add_sizer(&btn_sizer, 0, SizerFlag::Expand | SizerFlag::All, 10);
        panel.set_sizer(sizer, true);
        let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
        dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
        dialog.set_sizer(dialog_sizer, true);

        let progress = Self {
            dialog,
            status_label,
            gauge,
            detail_label,
            cancel_btn,
            cancelled: Arc::new(AtomicBool::new(false)),
        };
        let p = progress.clone();
        cancel_btn.on_click(move |_| p.on_cancel());
        let p = progress.clone();
        dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
            if e.get_key_code() == Some(WXK_ESCAPE) {
                p.on_cancel();
            } else {
                e.skip(true);
            }
        });
        dialog.centre();
        progress
    }

    pub fn is_cancelled(&self) -> bool {
        self.cancelled.load(Ordering::SeqCst)
    }

    /// Cancel and Escape. After an error the button reads "Close" but still
    /// lands here, as in Python.
    fn on_cancel(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
        self.status_label.set_label("Cancelling...");
        self.cancel_btn.enable(false);
    }

    /// Any thread. Returns false once cancelled.
    pub fn update_progress(&self, percent: f64, status: &str, detail: &str) -> bool {
        if self.is_cancelled() {
            return false;
        }
        let (gauge, status_label, detail_label) =
            (self.gauge, self.status_label, self.detail_label);
        let (status, detail) = (status.to_string(), detail.to_string());
        post_to_ui(move || {
            gauge.set_value(percent.clamp(0.0, 100.0) as i32);
            if !status.is_empty() {
                status_label.set_label(&status);
            }
            if !detail.is_empty() {
                detail_label.set_label(&detail);
            }
        });
        true
    }

    /// Any thread.
    pub fn set_status(&self, status: &str, detail: &str) {
        let (status_label, detail_label) = (self.status_label, self.detail_label);
        let (status, detail) = (status.to_string(), detail.to_string());
        post_to_ui(move || {
            status_label.set_label(&status);
            if !detail.is_empty() {
                detail_label.set_label(&detail);
            }
        });
    }

    /// UI thread: show the error and turn Cancel into Close.
    pub fn complete_error(&self, message: &str) {
        self.status_label.set_label("Error");
        self.detail_label.set_label(message);
        self.cancel_btn.set_label("Close");
        self.cancel_btn.enable(true);
    }

    pub fn destroy(&self) {
        self.dialog.destroy();
    }

    /// `wx.CallLater(ms, progress.Destroy)`.
    pub fn destroy_later(&self, ms: i32) {
        let dialog = self.dialog;
        keep_timer(ms, move || dialog.destroy());
    }
}
