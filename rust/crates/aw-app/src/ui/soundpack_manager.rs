//! Sound Pack Manager, ported from `ui/dialogs/soundpack_manager_dialog.py`
//! and its mixins (`soundpack_manager_ui.py`, `_mappings.py`,
//! `_pack_actions.py`, `_community.py`, `_models.py`). The pack logic lives
//! in `aw_audio::manager`; this module is the wx shell and its messages.

use std::cell::{Cell, RefCell};
use std::path::PathBuf;
use std::rc::Rc;
use std::sync::atomic::AtomicBool;

use aw_audio::community::CommunitySoundPackService;
use aw_audio::events::friendly_sound_event_choices;
use aw_audio::manager::{self, SoundListItem, SoundPackInfo};
use aw_audio::submission::{backend_url_from_setting, PackSubmissionService, SubmitError};
use serde_json::{Map, Value};
use wxdragon::prelude::*;
use wxdragon::timer::Timer;
use wxdragon::window::WindowHandle;

use super::community_packs_dialog::show_community_packs_dialog;
use super::location_dialog::set_hint;
use super::main_window::message_box;
use super::progress_dialog::ProgressDialog;
use super::soundpack_wizard::show_soundpack_wizard;
use crate::app::{post_to_ui, with_state};

pub(super) const AUDIO_WILDCARD: &str =
    "Audio files (*.wav;*.mp3;*.ogg;*.flac)|*.wav;*.mp3;*.ogg;*.flac";
const ZIP_WILDCARD: &str = "ZIP files (*.zip)|*.zip";
const PREVIEW_LABEL: &str = "Preview Selected Sound";

pub(super) fn label<W: WxWidget>(parent: &W, text: &str) -> StaticText {
    StaticText::builder(parent).with_label(text).build()
}

/// Bold, optionally resized, font (Python's `SetWeight(wx.FONTWEIGHT_BOLD)`).
pub(super) fn bold(ctrl: &StaticText, point_size: Option<i32>) {
    if let Some(mut font) = ctrl.get_font() {
        if let Some(size) = point_size {
            font.set_point_size(size);
        }
        font.make_bold();
        ctrl.set_font(&font);
    }
}

/// Hint text in `wx.SYS_COLOUR_GRAYTEXT`.
pub(super) fn gray(ctrl: &StaticText) {
    ctrl.set_foreground_color(SystemSettings::get_colour(SystemColour::GrayText));
}

pub(super) fn show_info(parent: &dyn WxWidget, message: &str, caption: &str) {
    message_box(
        parent,
        message,
        caption,
        MessageDialogStyle::OK | MessageDialogStyle::IconInformation,
    );
}

pub(super) fn show_error(parent: &dyn WxWidget, message: &str, caption: &str) {
    message_box(
        parent,
        message,
        caption,
        MessageDialogStyle::OK | MessageDialogStyle::IconError,
    );
}

/// Yes/No question; true on Yes.
pub(super) fn ask(
    parent: &dyn WxWidget,
    message: &str,
    caption: &str,
    icon: MessageDialogStyle,
) -> bool {
    message_box(parent, message, caption, MessageDialogStyle::YesNo | icon) == ID_YES
}

/// Open/save file dialog returning the chosen path.
pub(super) fn choose_file(
    parent: &dyn WxWidget,
    message: &str,
    wildcard: &str,
    style: FileDialogStyle,
    default_file: &str,
) -> Option<PathBuf> {
    let dialog = FileDialog::builder(parent)
        .with_message(message)
        .with_default_file(default_file)
        .with_wildcard(wildcard)
        .with_style(style)
        .build();
    if dialog.show_modal() != ID_OK {
        return None;
    }
    dialog.get_path().map(PathBuf::from)
}

struct Manager {
    dialog: Dialog,
    soundpacks_dir: PathBuf,
    /// `FRIENDLY_ALERT_CATEGORIES`: `(label, event key)`.
    categories: Vec<(&'static str, &'static str)>,
    sound_packs: RefCell<Vec<SoundPackInfo>>,
    selected_pack: RefCell<Option<String>>,
    /// Client data of the two list boxes.
    pack_ids: RefCell<Vec<String>>,
    sound_items: RefCell<Vec<SoundListItem>>,
    current_preview_path: RefCell<Option<PathBuf>>,
    community_available: Cell<bool>,
    preview_timer: Timer<Dialog>,
    pack_listbox: ListBox,
    name_label: StaticText,
    author_label: StaticText,
    description_label: StaticText,
    sounds_listbox: ListBox,
    preview_btn: Button,
    category_choice: Choice,
    mapping_file_text: TextCtrl,
    volume_spin: SpinCtrl,
    set_volume_btn: Button,
    custom_key_input: TextCtrl,
    browse_community_btn: Button,
    share_btn: Button,
    duplicate_btn: Button,
    edit_btn: Button,
    delete_btn: Button,
    export_btn: Button,
}

