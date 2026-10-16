//! Create Sound Pack wizard, ported from `ui/dialogs/soundpack_wizard_dialog.py`
//! (with `soundpack_wizard_shell.py`, `_scrolled.py` and `_state.py`). The
//! state and pack creation are `aw_audio::manager::SoundPackWizard`.

use std::cell::{Cell, RefCell};
use std::path::{Path, PathBuf};
use std::rc::Rc;

use aw_audio::events::{friendly_event_name, friendly_sound_event_choices};
use aw_audio::manager::{
    wizard_header, wizard_next_label, SoundPackWizard, WIZARD_COMMON_EVENTS, WIZARD_TOTAL_STEPS,
};
use wxdragon::prelude::*;

use super::location_dialog::set_hint;
use super::main_window::{keep_timer, message_box};
use super::soundpack_manager::{
    ask, bold, choose_file, gray, label, show_error, show_info, AUDIO_WILDCARD,
};

/// The current step's input controls, read when leaving it with Next.
enum StepControls {
    None,
    Details {
        name: TextCtrl,
        author: TextCtrl,
        description: TextCtrl,
    },
    Events(Vec<(&'static str, CheckBox)>),
}

struct Wizard {
    dialog: Dialog,
    soundpacks_dir: PathBuf,
    state: RefCell<SoundPackWizard>,
    current_step: Cell<u32>,
    created_pack_id: RefCell<Option<String>>,
    panel: Panel,
    header_label: StaticText,
    content_panel: Panel,
    prev_btn: Button,
    next_btn: Button,
    /// Children of `content_panel`, destroyed when the step changes
    /// (`content_sizer.Clear(True)`).
    step_widgets: RefCell<Vec<Box<dyn WxWidget>>>,
    controls: RefCell<StepControls>,
}

/// `ScrolledPanel` (`style=wx.TAB_TRAVERSAL`) after `SetupScrolling()`.
fn scrolled_panel(parent: &Panel, height: i32) -> ScrolledWindow {
    let scroll = ScrolledWindow::builder(parent)
        .with_size(Size::new(-1, height))
        .with_style(ScrolledWindowStyle::from_bits_retain(
            PanelStyle::TabTraversal.bits(),
        ))
        .build();
    scroll.set_scroll_rate(20, 20);
    scroll
}

fn three_column_grid() -> FlexGridSizer {
    let grid = FlexGridSizer::builder(0, 3)
        .with_hgap(5)
        .with_vgap(5)
        .build();
    grid.add_growable_col(1, 1);
    grid
}

/// `SoundPackWizardDialog`: the new pack's id when one was created.
pub(super) fn show_soundpack_wizard(
    parent: &dyn WxWidget,
    soundpacks_dir: &Path,
) -> Option<String> {
    let state = match SoundPackWizard::new() {
        Ok(state) => state,
        Err(e) => {
            tracing::error!("Failed to create the sound pack wizard staging folder: {e}");
            return None;
        }
    };
    let dialog = Dialog::builder(parent, "Create Sound Pack")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(650, 550)
        .build();

    // `create_wizard_shell`.
    let panel = Panel::builder(&dialog).build();
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let header_label = label(&panel, "");
    bold(&header_label, Some(12));
    main_sizer.add(&header_label, 0, SizerFlag::All, 10);
    let content_panel = Panel::builder(&panel).build();
    content_panel.set_sizer(BoxSizer::builder(Orientation::Vertical).build(), true);
    main_sizer.add(
        &content_panel,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        10,
    );
    let nav = BoxSizer::builder(Orientation::Horizontal).build();
    nav.add_stretch_spacer(1);
    let prev_btn = Button::builder(&panel).with_label("< Previous").build();
    nav.add(&prev_btn, 0, SizerFlag::Right, 5);
    let next_btn = Button::builder(&panel).with_label("Next >").build();
    nav.add(&next_btn, 0, SizerFlag::Right, 5);
    let cancel_btn = Button::builder(&panel)
        .with_id(ID_CANCEL)
        .with_label("Cancel")
        .build();
    nav.add(&cancel_btn, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&nav, 0, SizerFlag::Expand | SizerFlag::All, 10);
    panel.set_sizer(main_sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);

    let w = Rc::new(Wizard {
        dialog,
        soundpacks_dir: soundpacks_dir.to_path_buf(),
        state: RefCell::new(state),
        current_step: Cell::new(1),
        created_pack_id: RefCell::new(None),
        panel,
        header_label,
        content_panel,
        prev_btn,
        next_btn,
        step_widgets: RefCell::new(Vec::new()),
        controls: RefCell::new(StepControls::None),
    });
    {
        let w2 = w.clone();
        prev_btn.on_click(move |_| w2.go_previous());
        let w2 = w.clone();
        next_btn.on_click(move |_| w2.go_next());
        let w2 = w.clone();
        cancel_btn.on_click(move |_| w2.on_cancel());
        let w2 = w.clone();
        dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
            if e.get_key_code() == Some(WXK_ESCAPE) {
                w2.on_cancel();
            } else {
                e.skip(true);
            }
        });
        // The title-bar close goes through the same confirmation.
        let w2 = w.clone();
        dialog.bind_internal(EventType::CLOSE_WINDOW, move |_| w2.on_cancel());
    }
    w.render_step();
    dialog.centre();
    let result = dialog.show_modal();
    let created = w.created_pack_id.borrow_mut().take();
    dialog.destroy();
    created.filter(|_| result == ID_OK)
}

