//! The Weather Assistant chat (`ui/dialogs/weather_assistant_dialog.py` and
//! `weather_assistant_widgets.py`). Replies come from a worker thread; closing
//! the dialog cancels a pending one.

use std::cell::{Cell, RefCell};
use std::rc::Rc;
use std::sync::Arc;

use aw_ai::assistant::{
    build_weather_context, chat_entry, error_message, generate_response, prepare_request,
    welcome_message, AssistantAnswer, AssistantConversation, RESTORED_QUESTION_NOTE,
};
use aw_ai::tools::WeatherToolExecutor;
use aw_ai::{AiErrorKind, CancelToken};
use aw_providers::{HttpClient, ReqwestClient};
use chrono::{Local, Utc};
use wxdragon::prelude::*;

use super::assistant_host::AppAssistantHost;
use super::main_window::window;
use crate::app::{post_to_ui, with_state};
use crate::screen_reader::announce;

const TITLE: &str = "Weather Assistant";
const SPEAKER: &str = "Weather Assistant";
const YOU: &str = "You";
const CONVERSATION_LABEL: &str = "&Conversation:";
const HISTORY_NAME: &str = "Conversation history";
const MESSAGE_LABEL: &str = "&Message:";
const INPUT_NAME: &str = "Type your message";
const SEND_LABEL: &str = "&Send";
const CLEAR_LABEL: &str = "C&lear Chat";
const COPY_LABEL: &str = "Cop&y Chat";
const CLOSE_LABEL: &str = "&Close";
const THINKING: &str = "Thinking...";
const READY: &str = "Ready";
const COPIED: &str = "Chat copied to clipboard.";

fn spoken(speaker: &str, text: &str) -> String {
    format!("{speaker}: {text}")
}

fn model_status(model: &str) -> String {
    format!("Model: {model}")
}

/// `_on_response_error`'s announcement.
fn error_announcement(error: &str, restored: bool) -> String {
    let mut text = spoken(SPEAKER, &error_message(error));
    if restored {
        text.push_str(RESTORED_QUESTION_NOTE);
    }
    text
}

/// `WeatherAssistantDialog`.
struct Assistant {
    history: TextCtrl,
    status: StaticText,
    input: TextCtrl,
    send: Button,
    clear: Button,
    conversation: RefCell<AssistantConversation>,
    generating: Cell<bool>,
    /// Cancelled when the dialog closes.
    cancel: CancelToken,
}

thread_local! {
    static OPEN: RefCell<Option<Rc<Assistant>>> = const { RefCell::new(None) };
}

fn with_open(f: impl FnOnce(&Assistant)) {
    if let Some(assistant) = OPEN.with(|o| o.borrow().clone()) {
        f(&assistant);
    }
}

