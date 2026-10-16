//! Browse Community Sound Packs, ported from
//! `ui/dialogs/community_packs_dialog.py`.

use std::cell::RefCell;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::Arc;

use aw_audio::community::{
    filter_packs, progress_detail, CommunityError, CommunityPack, CommunitySoundPackService,
};
use aw_audio::installer::install_from_zip;
use wxdragon::prelude::*;

use super::location_dialog::set_hint;
use super::progress_dialog::ProgressDialog;
use super::soundpack_manager::{bold, label, show_info};
use crate::app::post_to_ui;

struct CommunityDialog {
    dialog: Dialog,
    soundpacks_dir: PathBuf,
    on_installed: Box<dyn Fn(&str)>,
    service: Option<Arc<CommunitySoundPackService>>,
    packs: RefCell<Vec<CommunityPack>>,
    /// Client data of the list: `_pack_key` for packs, `None` for the
    /// "Loading..." / "No packs found" / "Failed to load packs" rows.
    list_keys: RefCell<Vec<Option<String>>>,
    selected_key: RefCell<Option<String>>,
    search_input: TextCtrl,
    refresh_btn: Button,
    pack_listbox: ListBox,
    name_label: StaticText,
    author_label: StaticText,
    version_label: StaticText,
    size_label: StaticText,
    description_text: TextCtrl,
    status_label: StaticText,
    install_btn: Button,
}

thread_local! {
    static OPEN_DIALOG: RefCell<Option<Rc<CommunityDialog>>> = const { RefCell::new(None) };
}

/// The open browser, if `dialog` is it: results for a closed one are dropped.
fn open_dialog(dialog: Dialog) -> Option<Rc<CommunityDialog>> {
    OPEN_DIALOG
        .with(|d| d.borrow().clone())
        .filter(|d| dialog.is_valid() && d.dialog.window_handle() == dialog.window_handle())
}

/// `show_community_packs_dialog`. `on_installed(pack_name)` runs after a
/// successful install.
pub(super) fn show_community_packs_dialog(
    parent: &dyn WxWidget,
    soundpacks_dir: &Path,
    on_installed: impl Fn(&str) + 'static,
) {
    let service = CommunitySoundPackService::new()
        .inspect_err(|e| tracing::error!("Failed to initialize community service: {e}"))
        .ok()
        .map(Arc::new);

    let dialog = Dialog::builder(parent, "Browse Community Sound Packs")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(850, 550)
        .build();
    let panel = Panel::builder(&dialog).build();
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();

    let header = BoxSizer::builder(Orientation::Horizontal).build();
    header.add(
        &label(&panel, "Filter packs:"),
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        5,
    );
    let search_input = TextCtrl::builder(&panel)
        .with_size(Size::new(250, -1))
        .build();
    set_hint(&search_input, "Search by name or author");
    header.add(&search_input, 1, SizerFlag::Right, 10);
    let refresh_btn = Button::builder(&panel).with_label("Refresh").build();
    header.add(&refresh_btn, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&header, 0, SizerFlag::Expand | SizerFlag::All, 10);

    let content = BoxSizer::builder(Orientation::Horizontal).build();
    let left = BoxSizer::builder(Orientation::Vertical).build();
    let packs_label = label(&panel, "Available Packs:");
    bold(&packs_label, None);
    left.add(&packs_label, 0, SizerFlag::Bottom, 5);
    let pack_listbox = ListBox::builder(&panel).build();
    left.add(&pack_listbox, 1, SizerFlag::Expand, 0);
    content.add_sizer(&left, 1, SizerFlag::Expand | SizerFlag::Right, 10);

    let right = BoxSizer::builder(Orientation::Vertical).build();
    let details_box = StaticBox::builder(&panel)
        .with_label("Pack Details")
        .build();
    let details = StaticBoxSizerBuilder::new_with_box(&details_box, Orientation::Vertical).build();
    let name_label = label(&panel, "Select a pack to view details");
    bold(&name_label, Some(12));
    details.add(&name_label, 0, SizerFlag::All, 5);
    let detail_line = |text: &str| {
        let l = label(&panel, text);
        details.add(&l, 0, SizerFlag::Left | SizerFlag::Bottom, 5);
        l
    };
    let author_label = detail_line("");
    let version_label = detail_line("");
    let size_label = detail_line("");
    right.add_sizer(&details, 0, SizerFlag::Expand | SizerFlag::Bottom, 10);
    let desc_label = label(&panel, "Description:");
    bold(&desc_label, None);
    right.add(&desc_label, 0, SizerFlag::Bottom, 5);
    let description_text = TextCtrl::builder(&panel)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::WordWrap)
        .with_size(Size::new(-1, 150))
        .build();
    right.add(&description_text, 1, SizerFlag::Expand, 0);
    content.add_sizer(&right, 1, SizerFlag::Expand, 0);
    main_sizer.add_sizer(
        &content,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        10,
    );

    let status_label = label(&panel, "");
    main_sizer.add(
        &status_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    buttons.add_stretch_spacer(1);
    let install_btn = Button::builder(&panel)
        .with_label("Download && Install")
        .build();
    install_btn.enable(false);
    buttons.add(&install_btn, 0, SizerFlag::Right, 5);
    let close_btn = Button::builder(&panel)
        .with_id(ID_CLOSE)
        .with_label("Close")
        .build();
    buttons.add(&close_btn, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 10);
    panel.set_sizer(main_sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);

    // `_setup_accessibility`.
    search_input.set_name("Filter packs input");
    refresh_btn.set_name("Refresh community packs");
    pack_listbox.set_name("Available community sound packs list");
    description_text.set_name("Community pack description");
    install_btn.set_name("Download and install selected community pack");
    close_btn.set_name("Close community sound packs dialog");

    let d = Rc::new(CommunityDialog {
        dialog,
        soundpacks_dir: soundpacks_dir.to_path_buf(),
        on_installed: Box::new(on_installed),
        service,
        packs: RefCell::new(Vec::new()),
        list_keys: RefCell::new(Vec::new()),
        selected_key: RefCell::new(None),
        search_input,
        refresh_btn,
        pack_listbox,
        name_label,
        author_label,
        version_label,
        size_label,
        description_text,
        status_label,
        install_btn,
    });
    {
        let d2 = d.clone();
        search_input.on_text_changed(move |_| d2.populate_list(&d2.search_input.get_value()));
        let d2 = d.clone();
        refresh_btn.on_click(move |_| d2.start_loading(true));
        let d2 = d.clone();
        pack_listbox.on_selection_changed(move |_| d2.on_pack_selected());
        let d2 = d.clone();
        install_btn.on_click(move |_| d2.on_install());
        close_btn.on_click(move |_| dialog.end_modal(ID_CLOSE));
        dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
            if e.get_key_code() == Some(WXK_ESCAPE) {
                dialog.end_modal(ID_CLOSE);
            } else {
                e.skip(true);
            }
        });
    }
    dialog.centre();
    search_input.set_focus();
    // Load once the dialog is up (`wx.CallAfter(self._start_loading)`).
    post_to_ui(move || {
        if let Some(d) = open_dialog(dialog) {
            d.start_loading(false);
        }
    });

    OPEN_DIALOG.with(|slot| *slot.borrow_mut() = Some(d));
    dialog.show_modal();
    OPEN_DIALOG.with(|slot| slot.borrow_mut().take());
    dialog.destroy();
}