impl Wizard {
    /// Track a direct child of `content_panel` for the next step change.
    fn keep<W: WxWidget + Copy + 'static>(&self, widget: W) -> W {
        self.step_widgets.borrow_mut().push(Box::new(widget));
        widget
    }

    fn render_step(self: &Rc<Self>) {
        let step = self.current_step.get();
        self.header_label.set_label(&wizard_header(step));
        self.prev_btn.enable(step > 1);
        self.next_btn.set_label(wizard_next_label(step));

        let old: Vec<Box<dyn WxWidget>> = self.step_widgets.borrow_mut().drain(..).collect();
        for widget in old {
            // wxDragon defers child destruction; hide now so the old step
            // leaves the tab order at once, as `Clear(True)` does.
            widget.show(false);
            widget.destroy();
        }
        *self.controls.borrow_mut() = StepControls::None;

        let sizer = BoxSizer::builder(Orientation::Vertical).build();
        match step {
            1 => self.build_step1(&sizer),
            2 => self.build_step2(&sizer),
            3 => self.build_step3(&sizer),
            _ => self.build_step4(&sizer),
        }
        self.content_panel.set_sizer(sizer, true);
        self.content_panel.layout();
        self.panel.layout();
    }

    /// Step 1: Pack details.
    fn build_step1(&self, sizer: &BoxSizer) {
        let cp = &self.content_panel;
        let (pack_name, author, description) = {
            let st = self.state.borrow();
            (
                st.pack_name.clone(),
                st.author.clone(),
                st.description.clone(),
            )
        };
        sizer.add(
            &self.keep(label(cp, "Pack name (required):")),
            0,
            SizerFlag::Bottom,
            3,
        );
        let name = self.keep(TextCtrl::builder(cp).with_value(&pack_name).build());
        set_hint(&name, "e.g., My Weather Sounds");
        sizer.add(&name, 0, SizerFlag::Expand | SizerFlag::Bottom, 10);

        sizer.add(
            &self.keep(label(cp, "Author (optional):")),
            0,
            SizerFlag::Bottom,
            3,
        );
        let author = self.keep(TextCtrl::builder(cp).with_value(&author).build());
        sizer.add(&author, 0, SizerFlag::Expand | SizerFlag::Bottom, 10);

        sizer.add(
            &self.keep(label(cp, "Description (optional):")),
            0,
            SizerFlag::Bottom,
            3,
        );
        let description = self.keep(
            TextCtrl::builder(cp)
                .with_value(&description)
                .with_style(TextCtrlStyle::MultiLine)
                .with_size(Size::new(-1, 100))
                .build(),
        );
        sizer.add(&description, 1, SizerFlag::Expand | SizerFlag::Bottom, 10);

        let hint = self.keep(label(
            cp,
            "A folder name will be generated from your pack name.",
        ));
        gray(&hint);
        sizer.add(&hint, 0, SizerFlag::empty(), 0);

        name.set_focus();
        *self.controls.borrow_mut() = StepControls::Details {
            name,
            author,
            description,
        };
    }

    /// Step 2: Select sound events.
    fn build_step2(&self, sizer: &BoxSizer) {
        let cp = &self.content_panel;
        sizer.add(
            &self.keep(label(
                cp,
                "Choose the app and alert-severity events you want sounds for:",
            )),
            0,
            SizerFlag::Bottom,
            10,
        );
        let scroll = self.keep(scrolled_panel(cp, 300));
        let scroll_sizer = BoxSizer::builder(Orientation::Vertical).build();
        let checks: Vec<(&'static str, CheckBox)> = {
            let st = self.state.borrow();
            friendly_sound_event_choices()
                .into_iter()
                .map(|(display_name, key)| {
                    let cb = CheckBox::builder(&scroll)
                        .with_label(display_name)
                        .with_value(st.selected_alert_keys.iter().any(|k| k == key))
                        .build();
                    scroll_sizer.add(&cb, 0, SizerFlag::Bottom, 5);
                    (key, cb)
                })
                .collect()
        };
        scroll.set_sizer(scroll_sizer, true);
        sizer.add(&scroll, 1, SizerFlag::Expand | SizerFlag::Bottom, 10);

        let buttons = BoxSizer::builder(Orientation::Horizontal).build();
        let select_common = self.keep(Button::builder(cp).with_label("Select Common").build());
        buttons.add(&select_common, 0, SizerFlag::Right, 5);
        let clear_all = self.keep(Button::builder(cp).with_label("Clear All").build());
        buttons.add(&clear_all, 0, SizerFlag::empty(), 0);
        sizer.add_sizer(&buttons, 0, SizerFlag::empty(), 0);

        let c = checks.clone();
        select_common.on_click(move |_| {
            for (key, cb) in &c {
                cb.set_value(WIZARD_COMMON_EVENTS.contains(key));
            }
        });
        let c = checks.clone();
        clear_all.on_click(move |_| {
            for (_, cb) in &c {
                cb.set_value(false);
            }
        });
        *self.controls.borrow_mut() = StepControls::Events(checks);
    }

    /// Step 3: Assign sounds.
    fn build_step3(self: &Rc<Self>, sizer: &BoxSizer) {
        let cp = &self.content_panel;
        sizer.add(
            &self.keep(label(
                cp,
                "Assign a sound file to each selected event. You can leave some blank.",
            )),
            0,
            SizerFlag::Bottom,
            10,
        );
        let scroll = self.keep(scrolled_panel(cp, 350));
        let grid = three_column_grid();
        let keys = self.state.borrow().selected_alert_keys.clone();
        for key in keys {
            grid.add(
                &label(&scroll, &format!("{}:", friendly_event_name(&key))),
                0,
                SizerFlag::AlignCenterVertical,
                0,
            );
            let file_ctrl = TextCtrl::builder(&scroll)
                .with_style(TextCtrlStyle::ReadOnly)
                .build();
            if let Some(name) = self.state.borrow().mapped_file_name(&key) {
                file_ctrl.set_value(&name);
            }
            grid.add(&file_ctrl, 1, SizerFlag::Expand, 0);
            let choose_btn = Button::builder(&scroll)
                .with_label("Choose...")
                .with_size(Size::new(80, -1))
                .build();
            let w = self.clone();
            choose_btn.on_click(move |_| w.choose_sound_file(&key, &file_ctrl));
            grid.add(&choose_btn, 0, SizerFlag::empty(), 0);
        }
        scroll.set_sizer(grid, true);
        sizer.add(&scroll, 1, SizerFlag::Expand, 0);
    }

    fn choose_sound_file(&self, key: &str, file_ctrl: &TextCtrl) {
        let Some(src) = choose_file(
            &self.dialog,
            &format!("Choose sound for {key}"),
            AUDIO_WILDCARD,
            FileDialogStyle::Open | FileDialogStyle::FileMustExist,
            "",
        ) else {
            return;
        };
        if !src.exists() {
            return;
        }
        let staged = self.state.borrow_mut().stage_sound(key, &src);
        match staged {
            Ok(name) => file_ctrl.set_value(&name),
            // Python lets the copy error escape the handler: no message.
            Err(e) => tracing::error!("Failed to stage {}: {e}", src.display()),
        }
    }

    /// Step 4: Preview & Finalize.
    fn build_step4(self: &Rc<Self>, sizer: &BoxSizer) {
        let cp = &self.content_panel;
        let (summary, description, assigned, keys) = {
            let st = self.state.borrow();
            (
                st.summary(),
                st.description.clone(),
                st.assigned_summary(),
                st.selected_alert_keys.clone(),
            )
        };
        sizer.add(&self.keep(label(cp, &summary)), 0, SizerFlag::Bottom, 5);
        if !description.is_empty() {
            let desc = self.keep(label(cp, &description));
            desc.wrap(500);
            sizer.add(&desc, 0, SizerFlag::Bottom, 5);
        }
        sizer.add(&self.keep(label(cp, &assigned)), 0, SizerFlag::Bottom, 10);

        let scroll = self.keep(scrolled_panel(cp, 250));
        let grid = three_column_grid();
        for key in keys {
            grid.add(
                &label(&scroll, &format!("{}:", friendly_event_name(&key))),
                0,
                SizerFlag::AlignCenterVertical,
                0,
            );
            let file_name = self.state.borrow().mapped_file_name(&key);
            let mapped = file_name.is_some();
            grid.add(
                &label(&scroll, file_name.as_deref().unwrap_or("(default)")),
                1,
                SizerFlag::Expand,
                0,
            );
            let preview_btn = Button::builder(&scroll)
                .with_label("Preview")
                .with_size(Size::new(70, -1))
                .build();
            let w = self.clone();
            preview_btn.on_click(move |_| w.preview_sound(&key));
            preview_btn.enable(mapped);
            grid.add(&preview_btn, 0, SizerFlag::empty(), 0);
        }
        scroll.set_sizer(grid, true);
        sizer.add(&scroll, 1, SizerFlag::Expand | SizerFlag::Bottom, 10);

        let test_all_btn = self.keep(Button::builder(cp).with_label("Test All Sounds").build());
        let w = self.clone();
        test_all_btn.on_click(move |_| w.test_all_sounds());
        sizer.add(&test_all_btn, 0, SizerFlag::empty(), 0);
    }

    fn preview_sound(&self, key: &str) {
        if let Some(path) = self.state.borrow().mapped_path(key) {
            aw_audio::player().play_file(path, 1.0);
        }
    }

    /// The first five selected events' sounds, 500 ms apart, without
    /// blocking the UI.
    fn test_all_sounds(&self) {
        let sounds = self.state.borrow().test_all_files();
        if !sounds.is_empty() {
            play_next(Rc::new(sounds), 0);
        }
    }

    /// `_validate_current_step`, storing the step's values.
    fn validate_current_step(&self) -> bool {
        let checked = match &*self.controls.borrow() {
            StepControls::Details {
                name,
                author,
                description,
            } => self
                .state
                .borrow_mut()
                .set_details(
                    &name.get_value(),
                    &author.get_value(),
                    &description.get_value(),
                )
                .map_err(|msg| (msg, "Missing Name")),
            StepControls::Events(checks) => self
                .state
                .borrow_mut()
                .set_selected_events(
                    checks
                        .iter()
                        .filter(|(_, cb)| cb.is_checked())
                        .map(|(key, _)| key.to_string())
                        .collect(),
                )
                .map_err(|msg| (msg, "No Selection")),
            StepControls::None => Ok(()),
        };
        match checked {
            Ok(()) => true,
            Err((message, caption)) => {
                message_box(
                    &self.dialog,
                    message,
                    caption,
                    MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
                );
                false
            }
        }
    }

    fn go_previous(self: &Rc<Self>) {
        let step = self.current_step.get();
        if step > 1 {
            self.current_step.set(step - 1);
            self.render_step();
        }
    }

    fn go_next(self: &Rc<Self>) {
        if !self.validate_current_step() {
            return;
        }
        let step = self.current_step.get();
        if step < WIZARD_TOTAL_STEPS {
            self.current_step.set(step + 1);
            self.render_step();
        } else {
            self.create_pack();
        }
    }

    fn create_pack(&self) {
        let created = self.state.borrow().create_pack(&self.soundpacks_dir);
        match created {
            Ok(pack_id) => {
                *self.created_pack_id.borrow_mut() = Some(pack_id);
                let name = self.state.borrow().pack_name.clone();
                show_info(
                    &self.dialog,
                    &format!("Sound pack '{name}' created successfully!"),
                    "Pack Created",
                );
                self.dialog.end_modal(ID_OK);
            }
            Err(e) => show_error(
                &self.dialog,
                &format!("Failed to create sound pack:\n{e}"),
                "Pack Creation Failed",
            ),
        }
    }

    /// Cancel, Escape and the title-bar close.
    fn on_cancel(&self) {
        let has_changes = self.state.borrow().has_changes();
        if has_changes
            && !ask(
                &self.dialog,
                "Discard changes and close the wizard?",
                "Cancel Wizard",
                MessageDialogStyle::IconQuestion,
            )
        {
            return;
        }
        self.dialog.end_modal(ID_CANCEL);
    }
}

/// `play_next`: play `sounds[index]`, then the next one 500 ms later.
fn play_next(sounds: Rc<Vec<PathBuf>>, index: usize) {
    let Some(file) = sounds.get(index) else {
        return;
    };
    aw_audio::player().play_file(file, 1.0);
    keep_timer(500, move || play_next(sounds.clone(), index + 1));
}