/// View > Weather Assistant (Ctrl+T): `show_weather_assistant_dialog`.
pub(crate) fn show_weather_assistant_dialog() {
    let Some(w) = window() else { return };
    let dialog = Dialog::builder(&w.frame, TITLE)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let panel = Panel::builder(&dialog).build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();

    let conversation_label = StaticText::builder(&panel)
        .with_label(CONVERSATION_LABEL)
        .build();
    sizer.add(
        &conversation_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );
    let history = TextCtrl::builder(&panel)
        .with_style(
            TextCtrlStyle::MultiLine
                | TextCtrlStyle::ReadOnly
                | TextCtrlStyle::WordWrap
                | TextCtrlStyle::Rich2,
        )
        .build();
    history.set_name(HISTORY_NAME);
    sizer.add(&history, 1, SizerFlag::All | SizerFlag::Expand, 10);
    let status = StaticText::builder(&panel).with_label("").build();
    sizer.add(
        &status,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Expand,
        10,
    );

    let input_row = BoxSizer::builder(Orientation::Horizontal).build();
    let message_label = StaticText::builder(&panel)
        .with_label(MESSAGE_LABEL)
        .build();
    input_row.add(
        &message_label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        5,
    );
    let input = TextCtrl::builder(&panel)
        .with_style(TextCtrlStyle::ProcessEnter)
        .build();
    input.set_name(INPUT_NAME);
    input_row.add(
        &input,
        1,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        5,
    );
    let send = Button::builder(&panel).with_label(SEND_LABEL).build();
    input_row.add(&send, 0, SizerFlag::AlignCenterVertical, 0);
    sizer.add_sizer(
        &input_row,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom | SizerFlag::Expand,
        10,
    );

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    let clear = Button::builder(&panel).with_label(CLEAR_LABEL).build();
    buttons.add(&clear, 0, SizerFlag::Right, 5);
    let copy = Button::builder(&panel).with_label(COPY_LABEL).build();
    buttons.add(&copy, 0, SizerFlag::Right, 5);
    buttons.add_stretch_spacer(1);
    let close = Button::builder(&panel)
        .with_id(ID_CLOSE)
        .with_label(CLOSE_LABEL)
        .build();
    buttons.add(&close, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(
        &buttons,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom | SizerFlag::Expand,
        10,
    );
    panel.set_sizer(sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);

    let assistant = Rc::new(Assistant {
        history,
        status,
        input,
        send,
        clear,
        conversation: RefCell::new(AssistantConversation::new()),
        generating: Cell::new(false),
        cancel: CancelToken::new(),
    });
    OPEN.with(|o| *o.borrow_mut() = Some(assistant.clone()));

    send.on_click(|_| with_open(Assistant::on_send));
    input.on_text_enter(|_| with_open(Assistant::on_send));
    clear.on_click(|_| with_open(Assistant::on_clear));
    copy.on_click(|_| with_open(Assistant::on_copy));
    // `_on_close`: the Close button, the close box and Escape all end here.
    let cancel = assistant.cancel.clone();
    let on_close = move || {
        cancel.cancel();
        dialog.end_modal(ID_CLOSE);
    };
    let on_button = on_close.clone();
    close.on_click(move |_| on_button());
    dialog.bind_internal(EventType::CLOSE_WINDOW, move |_: Event| on_close());
    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            dialog.close(false);
        } else {
            e.skip(true);
        }
    });

    assistant.add_welcome_message();
    dialog.set_size(Size::new(650, 500));
    dialog.center();
    input.set_focus();

    dialog.show_modal();
    assistant.cancel.cancel();
    OPEN.with(|o| o.borrow_mut().take());
    dialog.destroy();
}

impl Assistant {
    fn add_welcome_message(&self) {
        let location = with_state().and_then(|s| {
            s.borrow()
                .config
                .current_location
                .as_ref()
                .map(|l| l.name.clone())
        });
        let welcome = welcome_message(location.as_deref());
        self.append_to_display(SPEAKER, &welcome);
        announce(&spoken(SPEAKER, &welcome));
    }

    /// `_append_to_display`. wxMSW's `AppendText` scrolls a rich edit
    /// control to the end, which is all Python's `ShowPosition` adds.
    fn append_to_display(&self, speaker: &str, text: &str) {
        self.history
            .append_text(&chat_entry(speaker, text, Local::now()));
    }

    fn set_generating(&self, generating: bool) {
        self.generating.set(generating);
        self.send.enable(!generating);
        self.clear.enable(!generating);
        // The input stays enabled so screen readers keep their focus.
        if generating {
            self.status.set_label(THINKING);
            announce(THINKING);
        } else {
            self.status.set_label(READY);
            self.input.set_focus();
        }
    }

    fn on_send(&self) {
        let message = self.input.get_value().trim().to_string();
        if message.is_empty() || self.generating.get() {
            return;
        }
        self.input.set_value("");
        self.append_to_display(YOU, &message);
        announce(&spoken(YOU, &message));
        self.conversation.borrow_mut().push_user(&message);
        self.set_generating(true);
        self.generate_response();
    }

