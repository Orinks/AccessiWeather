//! AI weather explanations (`ui/dialogs/explanation_dialog.py`): the
//! "Generating Explanation" dialog shown while the model answers, then the
//! "Weather Explanation" dialog with its Regenerate button.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::Arc;

use aw_ai::payload::{add_location_time_context, build_current_weather_payload};
use aw_ai::{
    AiError, AiErrorKind, AiExplainer, CancelToken, ExplanationCache, ExplanationResult,
    ExplanationStyle,
};
use aw_core::model::{Location, WeatherData};
use aw_core::settings::AppSettings;
use chrono::Utc;
use wxdragon::prelude::*;

use super::main_window::{message_box, window};
use crate::app::{post_to_ui, with_state};

const ERROR_CAPTION: &str = "AI Explanation Error";
const NO_LOCATION: &str = "No location selected. Please select a location first.";
const NO_WEATHER: &str = "No weather data available. Please refresh weather data first.";
const NO_TEXT: &str = "(No explanation text received)";
const LOADING_TITLE: &str = "Generating Explanation";
const PLEASE_WAIT: &str = "Please wait...";
const CANCELLING: &str = "Cancelling...";
const CANCEL_LABEL: &str = "Cancel";
const EXPLANATION_LABEL: &str = "Explanation:";
const MODEL_INFO_LABEL: &str = "Model Information:";
const MODEL_INFO_NAME: &str = "Model information";
const REGENERATE_LABEL: &str = "&Regenerate";
const CLOSE_LABEL: &str = "Close";
const GENERATING: &str = "Generating explanation...";
const REGENERATING: &str = "Regenerating...";
/// Reported by Regenerate when the app has no current conditions.
const REGENERATE_NO_WEATHER: &str = "No weather data available.";

fn dialog_title(location: &str) -> String {
    format!("Weather Explanation - {location}")
}

fn header_text(location: &str) -> String {
    format!("Weather explanation for {location}")
}

fn loading_text(location: &str) -> String {
    format!("Generating explanation for {location}...")
}

fn generated_label(result: &ExplanationResult) -> String {
    format!("Generated: {}", result.timestamp_text())
}

fn explanation_text(result: &ExplanationResult) -> &str {
    if result.text.is_empty() {
        NO_TEXT
    } else {
        &result.text
    }
}

fn regenerate_failed_text(error: &str) -> String {
    format!("Failed to regenerate: {error}")
}

fn regenerate_failed_announcement(error: &str) -> String {
    format!("Failed to regenerate. {error}")
}

// ---------------------------------------------------------------------------
// Generation
// ---------------------------------------------------------------------------

/// The explanation's result, or the message to show instead.
type Outcome = Result<ExplanationResult, String>;

/// What an explanation reads from the app, on the UI thread.
struct Request {
    settings: AppSettings,
    location: Option<Location>,
    weather: Option<WeatherData>,
    cache: Arc<ExplanationCache>,
}

impl Request {
    fn current() -> Option<Self> {
        let state = with_state()?;
        let st = state.borrow();
        Some(Self {
            settings: st.config.settings.clone(),
            location: st.config.current_location.clone(),
            weather: st.current_weather_data.clone(),
            cache: st.ai_explanation_cache.clone(),
        })
    }
}

fn generate(
    request: &Request,
    location_name: &str,
    cancel: &CancelToken,
) -> Result<ExplanationResult, AiError> {
    let explainer =
        AiExplainer::from_settings(&request.settings)?.with_cache(request.cache.clone());
    let Some(weather) = request.weather.as_ref().filter(|d| d.current.is_some()) else {
        return Err(AiError::new(AiErrorKind::Explainer, REGENERATE_NO_WEATHER));
    };
    let settings = &request.settings;
    let mut payload = build_current_weather_payload(
        weather,
        &settings.temperature_unit,
        &settings.wind_speed_unit,
        request.location.as_ref(),
    );
    if let Some(location) = &request.location {
        add_location_time_context(&mut payload, location, Utc::now());
    }
    explainer.explain_weather(
        &payload,
        location_name,
        ExplanationStyle::from_setting(&settings.ai_explanation_style),
        false,
        &|_| {},
        Some(cancel),
    )
}