thread_local! {
    /// The open manager; share results for a closed one show nothing.
    static OPEN_MANAGER: Cell<Option<WindowHandle>> = const { Cell::new(None) };
}

fn community_service_available() -> bool {
    CommunitySoundPackService::new()
        .inspect_err(|e| {
            tracing::warn!("Community packs disabled - failed to initialize service: {e}")
        })
        .is_ok()
}

/// `show_soundpack_manager_dialog`: Tools > Soundpack Manager and Settings >
/// Audio "Manage sound packs...". Returns when the dialog closes, so the
/// caller can refresh its own pack list.
pub(crate) fn open_soundpack_manager(parent: &dyn WxWidget) {
    let player = aw_audio::player();
    let soundpacks_dir = player.soundpacks_dir().to_path_buf();
    let _ = std::fs::create_dir(&soundpacks_dir);
    let community_available = community_service_available();

    let dialog = Dialog::builder(parent, "Sound Pack Manager")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(850, 600)
        .build();
    let panel = Panel::builder(&dialog).build();
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();

    let title = label(&panel, "Sound Pack Manager");
    bold(&title, Some(14));
    main_sizer.add(&title, 0, SizerFlag::All, 10);

    let content_sizer = BoxSizer::builder(Orientation::Horizontal).build();

    // Left: pack list.
    let left = BoxSizer::builder(Orientation::Vertical).build();
    left.add(
        &label(&panel, "Available Sound Packs:"),
        0,
        SizerFlag::Bottom,
        5,
    );
    let pack_listbox = ListBox::builder(&panel).build();
    left.add(&pack_listbox, 1, SizerFlag::Expand | SizerFlag::Bottom, 10);
    let import_btn = Button::builder(&panel)
        .with_label("Import Sound Pack...")
        .build();
    left.add(&import_btn, 0, SizerFlag::Expand | SizerFlag::Bottom, 5);
    let hint = label(&panel, "Hint: Select your active pack in Settings > Audio.");
    gray(&hint);
    left.add(&hint, 0, SizerFlag::empty(), 0);
    content_sizer.add_sizer(&left, 1, SizerFlag::Expand | SizerFlag::Right, 10);

    // Right: details, sounds and mappings.
    let right = BoxSizer::builder(Orientation::Vertical).build();
    let info_box = StaticBox::builder(&panel)
        .with_label("Sound Pack Details")
        .build();
    let info_sizer = StaticBoxSizerBuilder::new_with_box(&info_box, Orientation::Vertical).build();
    let name_label = label(&panel, "No pack selected");
    bold(&name_label, Some(12));
    info_sizer.add(&name_label, 0, SizerFlag::All, 5);
    let author_label = label(&panel, "");
    info_sizer.add(&author_label, 0, SizerFlag::Left | SizerFlag::Bottom, 5);
    let description_label = label(&panel, "");
    description_label.wrap(400);
    info_sizer.add(
        &description_label,
        0,
        SizerFlag::Left | SizerFlag::Bottom,
        5,
    );
    right.add_sizer(&info_sizer, 0, SizerFlag::Expand | SizerFlag::Bottom, 10);

    right.add(
        &label(&panel, "Sounds in this pack:"),
        0,
        SizerFlag::Bottom,
        5,
    );
    let sounds_listbox = ListBox::builder(&panel).build();
    right.add(&sounds_listbox, 1, SizerFlag::Expand | SizerFlag::Bottom, 5);
    let preview_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let preview_btn = Button::builder(&panel).with_label(PREVIEW_LABEL).build();
    preview_btn.enable(false);
    preview_sizer.add(&preview_btn, 0, SizerFlag::empty(), 0);
    right.add_sizer(&preview_sizer, 0, SizerFlag::Bottom, 10);

    let mapping_box = StaticBox::builder(&panel)
        .with_label("Sound Mappings")
        .build();
    let mapping_sizer =
        StaticBoxSizerBuilder::new_with_box(&mapping_box, Orientation::Vertical).build();
    let cat_row = BoxSizer::builder(Orientation::Horizontal).build();
    cat_row.add(
        &label(&panel, "Sound Event:"),
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        5,
    );
    let categories = friendly_sound_event_choices();
    let category_choice = Choice::builder(&panel)
        .with_choices(
            categories
                .iter()
                .map(|(name, _)| name.to_string())
                .collect(),
        )
        .build();
    cat_row.add(&category_choice, 1, SizerFlag::Right, 10);
    let mapping_file_text = TextCtrl::builder(&panel)
        .with_style(TextCtrlStyle::ReadOnly)
        .build();
    cat_row.add(&mapping_file_text, 1, SizerFlag::Right, 5);
    let browse_btn = Button::builder(&panel).with_label("Browse...").build();
    cat_row.add(&browse_btn, 0, SizerFlag::Right, 5);
    cat_row.add(
        &label(&panel, "Vol:"),
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        2,
    );
    let volume_spin = SpinCtrl::builder(&panel)
        .with_range(0, 100)
        .with_initial_value(100)
        .with_size(Size::new(60, -1))
        .build();
    volume_spin.set_tooltip("Volume percentage (0-100%)");
    cat_row.add(&volume_spin, 0, SizerFlag::Right, 5);
    let set_volume_btn = Button::builder(&panel).with_label("Set Vol").build();
    set_volume_btn.set_tooltip("Apply volume to current sound");
    set_volume_btn.enable(false);
    cat_row.add(&set_volume_btn, 0, SizerFlag::empty(), 0);
    mapping_sizer.add_sizer(&cat_row, 0, SizerFlag::Expand | SizerFlag::All, 5);

    let custom_row = BoxSizer::builder(Orientation::Horizontal).build();
    custom_row.add(
        &label(&panel, "Custom Key:"),
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        5,
    );
    let custom_key_input = TextCtrl::builder(&panel)
        .with_size(Size::new(200, -1))
        .with_style(TextCtrlStyle::ProcessEnter)
        .build();
    set_hint(&custom_key_input, "e.g., severe");
    custom_row.add(&custom_key_input, 1, SizerFlag::Right, 5);
    let add_mapping_btn = Button::builder(&panel)
        .with_label("Choose Sound...")
        .build();
    custom_row.add(&add_mapping_btn, 0, SizerFlag::Right, 5);
    let remove_mapping_btn = Button::builder(&panel).with_label("Remove").build();
    custom_row.add(&remove_mapping_btn, 0, SizerFlag::empty(), 0);
    mapping_sizer.add_sizer(&custom_row, 0, SizerFlag::Expand | SizerFlag::All, 5);
    right.add_sizer(&mapping_sizer, 0, SizerFlag::Expand, 0);
    content_sizer.add_sizer(&right, 2, SizerFlag::Expand, 0);

    main_sizer.add_sizer(
        &content_sizer,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        10,
    );

    // Bottom buttons.
    let button_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let button = |text: &str, enabled: bool| {
        let b = Button::builder(&panel).with_label(text).build();
        b.enable(enabled);
        b
    };
    let create_btn = button("Create Sound Pack...", true);
    let browse_community_btn = button("Browse Community", community_available);
    let share_btn = button("Share Pack", false);
    let duplicate_btn = button("Duplicate", false);
    let edit_btn = button("Edit...", false);
    let delete_btn = button("Delete", false);
    let export_btn = button("Export...", false);
    for b in [
        &create_btn,
        &browse_community_btn,
        &share_btn,
        &duplicate_btn,
        &edit_btn,
        &delete_btn,
    ] {
        button_sizer.add(b, 0, SizerFlag::Right, 5);
    }
    button_sizer.add(&export_btn, 0, SizerFlag::empty(), 0);
    button_sizer.add_stretch_spacer(1);
    let close_btn = Button::builder(&panel)
        .with_id(ID_CLOSE)
        .with_label("Close")
        .build();
    button_sizer.add(&close_btn, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&button_sizer, 0, SizerFlag::Expand | SizerFlag::All, 10);

    panel.set_sizer(main_sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);

    let m = Rc::new(Manager {
        dialog,
        soundpacks_dir,
        categories,
        sound_packs: RefCell::new(Vec::new()),
        selected_pack: RefCell::new(None),
        pack_ids: RefCell::new(Vec::new()),
        sound_items: RefCell::new(Vec::new()),
        current_preview_path: RefCell::new(None),
        community_available: Cell::new(community_available),
        preview_timer: Timer::new(&dialog),
        pack_listbox,
        name_label,
        author_label,
        description_label,
        sounds_listbox,
        preview_btn,
        category_choice,
        mapping_file_text,
        volume_spin,
        set_volume_btn,
        custom_key_input,
        browse_community_btn,
        share_btn,
        duplicate_btn,
        edit_btn,
        delete_btn,
        export_btn,
    });

    let on = |f: fn(&Rc<Manager>)| {
        let m = m.clone();
        move || f(&m)
    };
    {
        let f = on(Manager::on_preview_timer);
        m.preview_timer.on_tick(move |_| f());
        let f = on(Manager::on_pack_selected);
        pack_listbox.on_selection_changed(move |_| f());
        let f = on(Manager::on_import_pack);
        import_btn.on_click(move |_| f());
        let f = on(Manager::on_sound_selected);
        sounds_listbox.on_selection_changed(move |_| f());
        let f = on(Manager::on_preview_sound);
        preview_btn.on_click(move |_| f());
        let f = on(Manager::on_category_changed);
        category_choice.on_selection_changed(move |_| f());
        let f = on(Manager::on_browse_mapping);
        browse_btn.on_click(move |_| f());
        let f = on(Manager::on_set_volume);
        set_volume_btn.on_click(move |_| f());
        let f = on(Manager::on_add_custom_mapping);
        add_mapping_btn.on_click(move |_| f());
        let f = on(Manager::on_remove_mapping);
        remove_mapping_btn.on_click(move |_| f());
        let f = on(Manager::on_create_pack);
        create_btn.on_click(move |_| f());
        let f = on(Manager::on_browse_community);
        browse_community_btn.on_click(move |_| f());
        let f = on(Manager::on_share_pack);
        share_btn.on_click(move |_| f());
        let f = on(Manager::on_duplicate_pack);
        duplicate_btn.on_click(move |_| f());
        let f = on(Manager::on_edit_pack);
        edit_btn.on_click(move |_| f());
        let f = on(Manager::on_delete_pack);
        delete_btn.on_click(move |_| f());
        let f = on(Manager::on_export_pack);
        export_btn.on_click(move |_| f());
        close_btn.on_click(move |_| dialog.end_modal(ID_CLOSE));
        dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
            if e.get_key_code() == Some(WXK_ESCAPE) {
                dialog.end_modal(ID_CLOSE);
            } else {
                e.skip(true);
            }
        });
    }

    m.load_sound_packs();
    m.refresh_pack_list();
    dialog.centre();
    pack_listbox.set_focus();
    OPEN_MANAGER.with(|m| m.set(Some(dialog.window_handle())));
    dialog.show_modal();
    OPEN_MANAGER.with(|m| m.set(None));
    // Every close path stops the preview (`_on_close`, `_on_dialog_close`).
    m.preview_timer.stop();
    player.preview_stop();
    dialog.destroy();
}