    /// `_generate_response`: settings, context and the selected location are
    /// read here; the request and its tool calls run on a worker thread.
    fn generate_response(&self) {
        let Some(state) = with_state() else { return };
        let (settings, weather, location) = {
            let st = state.borrow();
            (
                st.config.settings.clone(),
                st.current_weather_data.clone(),
                st.config.current_location.clone(),
            )
        };
        let context = build_weather_context(weather.as_ref());
        let request = match prepare_request(&settings, &context, Local::now().fixed_offset()) {
            Ok(request) => request,
            Err(message) => {
                let cancel = self.cancel.clone();
                post_to_ui(move || {
                    if !cancel.is_cancelled() {
                        with_open(|a| a.on_response_error(&message));
                    }
                });
                return;
            }
        };
        let conversation = self.conversation.borrow().clone();
        let cancel = self.cancel.clone();
        std::thread::Builder::new()
            .name("aw-assistant".into())
            .spawn(move || {
                let http = ReqwestClient::new()
                    .inspect_err(|e| tracing::debug!("Could not create WeatherToolExecutor: {e}"))
                    .ok()
                    .map(|c| Arc::new(c) as Arc<dyn HttpClient>);
                let host = http.map(AppAssistantHost::new);
                let executor = host.as_ref().map(|h| {
                    WeatherToolExecutor::new(h, location.as_ref(), weather.as_ref(), Utc::now())
                });
                tracing::info!(
                    "Tool executor: {}",
                    if executor.is_some() {
                        "available"
                    } else {
                        "NONE"
                    }
                );
                let outcome =
                    generate_response(&request, &conversation, executor.as_ref(), Some(&cancel));
                if let Err(error) = &outcome {
                    if error.kind == AiErrorKind::Cancelled {
                        return;
                    }
                    tracing::warn!("Weather Assistant request failed: {:?}", error.kind);
                }
                post_to_ui(move || {
                    if cancel.is_cancelled() {
                        return;
                    }
                    with_open(|a| match outcome {
                        Ok(answer) => a.on_response_received(&answer),
                        Err(error) => a.on_response_error(&error.message),
                    });
                });
            })
            .expect("spawn assistant thread");
    }

    fn on_response_received(&self, answer: &AssistantAnswer) {
        self.conversation.borrow_mut().accept(answer);
        self.append_to_display(SPEAKER, &answer.text);
        announce(&spoken(SPEAKER, &answer.text));
        self.set_generating(false);
        self.status.set_label(&model_status(&answer.model));
    }

    /// Show the failure and put the question back when the input is empty.
    fn on_response_error(&self, error: &str) {
        self.append_to_display(SPEAKER, &error_message(error));
        let question = self.conversation.borrow_mut().take_failed_question();
        let restored = match question {
            Some(q) if !q.is_empty() && self.input.get_value().trim().is_empty() => {
                self.input.set_value(&q);
                self.input.set_insertion_point_end();
                true
            }
            _ => false,
        };
        announce(&error_announcement(error, restored));
        self.set_generating(false);
    }

    fn on_clear(&self) {
        if self.generating.get() {
            return;
        }
        self.conversation.borrow_mut().clear();
        self.history.set_value("");
        self.status.set_label("");
        self.add_welcome_message();
        self.input.set_focus();
    }

    fn on_copy(&self) {
        let text = self.history.get_value();
        if !text.is_empty() && Clipboard::get().set_text(&text) {
            self.status.set_label(COPIED);
        }
    }
}

#[cfg(test)]
mod tests {
    //! Golden parity with `weather_assistant_dialog.py`, generated by
    //! `rust/tools/golden/aiui.py`. The steps replay the dialog's handlers
    //! with the same text helpers the wx code uses.

    use chrono::TimeZone;
    use serde_json::{json, Value};

    use super::*;

    fn label(text: &str) -> Value {
        json!({"kind": "label", "label": text, "bold": false, "italic": false})
    }

    fn button(label: &str, id: Value) -> Value {
        json!({"kind": "button", "id": id, "label": label, "name": "button", "enabled": true})
    }

    /// The panel's controls in creation order (buttons enabled).
    fn controls(history: &str, status: &str, input: &str) -> Value {
        json!([
            label(CONVERSATION_LABEL),
            {"kind": "text", "name": HISTORY_NAME, "value": history},
            label(status),
            label(MESSAGE_LABEL),
            {"kind": "text", "name": INPUT_NAME, "value": input},
            button(SEND_LABEL, json!("auto")),
            button(CLEAR_LABEL, json!("auto")),
            button(COPY_LABEL, json!("auto")),
            button(CLOSE_LABEL, json!(ID_CLOSE)),
        ])
    }