impl CommunityDialog {
    fn set_list_rows(&self, rows: Vec<(String, Option<String>)>) {
        self.pack_listbox.clear();
        let mut keys = Vec::with_capacity(rows.len());
        for (text, key) in rows {
            self.pack_listbox.append(&text);
            keys.push(key);
        }
        *self.list_keys.borrow_mut() = keys;
    }

    /// `_pack_index` lookup: the last pack with this key wins, like the dict.
    fn pack_for(&self, key: &str) -> Option<CommunityPack> {
        self.packs
            .borrow()
            .iter()
            .rev()
            .find(|p| p.key() == key)
            .cloned()
    }

    fn start_loading(&self, force: bool) {
        let Some(service) = self.service.clone() else {
            self.status_label.set_label("Community packs unavailable");
            return;
        };
        self.status_label.set_label("Loading community packs...");
        self.refresh_btn.enable(false);
        self.set_list_rows(vec![("Loading...".into(), None)]);
        let dialog = self.dialog;
        std::thread::Builder::new()
            .name("aw-community-packs".into())
            .spawn(move || {
                let result = service.fetch_available_packs(force);
                if let Err(e) = &result {
                    tracing::error!("Failed to load community packs: {e}");
                }
                post_to_ui(move || {
                    let Some(d) = open_dialog(dialog) else { return };
                    match result {
                        Ok(packs) => d.on_packs_loaded(packs),
                        Err(e) => d.on_load_error(&e.to_string()),
                    }
                });
            })
            .expect("spawn community packs thread");
    }

    fn on_packs_loaded(&self, packs: Vec<CommunityPack>) {
        let count = packs.len();
        *self.packs.borrow_mut() = packs;
        // Python repopulates unfiltered, whatever the filter box holds.
        self.populate_list("");
        self.refresh_btn.enable(true);
        self.status_label
            .set_label(&format!("Found {count} community packs"));
    }

    fn on_load_error(&self, error: &str) {
        self.set_list_rows(vec![("Failed to load packs".into(), None)]);
        self.status_label.set_label(&format!("Error: {error}"));
        self.refresh_btn.enable(true);
    }