impl Manager {
    fn selected_info(&self) -> Option<SoundPackInfo> {
        let id = self.selected_pack.borrow().clone()?;
        self.sound_packs
            .borrow()
            .iter()
            .find(|p| p.pack_id == id)
            .cloned()
    }

    fn load_sound_packs(&self) {
        *self.sound_packs.borrow_mut() = manager::load_sound_packs(&self.soundpacks_dir);
    }

    fn refresh_pack_list(self: &Rc<Self>) {
        self.pack_listbox.clear();
        let ids: Vec<String> = {
            let packs = self.sound_packs.borrow();
            manager::sorted_by_name(&packs)
                .into_iter()
                .map(|info| {
                    self.pack_listbox.append(&info.list_label());
                    info.pack_id.clone()
                })
                .collect()
        };
        let any = !ids.is_empty();
        *self.pack_ids.borrow_mut() = ids;
        if any {
            self.pack_listbox.set_selection(0, true);
            self.on_pack_selected();
        }
    }

    /// Select `pack_id` in the list, as after import, create and duplicate.
    fn select_pack(self: &Rc<Self>, pack_id: &str) {
        let index = self.pack_ids.borrow().iter().position(|id| id == pack_id);
        if let Some(i) = index {
            self.pack_listbox.set_selection(i as u32, true);
            self.on_pack_selected();
        }
    }