    /// Model of the dialog state the handlers change.
    #[derive(Default)]
    struct Model {
        history: String,
        status: String,
        input: String,
        generating: bool,
        spoken: Vec<String>,
        conversation: AssistantConversation,
    }

    impl Model {
        fn append(&mut self, speaker: &str, text: &str) {
            let time = Local.with_ymd_and_hms(2026, 9, 25, 14, 3, 5).unwrap();
            self.history.push_str(&chat_entry(speaker, text, time));
        }
        fn welcome(&mut self, location: Option<&str>) {
            let welcome = welcome_message(location);
            self.append(SPEAKER, &welcome);
            self.spoken.push(spoken(SPEAKER, &welcome));
        }
        fn set_generating(&mut self, generating: bool) {
            self.generating = generating;
            if generating {
                self.status = THINKING.into();
                self.spoken.push(THINKING.into());
            } else {
                self.status = READY.into();
            }
        }
        fn send(&mut self, raw: &str) {
            self.input = raw.into();
            let message = raw.trim().to_string();
            if message.is_empty() || self.generating {
                return;
            }
            self.input.clear();
            self.append(YOU, &message);
            self.spoken.push(spoken(YOU, &message));
            self.conversation.push_user(&message);
            self.set_generating(true);
        }
        fn reply(&mut self, text: &str, model: &str) {
            let mut messages = vec![json!({"role": "system", "content": "s"})];
            messages.extend(self.conversation.messages.iter().cloned());
            messages.push(json!({"role": "assistant", "content": text}));
            self.conversation.accept(&AssistantAnswer {
                text: text.into(),
                model: model.into(),
                messages,
            });
            self.append(SPEAKER, text);
            self.spoken.push(spoken(SPEAKER, text));
            self.set_generating(false);
            self.status = model_status(model);
        }
        fn error(&mut self, error: &str) {
            self.append(SPEAKER, &error_message(error));
            let question = self.conversation.take_failed_question();
            let restored = match question {
                Some(q) if !q.is_empty() && self.input.trim().is_empty() => {
                    self.input = q;
                    true
                }
                _ => false,
            };
            self.spoken.push(error_announcement(error, restored));
            self.set_generating(false);
        }
        fn check(&mut self, step: &Value) {
            assert_eq!(step["history"], self.history, "{}", step["step"]);
            assert_eq!(step["status"], self.status, "{}", step["step"]);
            assert_eq!(step["input"], self.input, "{}", step["step"]);
            assert_eq!(step["send_enabled"], !self.generating);
            assert_eq!(step["clear_enabled"], !self.generating);
            assert_eq!(step["spoken"], json!(std::mem::take(&mut self.spoken)));
            if !self.generating {
                assert_eq!(
                    step["controls"],
                    controls(&self.history, &self.status, &self.input)
                );
            }
        }
    }

    #[test]
    fn assistant_dialog_matches_python() {
        let g: Value =
            serde_json::from_str(include_str!("../../../../testdata/golden/aiui/cases.json"))
                .unwrap();
        for case in g["assistant"].as_array().unwrap() {
            assert_eq!(case["title"], TITLE);
            let location = case["location"].as_str();
            let mut model = Model::default();
            for step in case["steps"].as_array().unwrap() {
                match step["step"].as_str().unwrap() {
                    "open" => {
                        model.welcome(location);
                        assert_eq!(step["focus"], INPUT_NAME);
                    }
                    "send" | "send_while_generating" => {
                        model.send(step["message"].as_str().unwrap())
                    }
                    "reply" => {
                        // The generator empties the input before the reply.
                        model.input.clear();
                        model.reply(
                            step["text"].as_str().unwrap(),
                            step["model"].as_str().unwrap(),
                        );
                    }
                    "error" => {
                        if let Some(before) = step["input_before"].as_str() {
                            model.input = before.into();
                        }
                        model.error(step["error"].as_str().unwrap());
                    }
                    "copy" => model.status = COPIED.into(),
                    "clear" => {
                        model.conversation.clear();
                        model.history.clear();
                        model.status.clear();
                        model.welcome(location);
                    }
                    other => panic!("unknown step {other}"),
                }
                model.check(step);
            }
            assert!(model.conversation.messages.is_empty());
            assert_eq!(case["conversation_after_clear"], json!([]));
        }
    }
}