/// Generate on a worker thread; `done` receives the outcome on the UI
/// thread unless `cancel` fired first.
fn spawn_generation(
    request: Request,
    location_name: String,
    cancel: CancelToken,
    done: impl FnOnce(Outcome) + Send + 'static,
) {
    std::thread::Builder::new()
        .name("aw-explain".into())
        .spawn(move || {
            let outcome = generate(&request, &location_name, &cancel);
            if let Err(error) = &outcome {
                if error.kind == AiErrorKind::Cancelled {
                    return;
                }
                tracing::warn!("AI explanation error: {error}");
            }
            let outcome = outcome.map_err(|e| e.message);
            post_to_ui(move || {
                if !cancel.is_cancelled() {
                    done(outcome);
                }
            });
        })
        .expect("spawn explanation thread");
}

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

thread_local! {
    /// The loading dialog waiting for a result, and the result once it arrives.
    static LOADING: RefCell<Option<(Dialog, Option<Outcome>)>> = const { RefCell::new(None) };
    /// The open explanation dialog, for Regenerate results.
    static OPEN: RefCell<Option<Rc<ExplanationDialog>>> = const { RefCell::new(None) };
}

fn label(parent: &Dialog, text: &str) -> StaticText {
    StaticText::builder(parent).with_label(text).build()
}

fn restyle(label: &StaticText, edit: impl FnOnce(&mut Font)) {
    if let Some(mut font) = label.get_font() {
        edit(&mut font);
        label.set_font(&font);
    }
}

fn italic(label: &StaticText) {
    restyle(label, |f| f.set_style(FontStyle::Italic));
}

/// `wx.Gauge.Pulse`: wxMSW switches the progress bar to marquee mode once,
/// then steps it.
#[cfg(windows)]
fn pulse(gauge: &Gauge) {
    use std::ffi::c_void;
    #[link(name = "user32")]
    extern "system" {
        fn GetWindowLongW(hwnd: *mut c_void, index: i32) -> i32;
        fn SetWindowLongW(hwnd: *mut c_void, index: i32, value: i32) -> i32;
        fn SendMessageW(hwnd: *mut c_void, msg: u32, wparam: usize, lparam: isize) -> isize;
    }
    const GWL_STYLE: i32 = -16;
    const PBS_MARQUEE: i32 = 0x08;
    const PBM_STEPIT: u32 = 0x0400 + 5;
    const PBM_SETMARQUEE: u32 = 0x0400 + 10;
    let hwnd = gauge.get_handle();
    if hwnd.is_null() {
        return;
    }
    // SAFETY: a live progress-bar HWND and plain integer messages.
    unsafe {
        let style = GetWindowLongW(hwnd, GWL_STYLE);
        if style & PBS_MARQUEE == 0 {
            SetWindowLongW(hwnd, GWL_STYLE, style | PBS_MARQUEE);
            SendMessageW(hwnd, PBM_SETMARQUEE, 1, 0);
        }
        SendMessageW(hwnd, PBM_STEPIT, 0, 0);
    }
}

/// The generic `wxGaugeBase::Pulse` step.
#[cfg(not(windows))]
fn pulse(gauge: &Gauge) {
    gauge.set_value((gauge.get_value() + 1) % 100);
}