    fn reload_and_refresh(self: &Rc<Self>) {
        self.load_sound_packs();
        self.refresh_pack_list();
    }

    fn update_pack_details(self: &Rc<Self>) {
        let Some(info) = self.selected_info() else {
            self.name_label.set_label("No pack selected");
            self.author_label.set_label("");
            self.description_label.set_label("");
            self.sounds_listbox.clear();
            self.sound_items.borrow_mut().clear();
            for b in [
                &self.preview_btn,
                &self.duplicate_btn,
                &self.edit_btn,
                &self.delete_btn,
                &self.export_btn,
                &self.share_btn,
            ] {
                b.enable(false);
            }
            return;
        };
        self.name_label.set_label(&info.name);
        self.author_label.set_label(&info.author_label());
        self.description_label.set_label(info.description_label());
        self.description_label.wrap(400);

        self.sounds_listbox.clear();
        let items = manager::sound_list_items(&info);
        for item in &items {
            self.sounds_listbox.append(&item.label);
        }
        *self.sound_items.borrow_mut() = items;

        self.duplicate_btn.enable(true);
        self.edit_btn.enable(true);
        self.delete_btn.enable(!info.is_default());
        self.export_btn.enable(true);
        self.share_btn.enable(!info.is_default());
        self.on_category_changed();
    }