    fn populate_list(&self, filter_text: &str) {
        *self.selected_key.borrow_mut() = None;
        self.install_btn.enable(false);
        let rows: Vec<(String, Option<String>)> = filter_packs(&self.packs.borrow(), filter_text)
            .into_iter()
            .map(|p| (p.list_label(), Some(p.key())))
            .collect();
        if rows.is_empty() {
            self.set_list_rows(vec![("No packs found".into(), None)]);
            self.update_details(None);
        } else {
            self.set_list_rows(rows);
        }
    }

    fn on_pack_selected(&self) {
        let key = self
            .pack_listbox
            .get_selection()
            .and_then(|i| self.list_keys.borrow().get(i as usize).cloned().flatten());
        let pack = key.as_deref().and_then(|k| self.pack_for(k));
        match pack {
            Some(pack) => {
                *self.selected_key.borrow_mut() = key;
                self.update_details(Some(&pack));
                self.install_btn.enable(pack.installable());
            }
            None => {
                *self.selected_key.borrow_mut() = None;
                self.update_details(None);
                self.install_btn.enable(false);
            }
        }
    }

    fn update_details(&self, pack: Option<&CommunityPack>) {
        let Some(pack) = pack else {
            self.name_label.set_label("Select a pack to view details");
            self.author_label.set_label("");
            self.version_label.set_label("");
            self.size_label.set_label("");
            self.description_text.set_value("");
            return;
        };
        let [name, author, version, size, description] = pack.detail_labels();
        self.name_label.set_label(&name);
        self.author_label.set_label(&author);
        self.version_label.set_label(&version);
        self.size_label.set_label(&size);
        self.description_text.set_value(&description);
    }

    fn on_install(&self) {
        let Some(service) = self.service.clone() else {
            return;
        };
        let Some(pack) = self
            .selected_key
            .borrow()
            .as_deref()
            .and_then(|k| self.pack_for(k))
        else {
            return;
        };
        let progress = ProgressDialog::new(
            &self.dialog,
            &format!("Downloading {}", pack.name),
            "Preparing download...",
        );
        progress.dialog.show(true);
        let soundpacks_dir = self.soundpacks_dir.clone();
        let dialog = self.dialog;
        std::thread::Builder::new()
            .name("aw-community-install".into())
            .spawn(move || {
                let outcome = download_and_install(&service, &pack, &soundpacks_dir, &progress);
                post_to_ui(move || {
                    let Some(d) = open_dialog(dialog) else { return };
                    match outcome {
                        Outcome::Installed => d.on_install_success(&progress, &pack.name),
                        Outcome::Cancelled => {
                            progress.complete_error("Download cancelled");
                            progress.destroy_later(1500);
                        }
                        Outcome::Failed(error) => {
                            progress.complete_error(&error);
                            progress.destroy_later(3000);
                        }
                    }
                });
            })
            .expect("spawn community install thread");
    }

    fn on_install_success(&self, progress: &ProgressDialog, pack_name: &str) {
        progress.destroy();
        show_info(
            &self.dialog,
            &format!(
                "\"{pack_name}\" has been installed.\n\n\
                 Switch to the Sound Pack Manager or Settings > Audio to activate it."
            ),
            "Sound Pack Installed",
        );
        (self.on_installed)(pack_name);
    }
}

enum Outcome {
    Installed,
    Cancelled,
    Failed(String),
}

/// The download worker thread (`download_thread`).
fn download_and_install(
    service: &CommunitySoundPackService,
    pack: &CommunityPack,
    soundpacks_dir: &Path,
    progress: &ProgressDialog,
) -> Outcome {
    let tmp_dir = soundpacks_dir.join("_downloads");
    let status = format!("Downloading {}...", pack.name);
    let downloaded = service.download_pack(pack, &tmp_dir, &mut |pct, done, total| {
        progress.update_progress(pct, &status, &progress_detail(done, total))
    });
    let zip_path = match downloaded {
        Ok(path) => path,
        // Python's cancelled download escapes its handler and leaves the
        // dialog reading "Cancelling..."; this ends it the way its unused
        // `_on_download_cancelled` does.
        Err(CommunityError::Cancelled) => return Outcome::Cancelled,
        Err(e) => {
            tracing::error!("Download/install failed: {e}");
            return Outcome::Failed(e.to_string());
        }
    };
    if progress.is_cancelled() {
        return Outcome::Cancelled;
    }
    progress.set_status("Installing...", &format!("Installing {}", pack.name));
    match install_from_zip(soundpacks_dir, &zip_path, None) {
        (true, _) => Outcome::Installed,
        (false, message) => Outcome::Failed(message),
    }
}