/// `LoadingDialog`: returns the dialog and its pulse timer. Cancel, Escape
/// and the close box cancel `cancel` and end the dialog with ID_CANCEL.
fn loading_dialog(parent: &Frame, location: &str, cancel: CancelToken) -> (Dialog, Timer<Dialog>) {
    let dialog = Dialog::builder(parent, LOADING_TITLE)
        .with_style(DialogStyle::DefaultDialogStyle)
        .with_size(350, 150)
        .build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();
    let loading = label(&dialog, &loading_text(location));
    sizer.add(
        &loading,
        0,
        SizerFlag::All | SizerFlag::AlignCenterHorizontal,
        15,
    );
    let gauge = Gauge::builder(&dialog)
        .with_range(100)
        .with_size(Size::new(200, 20))
        .build();
    pulse(&gauge);
    sizer.add(
        &gauge,
        0,
        SizerFlag::AlignCenterHorizontal | SizerFlag::Left | SizerFlag::Right,
        15,
    );
    let status = label(&dialog, PLEASE_WAIT);
    italic(&status);
    sizer.add(
        &status,
        0,
        SizerFlag::All | SizerFlag::AlignCenterHorizontal,
        10,
    );
    let cancel_btn = Button::builder(&dialog)
        .with_id(ID_CANCEL)
        .with_label(CANCEL_LABEL)
        .build();
    sizer.add(
        &cancel_btn,
        0,
        SizerFlag::AlignCenterHorizontal | SizerFlag::Bottom,
        10,
    );
    dialog.set_sizer(sizer, true);

    let on_cancel = Rc::new(move || {
        tracing::info!("User cancelled explanation generation");
        cancel.cancel();
        status.set_label(CANCELLING);
        cancel_btn.enable(false);
        dialog.end_modal(ID_CANCEL);
    });
    let on_click = on_cancel.clone();
    cancel_btn.on_click(move |_| on_click());
    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            on_cancel();
        } else {
            e.skip(true);
        }
    });

    let timer = Timer::new(&dialog);
    timer.on_tick(move |_| pulse(&gauge));
    timer.start(50, false);
    (dialog, timer)
}

/// View > Explain Weather (Ctrl+E) and Explain Conditions:
/// `show_explanation_dialog`.
pub(crate) fn show_explanation_dialog() {
    let (Some(w), Some(request)) = (window(), Request::current()) else {
        return;
    };
    let warn = |message: &str| {
        message_box(
            &w.frame,
            message,
            ERROR_CAPTION,
            MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
        );
    };
    let Some(name) = request.location.as_ref().map(|l| l.name.clone()) else {
        warn(NO_LOCATION);
        return;
    };
    if !request
        .weather
        .as_ref()
        .is_some_and(|d| d.current.is_some())
    {
        warn(NO_WEATHER);
        return;
    }

    let cancel = CancelToken::new();
    let (loading, timer) = loading_dialog(&w.frame, &name, cancel.clone());
    LOADING.with(|l| *l.borrow_mut() = Some((loading, None)));
    spawn_generation(request, name.clone(), cancel.clone(), |outcome| {
        let dialog = LOADING.with(|l| {
            let mut l = l.borrow_mut();
            let (dialog, slot) = l.as_mut()?;
            *slot = Some(outcome);
            Some(*dialog)
        });
        if let Some(dialog) = dialog {
            dialog.end_modal(ID_OK);
        }
    });

    let code = loading.show_modal();
    timer.stop();
    drop(timer);
    let outcome = LOADING.with(|l| l.borrow_mut().take()).and_then(|(_, o)| o);
    loading.destroy();
    match outcome {
        _ if code == ID_CANCEL => cancel.cancel(),
        Some(Ok(result)) => {
            tracing::info!(
                "Generated weather explanation for {name} (tokens: {}, cached: {})",
                result.token_count,
                result.cached
            );
            show_result_dialog(&w.frame, &result, &name);
        }
        Some(Err(message)) => {
            message_box(
                &w.frame,
                &message,
                ERROR_CAPTION,
                MessageDialogStyle::OK | MessageDialogStyle::IconError,
            );
        }
        None => cancel.cancel(),
    }
}

/// `ExplanationDialog`.
struct ExplanationDialog {
    location: String,
    timestamp_label: StaticText,
    text_ctrl: TextCtrl,
    model_info: TextCtrl,
    regenerate_btn: Button,
    /// Cancelled when the dialog closes, dropping a pending regeneration.
    cancel: CancelToken,
}