    // --- Mappings and preview (`soundpack_manager_mappings.py`) ----------

    fn on_pack_selected(self: &Rc<Self>) {
        let id = self
            .pack_listbox
            .get_selection()
            .and_then(|i| self.pack_ids.borrow().get(i as usize).cloned());
        *self.selected_pack.borrow_mut() = id;
        self.update_pack_details();
    }

    fn selected_sound(&self) -> Option<SoundListItem> {
        let i = self.sounds_listbox.get_selection()? as usize;
        self.sound_items.borrow().get(i).cloned()
    }

    fn on_sound_selected(self: &Rc<Self>) {
        let player = aw_audio::player();
        if player.preview_is_playing() {
            player.preview_stop();
            *self.current_preview_path.borrow_mut() = None;
        }
        self.preview_btn.set_label(PREVIEW_LABEL);
        let item = self.selected_sound();
        let (Some(item), Some(_)) = (item, self.selected_pack.borrow().clone()) else {
            self.preview_btn.enable(false);
            return;
        };
        let Some(info) = self.selected_info() else {
            return;
        };
        let exists = info.path.join(&item.file).exists();
        self.preview_btn.enable(exists);
        self.set_volume_btn.enable(exists);
        self.volume_spin.set_value((item.volume * 100.0) as i32);
    }

    /// Toggle: stop the sound this button started, or play the selection.
    fn on_preview_sound(self: &Rc<Self>) {
        let (Some(item), Some(info)) = (self.selected_sound(), self.selected_info()) else {
            return;
        };
        let volume = f64::from(self.volume_spin.value()) / 100.0;
        let path = info.path.join(&item.file);
        if !path.exists() {
            return;
        }
        let player = aw_audio::player();
        let same = self.current_preview_path.borrow().as_deref() == Some(path.as_path());
        if player.preview_is_playing() && same {
            player.preview_stop();
            self.preview_timer.stop();
            self.preview_btn.set_label(PREVIEW_LABEL);
            *self.current_preview_path.borrow_mut() = None;
            return;
        }
        player.preview_stop();
        if player.preview_play(&path, volume) {
            *self.current_preview_path.borrow_mut() = Some(path);
            self.preview_btn.set_label("Stop Preview");
            self.preview_timer.start(200, false);
        } else {
            *self.current_preview_path.borrow_mut() = None;
            self.preview_btn.set_label(PREVIEW_LABEL);
        }
    }

    fn on_preview_timer(self: &Rc<Self>) {
        if !aw_audio::player().preview_is_playing() {
            self.preview_timer.stop();
            *self.current_preview_path.borrow_mut() = None;
            self.preview_btn.set_label(PREVIEW_LABEL);
        }
    }

    fn selected_category(&self) -> Option<&'static str> {
        let i = self.category_choice.get_selection()? as usize;
        self.categories.get(i).map(|(_, key)| *key)
    }

    fn on_category_changed(self: &Rc<Self>) {
        let Some(info) = self.selected_info() else {
            self.mapping_file_text.set_value("");
            self.volume_spin.set_value(100);
            return;
        };
        let Some(key) = self.selected_category() else {
            return;
        };
        let (file, percent, enabled) = manager::category_mapping(&info, key);
        self.mapping_file_text.set_value(&file);
        self.volume_spin.set_value(percent as i32);
        self.set_volume_btn.enable(enabled);
    }

    /// "Set Vol": the selected sound, else the selected category's sound.
    fn on_set_volume(self: &Rc<Self>) {
        let Some(info) = self.selected_info() else {
            return;
        };
        let volume = f64::from(self.volume_spin.value()) / 100.0;
        let (key, file) = if let Some(item) = self.selected_sound() {
            (item.key, item.file)
        } else if let Some(key) = self.selected_category() {
            match manager::mapped_file(&info, key) {
                Some(file) => (key.to_string(), file),
                None => {
                    show_info(
                        &self.dialog,
                        "No sound mapped to this category yet.",
                        "No Sound",
                    );
                    return;
                }
            }
        } else {
            show_info(
                &self.dialog,
                "Please select a sound from the list or a category.",
                "No Selection",
            );
            return;
        };
        if file.is_empty() {
            return;
        }
        match manager::set_sound_mapping(&info.path, &key, &file, volume) {
            Ok(()) => {
                self.load_sound_packs();
                self.update_pack_details();
                let index = self.sound_items.borrow().iter().position(|i| i.key == key);
                if let Some(i) = index {
                    self.sounds_listbox.set_selection(i as u32, true);
                }
            }
            Err(e) => {
                tracing::error!("Failed to set volume: {e}");
                show_error(&self.dialog, &format!("Failed to set volume: {e}"), "Error");
            }
        }
    }

    fn on_browse_mapping(self: &Rc<Self>) {
        if self.selected_pack.borrow().is_none() {
            return;
        }
        match self.selected_category() {
            Some(key) => self.apply_mapping(key),
            None => show_info(
                &self.dialog,
                "Please select a category first.",
                "No Category",
            ),
        }
    }

    fn custom_key(&self) -> String {
        manager::normalize_custom_key(&self.custom_key_input.get_value())
    }

    fn on_add_custom_mapping(self: &Rc<Self>) {
        if self.selected_pack.borrow().is_none() {
            return;
        }
        let key = self.custom_key();
        if key.is_empty() {
            show_info(
                &self.dialog,
                "Please enter a mapping key first.",
                "Missing Key",
            );
            return;
        }
        self.apply_mapping(&key);
    }

    fn apply_mapping(self: &Rc<Self>, key: &str) {
        let Some(src) = choose_file(
            &self.dialog,
            "Select Audio File",
            AUDIO_WILDCARD,
            FileDialogStyle::Open | FileDialogStyle::FileMustExist,
            "",
        ) else {
            return;
        };
        let Some(info) = self.selected_info() else {
            return;
        };
        let volume = f64::from(self.volume_spin.value()) / 100.0;
        match manager::apply_mapping(&info, key, &src, volume) {
            Ok(message) => {
                self.load_sound_packs();
                self.update_pack_details();
                show_info(&self.dialog, &message, "Mapping Updated");
            }
            Err(e) => {
                tracing::error!("Failed to update mapping: {e}");
                show_error(
                    &self.dialog,
                    &format!("Failed to update mapping: {e}"),
                    "Error",
                );
            }
        }
    }

    fn on_remove_mapping(self: &Rc<Self>) {
        if self.selected_pack.borrow().is_none() {
            return;
        }
        let key = self.custom_key();
        if key.is_empty() {
            show_info(
                &self.dialog,
                "Please enter a mapping key to remove.",
                "Missing Key",
            );
            return;
        }
        let Some(info) = self.selected_info() else {
            return;
        };
        match manager::remove_mapping(&info, &key) {
            Ok(false) => show_info(
                &self.dialog,
                &format!("No mapping exists for '{key}'."),
                "Not Found",
            ),
            Ok(true) => {
                self.load_sound_packs();
                self.update_pack_details();
                show_info(
                    &self.dialog,
                    &format!("Removed mapping for '{key}'."),
                    "Mapping Removed",
                );
            }
            Err(e) => {
                tracing::error!("Failed to remove mapping: {e}");
                show_error(
                    &self.dialog,
                    &format!("Failed to remove mapping: {e}"),
                    "Error",
                );
            }
        }
    }

    // --- Pack actions (`soundpack_manager_pack_actions.py`) ---------------

    fn on_import_pack(self: &Rc<Self>) {
        let Some(zip_path) = choose_file(
            &self.dialog,
            "Select Sound Pack ZIP File",
            ZIP_WILDCARD,
            FileDialogStyle::Open | FileDialogStyle::FileMustExist,
            "",
        ) else {
            return;
        };
        let dialog = self.dialog;
        let result = manager::import_pack(&self.soundpacks_dir, &zip_path, |name| {
            ask(
                &dialog,
                &format!("A sound pack named '{name}' already exists. Overwrite?"),
                "Pack Exists",
                MessageDialogStyle::IconQuestion,
            )
        });
        match result {
            Ok(None) => {}
            Ok(Some(imported)) => {
                self.reload_and_refresh();
                self.select_pack(&imported.pack_id);
                show_info(
                    &self.dialog,
                    &format!("Sound pack '{}' imported successfully.", imported.pack_name),
                    "Import Successful",
                );
            }
            Err(e) => {
                show_error(&self.dialog, &e.to_string(), "Import Error");
            }
        }
    }

    fn on_create_pack(self: &Rc<Self>) {
        if let Some(pack_id) = show_soundpack_wizard(&self.dialog, &self.soundpacks_dir) {
            self.reload_and_refresh();
            self.select_pack(&pack_id);
        }
    }

    fn on_duplicate_pack(self: &Rc<Self>) {
        let Some(info) = self.selected_info() else {
            return;
        };
        let pack_id = match manager::duplicate_pack(&self.soundpacks_dir, &info) {
            Ok(id) => id,
            Err(e) => {
                // Python lets this exception escape the handler: no message.
                tracing::error!("Failed to duplicate sound pack: {e}");
                return;
            }
        };
        self.reload_and_refresh();
        self.select_pack(&pack_id);
        show_info(
            &self.dialog,
            &format!("Created '{} (Copy)'.", info.name),
            "Pack Duplicated",
        );
    }

    /// "Edit...": the Edit Sound Pack Metadata dialog.
    fn on_edit_pack(self: &Rc<Self>) {
        let Some(info) = self.selected_info() else {
            return;
        };
        let dialog = Dialog::builder(&self.dialog, "Edit Sound Pack Metadata")
            .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
            .with_size(400, 300)
            .build();
        let panel = Panel::builder(&dialog).build();
        let sizer = BoxSizer::builder(Orientation::Vertical).build();
        let field = SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom;

        sizer.add(&label(&panel, "Name:"), 0, SizerFlag::All, 5);
        let name_input = TextCtrl::builder(&panel).with_value(&info.name).build();
        sizer.add(&name_input, 0, field, 5);
        sizer.add(&label(&panel, "Author:"), 0, SizerFlag::All, 5);
        let author_input = TextCtrl::builder(&panel).with_value(&info.author).build();
        sizer.add(&author_input, 0, field, 5);
        sizer.add(&label(&panel, "Description:"), 0, SizerFlag::All, 5);
        let desc_input = TextCtrl::builder(&panel)
            .with_value(&info.description)
            .with_style(TextCtrlStyle::MultiLine)
            .with_size(Size::new(-1, 100))
            .build();
        sizer.add(&desc_input, 1, field, 5);

        let btn_sizer = BoxSizer::builder(Orientation::Horizontal).build();
        let save_btn = Button::builder(&panel)
            .with_id(ID_SAVE)
            .with_label("Save")
            .build();
        let cancel_btn = Button::builder(&panel)
            .with_id(ID_CANCEL)
            .with_label("Cancel")
            .build();
        btn_sizer.add(&save_btn, 0, SizerFlag::Right, 5);
        btn_sizer.add(&cancel_btn, 0, SizerFlag::empty(), 0);
        sizer.add_sizer(&btn_sizer, 0, SizerFlag::AlignRight | SizerFlag::All, 10);
        panel.set_sizer(sizer, true);
        let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
        dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
        dialog.set_sizer(dialog_sizer, true);

        let m = self.clone();
        save_btn.on_click(move |_| {
            let saved = manager::edit_metadata(
                &info,
                &name_input.get_value(),
                &author_input.get_value(),
                &desc_input.get_value(),
            );
            match saved {
                Ok(()) => {
                    m.reload_and_refresh();
                    m.update_pack_details();
                    dialog.end_modal(ID_OK);
                    show_info(&m.dialog, "Sound pack metadata updated.", "Pack Updated");
                }
                Err(e) => {
                    tracing::error!("Failed to save pack metadata: {e}");
                    show_error(
                        &dialog,
                        &format!("Failed to save pack metadata: {e}"),
                        "Save Error",
                    );
                }
            }
        });
        cancel_btn.on_click(move |_| dialog.end_modal(ID_CANCEL));
        dialog.show_modal();
        dialog.destroy();
    }

    fn on_delete_pack(self: &Rc<Self>) {
        let Some(info) = self.selected_info().filter(|i| !i.is_default()) else {
            return;
        };
        if !ask(
            &self.dialog,
            &format!(
                "Are you sure you want to delete '{}'?\n\nThis action cannot be undone.",
                info.name
            ),
            "Delete Sound Pack",
            MessageDialogStyle::IconWarning,
        ) {
            return;
        }
        match manager::delete_pack(&info) {
            Ok(_) => {
                self.reload_and_refresh();
                // As in Python the list keeps its first entry selected while
                // the details read "No pack selected".
                *self.selected_pack.borrow_mut() = None;
                self.update_pack_details();
                show_info(
                    &self.dialog,
                    &format!("Sound pack '{}' has been deleted.", info.name),
                    "Pack Deleted",
                );
            }
            Err(e) => {
                tracing::error!("Failed to delete sound pack: {e}");
                show_error(
                    &self.dialog,
                    &format!("Failed to delete sound pack: {e}"),
                    "Delete Error",
                );
            }
        }
    }

    fn on_export_pack(self: &Rc<Self>) {
        let Some(info) = self.selected_info() else {
            return;
        };
        let Some(output) = choose_file(
            &self.dialog,
            "Export Sound Pack",
            ZIP_WILDCARD,
            FileDialogStyle::Save | FileDialogStyle::OverwritePrompt,
            &format!("{}.zip", info.pack_id),
        ) else {
            return;
        };
        match manager::export_pack(&info, &output) {
            Ok(()) => show_info(
                &self.dialog,
                &format!("Sound pack exported to {}.", output.display()),
                "Export Successful",
            ),
            Err(e) => {
                tracing::error!("Failed to export sound pack: {e}");
                show_error(
                    &self.dialog,
                    &format!("Failed to export sound pack: {e}"),
                    "Export Error",
                );
            }
        }
    }

    // --- Community (`soundpack_manager_community.py`) ---------------------

    fn on_browse_community(self: &Rc<Self>) {
        if !self.community_available.get() {
            // Try to reinitialize.
            if community_service_available() {
                self.community_available.set(true);
                self.browse_community_btn.enable(true);
            } else {
                message_box(
                    &self.dialog,
                    "Community packs are temporarily unavailable. Please try again later.",
                    "Community Sound Packs",
                    MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
                );
                return;
            }
        }
        let m = self.clone();
        show_community_packs_dialog(&self.dialog, &self.soundpacks_dir, move |_| {
            m.reload_and_refresh();
        });
    }

    fn on_share_pack(self: &Rc<Self>) {
        let Some(info) = self.selected_info() else {
            show_info(
                &self.dialog,
                "Please select a sound pack to share.",
                "Share Pack",
            );
            return;
        };
        if info.is_default() {
            show_info(
                &self.dialog,
                "The default sound pack comes preinstalled and cannot be shared with the community.",
                "Share Pack",
            );
            return;
        }
        if !ask(
            &self.dialog,
            &format!(
                "Are you sure you want to share '{}' with the community?\n\n\
                 This will submit a pull request for review.",
                info.name
            ),
            "Confirm Share",
            MessageDialogStyle::IconQuestion,
        ) {
            return;
        }
        let (ok, msg) = aw_audio::validate_sound_pack(&info.path);
        if !ok {
            show_error(
                &self.dialog,
                &format!("Sound pack validation failed: {msg}"),
                "Share Pack",
            );
            return;
        }

        let progress = ProgressDialog::new(
            &self.dialog,
            "Sharing Sound Pack",
            "Preparing submission...",
        );
        progress.dialog.show(true);
        let backend_url = backend_url_from_setting(&github_backend_url_setting());
        let dialog = self.dialog;
        std::thread::Builder::new()
            .name("aw-share-pack".into())
            .spawn(move || {
                let result = share_pack(&progress, &backend_url, &info);
                post_to_ui(move || match result {
                    Ok(pr_url) => on_share_success(&dialog, &progress, &pr_url),
                    Err(SubmitError::Cancelled) => progress.destroy(),
                    Err(e) => {
                        progress.complete_error(&e.to_string());
                        progress.destroy_later(3000);
                    }
                });
            })
            .expect("spawn share thread");
    }
}