fn show_result_dialog(parent: &Frame, result: &ExplanationResult, location: &str) {
    let dialog = Dialog::builder(parent, &dialog_title(location))
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(550, 450)
        .build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();

    let header = label(&dialog, &header_text(location));
    restyle(&header, |f| {
        f.set_weight(FontWeight::Bold);
        f.set_point_size(f.get_point_size() + 2);
    });
    sizer.add(&header, 0, SizerFlag::All, 10);
    let timestamp_label = label(&dialog, &generated_label(result));
    italic(&timestamp_label);
    sizer.add(
        &timestamp_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );

    sizer.add(
        &label(&dialog, EXPLANATION_LABEL),
        0,
        SizerFlag::Left | SizerFlag::Right,
        10,
    );
    let text_ctrl = TextCtrl::builder(&dialog)
        .with_value(explanation_text(result))
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::WordWrap)
        .build();
    sizer.add(
        &text_ctrl,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        10,
    );

    sizer.add(
        &label(&dialog, MODEL_INFO_LABEL),
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );
    let model_info = TextCtrl::builder(&dialog)
        .with_value(&result.explanation_info())
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly)
        .with_size(Size::new(-1, 80))
        .build();
    model_info.set_name(MODEL_INFO_NAME);
    sizer.add(
        &model_info,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        10,
    );

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    let regenerate_btn = Button::builder(&dialog)
        .with_label(REGENERATE_LABEL)
        .build();
    buttons.add(&regenerate_btn, 0, SizerFlag::Right, 5);
    buttons.add_stretch_spacer(1);
    let close = Button::builder(&dialog)
        .with_id(ID_CLOSE)
        .with_label(CLOSE_LABEL)
        .build();
    close.on_click(move |_| dialog.end_modal(ID_OK));
    buttons.add(&close, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 10);
    dialog.set_sizer(sizer, true);
    text_ctrl.set_focus();

    let view = Rc::new(ExplanationDialog {
        location: location.to_string(),
        timestamp_label,
        text_ctrl,
        model_info,
        regenerate_btn,
        cancel: CancelToken::new(),
    });
    let on_regenerate = view.clone();
    regenerate_btn.on_click(move |_| on_regenerate.regenerate());
    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            dialog.close(false);
        } else {
            e.skip(true);
        }
    });

    OPEN.with(|o| *o.borrow_mut() = Some(view.clone()));
    dialog.show_modal();
    view.cancel.cancel();
    OPEN.with(|o| o.borrow_mut().take());
    dialog.destroy();
}

fn with_open(f: impl FnOnce(&ExplanationDialog)) {
    if let Some(view) = OPEN.with(|o| o.borrow().clone()) {
        f(&view);
    }
}

impl ExplanationDialog {
    /// `_on_regenerate`: clear the shared cache and explain again in place.
    fn regenerate(&self) {
        let Some(request) = Request::current() else {
            return;
        };
        request.cache.clear();
        self.regenerate_btn.enable(false);
        self.text_ctrl.set_value(GENERATING);
        self.model_info.set_value("");
        self.timestamp_label.set_label(REGENERATING);
        let location_name = request
            .location
            .as_ref()
            .map_or_else(|| self.location.clone(), |l| l.name.clone());
        spawn_generation(request, location_name, self.cancel.clone(), |outcome| {
            with_open(|view| match outcome {
                Ok(result) => view.regenerated(&result),
                Err(message) => view.regenerate_failed(&message),
            });
        });
    }

    /// `_on_regenerate_complete`.
    fn regenerated(&self, result: &ExplanationResult) {
        self.text_ctrl.set_value(explanation_text(result));
        self.timestamp_label.set_label(&generated_label(result));
        self.model_info.set_value(&result.explanation_info());
        self.regenerate_btn.enable(true);
        self.text_ctrl.set_focus();
    }

    /// `_on_regenerate_error`.
    fn regenerate_failed(&self, error: &str) {
        self.text_ctrl.set_value(&regenerate_failed_text(error));
        self.regenerate_btn.enable(true);
        self.text_ctrl.set_focus();
        crate::screen_reader::announce(&regenerate_failed_announcement(error));
    }
}

#[cfg(test)]
mod tests {
    //! Golden parity with `explanation_dialog.py`, generated by
    //! `rust/tools/golden/aiui.py`.

    use chrono::{DateTime, Local, TimeZone};
    use serde_json::{json, Value};

    use super::*;

    fn golden() -> Value {
        serde_json::from_str(include_str!("../../../../testdata/golden/aiui/cases.json")).unwrap()
    }