/// `github_backend_url` is not a typed `AppSettings` field yet; the Python
/// value round-trips through `extra`.
fn github_backend_url_setting() -> String {
    with_state()
        .and_then(|s| {
            s.borrow()
                .config
                .settings
                .extra
                .get("github_backend_url")
                .and_then(Value::as_str)
                .map(str::to_string)
        })
        .unwrap_or_default()
}

/// The share worker thread (`share_thread`).
fn share_pack(
    progress: &ProgressDialog,
    backend_url: &str,
    info: &SoundPackInfo,
) -> Result<String, SubmitError> {
    if progress.is_cancelled() {
        return Err(SubmitError::Cancelled);
    }
    progress.update_progress(10.0, "Connecting to backend...", "");
    let service = PackSubmissionService::new(backend_url).map_err(|e| {
        tracing::error!("Pack submission failed: {e}");
        SubmitError::Runtime(e.to_string())
    })?;
    if progress.is_cancelled() {
        return Err(SubmitError::Cancelled);
    }
    let mut meta = Map::new();
    meta.insert("name".into(), Value::from(info.name.as_str()));
    meta.insert("author".into(), Value::from(info.author.as_str()));
    meta.insert("description".into(), Value::from(info.description.as_str()));
    meta.insert("sounds".into(), Value::Object(info.sounds.clone()));
    let cancel = AtomicBool::new(false);
    let result = service.submit_pack(
        &info.path,
        &meta,
        &mut |pct, status| progress.update_progress(pct, status, ""),
        &cancel,
    );
    if let Err(e) = &result {
        if *e != SubmitError::Cancelled {
            tracing::error!("Pack submission failed: {e}");
        }
    }
    result
}

fn on_share_success(dialog: &Dialog, progress: &ProgressDialog, pr_url: &str) {
    progress.destroy();
    // Python's handler dies with the closed manager before its message.
    if OPEN_MANAGER.with(Cell::get) != Some(dialog.window_handle()) {
        return;
    }
    let open = ask(
        dialog,
        &format!(
            "🎉 Your sound pack has been submitted for review!\n\n\
             Pull Request: {pr_url}\n\n\
             Would you like to open the pull request in your browser?"
        ),
        "Sound Pack Shared Successfully",
        MessageDialogStyle::IconInformation,
    );
    if open {
        launch_default_browser(pr_url, BrowserLaunchFlags::Default);
    }
}