    fn result(case: &Value) -> ExplanationResult {
        // Python formats the timestamp's own wall-clock time.
        let stamp = DateTime::parse_from_rfc3339(case["timestamp"].as_str().unwrap()).unwrap();
        ExplanationResult {
            text: case["text"].as_str().unwrap().into(),
            model_used: case["model_used"].as_str().unwrap().into(),
            token_count: case["token_count"].as_u64().unwrap(),
            estimated_cost: case["estimated_cost"].as_f64(),
            cached: case["cached"].as_bool().unwrap(),
            timestamp: Local
                .from_local_datetime(&stamp.naive_local())
                .single()
                .unwrap(),
            requested_model: None,
            model_attempts: Vec::new(),
            model_selection_reason: None,
        }
    }

    fn text_label(text: &str, bold: bool, italic: bool) -> Value {
        json!({"kind": "label", "label": text, "bold": bold, "italic": italic})
    }

    /// `ExplanationDialog`'s controls in creation order.
    fn explanation_controls(
        location: &str,
        timestamp: &str,
        text: &str,
        info: &str,
        regenerate_enabled: bool,
    ) -> Value {
        json!([
            text_label(&header_text(location), true, false),
            text_label(timestamp, false, true),
            text_label(EXPLANATION_LABEL, false, false),
            {"kind": "text", "name": "text", "value": text},
            text_label(MODEL_INFO_LABEL, false, false),
            {"kind": "text", "name": MODEL_INFO_NAME, "value": info},
            {"kind": "button", "id": "auto", "label": REGENERATE_LABEL, "name": "button", "enabled": regenerate_enabled},
            {"kind": "button", "id": ID_CLOSE, "label": CLOSE_LABEL, "name": "button", "enabled": true},
        ])
    }

    #[test]
    fn explanation_dialog_matches_python() {
        let g = golden();
        let cases = g["explanations"].as_array().unwrap();
        let results: Vec<ExplanationResult> = cases.iter().map(|c| result(&c["result"])).collect();
        for (i, case) in cases.iter().enumerate() {
            let location = case["location"].as_str().unwrap();
            let r = &results[i];
            assert_eq!(case["title"], dialog_title(location));
            assert_eq!(
                case["controls"],
                explanation_controls(
                    location,
                    &generated_label(r),
                    explanation_text(r),
                    &r.explanation_info(),
                    true
                )
            );
            assert_eq!(case["focus"], "text");
            assert_eq!(
                case["regenerating"],
                explanation_controls(location, REGENERATING, GENERATING, "", false)
            );
            let next = &results[(i + 1) % results.len()];
            assert_eq!(
                case["regenerated"],
                explanation_controls(
                    location,
                    &generated_label(next),
                    explanation_text(next),
                    &next.explanation_info(),
                    true
                )
            );
            assert_eq!(case["regenerated_focus"], "text");
            assert_eq!(
                case["failed"],
                explanation_controls(
                    location,
                    &generated_label(next),
                    &regenerate_failed_text(REGENERATE_NO_WEATHER),
                    &next.explanation_info(),
                    true
                )
            );
            assert_eq!(
                case["failed_spoken"],
                json!([regenerate_failed_announcement(REGENERATE_NO_WEATHER)])
            );
        }
    }

    #[test]
    fn loading_dialog_and_messages_match_python() {
        let g = golden();
        let loading = &g["loading"];
        assert_eq!(loading["title"], LOADING_TITLE);
        assert_eq!(
            loading["controls"],
            json!([
                text_label(&loading_text("Philadelphia, Pennsylvania"), false, false),
                {"kind": "gauge", "range": 100},
                text_label(PLEASE_WAIT, false, true),
                {"kind": "button", "id": ID_CANCEL, "label": CANCEL_LABEL, "name": "button", "enabled": true},
            ])
        );
        let messages: Vec<Value> = [(false, NO_LOCATION), (true, NO_WEATHER), (true, NO_WEATHER)]
            .iter()
            .map(|(has_location, message)| {
                json!({"has_location": has_location, "message": message,
                       "caption": ERROR_CAPTION, "icon": "warning"})
            })
            .collect();
        assert_eq!(g["explanation_messages"], json!(messages));
        assert_eq!(g["ids"]["close"], ID_CLOSE);
        assert_eq!(g["ids"]["cancel"], ID_CANCEL);
    }
}
