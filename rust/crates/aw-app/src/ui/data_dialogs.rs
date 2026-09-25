//! Read-only weather data dialogs, ported from `ui/dialogs/`:
//! `weather_history_dialog.py`, `precipitation_timeline_dialog.py`,
//! `air_quality_dialog.py` and `uv_index_dialog.py`.
//!
//! Each dialog is described by a pure function as its controls in creation
//! (tab) order, golden-tested against the real Python dialogs
//! (`rust/tools/golden/dataui.py`), and then built by [`show`].

use aw_core::display::pyfmt::round_int;
use aw_core::display::time::location_zone;
use aw_core::model::{
    EnvironmentalConditions, MinutelyPrecipitationForecast, MinutelyPrecipitationPoint, Timestamp,
    WeatherData,
};
use aw_core::py::casefold;
use aw_core::py::float_repr as repr_f64;
use aw_core::Location;
use aw_notify::events::minutely::{is_wet, precipitation_type_label};
use wxdragon::prelude::*;

use super::commands::MSG_SELECT_LOCATION_FIRST;
use super::locations::CAPTION_NO_LOCATION;
use super::main_window::{message_box, window};
use crate::app::with_state;

/// A `wx.StaticText`.
#[derive(Debug, Clone, PartialEq)]
struct Label {
    text: String,
    /// `SetName`, where Python sets one.
    name: Option<&'static str>,
    bold: bool,
    /// `GetFont().Scaled(...)`.
    scale: f64,
    gray: bool,
    /// `Wrap(width)`.
    wrap: Option<i32>,
    /// Space above, in pixels.
    gap: i32,
}

/// A read-only multi-line `wx.TextCtrl`.
#[derive(Debug, Clone, PartialEq)]
struct Text {
    value: String,
    name: Option<&'static str>,
    /// 10 pt teletype font.
    mono: bool,
    /// `wx.TE_RICH2`.
    rich: bool,
    /// Initial height (-1 for the default).
    height: i32,
    /// Takes the dialog's spare height.
    grow: bool,
    gap: i32,
}

#[derive(Debug, Clone, PartialEq)]
enum Item {
    Label(Label),
    Text(Text),
}

/// A dialog: its items, then a right-aligned "Close" button.
#[derive(Debug, Clone, PartialEq)]
struct InfoDialog {
    title: String,
    size: (i32, i32),
    items: Vec<Item>,
    /// Index of the item focused initially; `None` focuses Close.
    focus: Option<usize>,
}

fn label(text: impl Into<String>) -> Label {
    Label {
        text: text.into(),
        name: None,
        bold: false,
        scale: 1.0,
        gray: false,
        wrap: None,
        gap: 15,
    }
}

/// A bold section heading (`GetFont().Bold().Scaled(scale)`).
fn heading(text: &str, scale: f64) -> Item {
    Item::Label(Label {
        bold: true,
        scale,
        ..label(text)
    })
}

/// A gray explanatory line (`SYS_COLOUR_GRAYTEXT`).
fn note(text: impl Into<String>, gap: i32) -> Item {
    Item::Label(Label {
        gray: true,
        gap,
        ..label(text)
    })
}

fn text(value: String, name: &'static str) -> Text {
    Text {
        value,
        name: Some(name),
        mono: false,
        rich: false,
        height: -1,
        grow: true,
        gap: 15,
    }
}

/// `strftime("%I:%M %p").lstrip("0")`.
fn clock_time(dt: &Timestamp) -> String {
    dt.format("%I:%M %p")
        .to_string()
        .trim_start_matches('0')
        .to_string()
}

/// "Last updated: 9:05 AM on September 25, 2026".
fn last_updated(dt: &Timestamp) -> String {
    format!(
        "Last updated: {} on {}",
        clock_time(dt),
        dt.format("%B %d, %Y")
    )
}

fn non_empty(s: Option<&str>) -> Option<&str> {
    s.filter(|s| !s.is_empty())
}

// ---------------------------------------------------------------------------
// Weather history (`weather_history_dialog.py`)
// ---------------------------------------------------------------------------

/// `_build_history_sections`: (heading, content) pairs.
///
/// Python's "Weather Trends" section reads `trend_type` and `description`,
/// which `TrendInsight` does not have, so it never appears; nor does the
/// trailing "No Data" fallback, as "Recent Weather History" always does.
fn history_sections(weather: Option<&WeatherData>) -> Vec<(String, String)> {
    let Some(weather) = weather else {
        return vec![(
            "No Data".into(),
            "Weather history data is not available.".into(),
        )];
    };
    let history = &weather.daily_history;
    let recent = if history.is_empty() {
        "Historical data not available.".to_string()
    } else {
        history
            .iter()
            .take(7)
            .map(|period| {
                let date = match &period.start_time {
                    Some(start) => start.format("%A, %b %d").to_string(),
                    None if !period.name.is_empty() => period.name.clone(),
                    None => "Unknown".into(),
                };
                let condition = non_empty(period.short_forecast.as_deref()).unwrap_or("Unknown");
                match period.temperature {
                    Some(t) => format!("{date}: {}°F - {condition}", repr_f64(t)),
                    None => format!("{date}: {condition}"),
                }
            })
            .collect::<Vec<_>>()
            .join("\n")
    };
    let mut sections = vec![("Recent Weather History".to_string(), recent)];

    let current_temp = weather.current.as_ref().and_then(|c| c.temperature_f);
    let yesterday_temp = history.first().and_then(|p| p.temperature);
    if let (Some(now), Some(then)) = (current_temp, yesterday_temp) {
        let diff = now - then;
        let (now, then) = (repr_f64(now), repr_f64(then));
        let comparison = if diff.abs() < 0.5 {
            format!("Current temperature ({now}°F) is about the same as yesterday ({then}°F).")
        } else {
            let direction = if diff > 0.0 { "warmer" } else { "cooler" };
            format!(
                "Current temperature ({now}°F) is {:.1}°F {direction} than yesterday ({then}°F).",
                diff.abs()
            )
        };
        sections.push(("Today vs Yesterday".into(), comparison));
    }
    sections
}

/// `WeatherHistoryDialog`.
fn weather_history_dialog(location_name: &str, sections: &[(String, String)]) -> InfoDialog {
    let content = sections
        .iter()
        .map(|(heading, content)| {
            let content = if content.is_empty() {
                "No data available."
            } else {
                content
            };
            format!("=== {heading} ===\n{content}\n")
        })
        .collect::<Vec<_>>()
        .join("\n");
    InfoDialog {
        title: format!("Weather History - {location_name}"),
        size: (700, 500),
        items: vec![
            heading(&format!("Weather History for {location_name}"), 1.2),
            note(
                "Comparisons against previous days to provide context for current conditions.",
                15,
            ),
            Item::Text(Text {
                mono: true,
                rich: true,
                ..text(content.trim().to_string(), "Weather history text")
            }),
        ],
        focus: Some(2),
    }
}

// ---------------------------------------------------------------------------
// Precipitation timeline (`precipitation_timeline_dialog.py`)
// ---------------------------------------------------------------------------

const MSG_NO_TIMELINE: &str = "Minutely precipitation data is not available for this location yet.";
const CAPTION_NO_TIMELINE: &str = "No Precipitation Timeline Available";

/// `_format_point_conditions`.
fn point_conditions(point: &MinutelyPrecipitationPoint) -> String {
    let mut details = vec![if is_wet(point, 0.0) {
        precipitation_type_label(point.precipitation_type.as_deref()).to_string()
    } else {
        "Dry".to_string()
    }];
    if let Some(probability) = point.precipitation_probability.filter(|p| *p > 0.0) {
        details.push(format!("{}% chance", round_int(probability * 100.0)));
    }
    if let Some(intensity) = point.precipitation_intensity.filter(|i| *i > 0.0) {
        let mut text = format!("{intensity:.3} {}", point.precipitation_intensity_unit);
        if let Some(error) = point.precipitation_intensity_error.filter(|e| *e > 0.0) {
            text = format!(
                "{text} (+/- {error:.3} {})",
                point.precipitation_intensity_error_unit
            );
        }
        details.push(text);
    }
    details.join(" | ")
}

/// `_format_timeline_line`, with the point's time already in the display zone.
fn timeline_line(
    minute_offset: usize,
    point: &MinutelyPrecipitationPoint,
    time: &Timestamp,
) -> String {
    let offset = if minute_offset == 0 {
        "Now".to_string()
    } else {
        format!("+{minute_offset:02}m")
    };
    let time = clock_time(time);
    format!("{offset:<6}  {time:<8}  {}", point_conditions(point))
}

/// `build_precipitation_timeline_text`.
fn precipitation_timeline_text(
    forecast: &MinutelyPrecipitationForecast,
    timezone_name: Option<&str>,
) -> String {
    let zone = location_zone(timezone_name);
    let zone_label = match (zone, timezone_name) {
        (Some(_), Some(name)) => name,
        _ => "forecast time",
    };
    let mut lines = vec![
        "Offset  Time      Conditions".to_string(),
        "------  --------  ----------".to_string(),
    ];
    if forecast.points.is_empty() {
        lines.push("No minutely precipitation data available.".into());
    }
    lines.extend(forecast.points.iter().enumerate().map(|(i, point)| {
        let time = match zone {
            Some(tz) => point.time.with_timezone(&tz).fixed_offset(),
            None => point.time,
        };
        timeline_line(i, point, &time)
    }));
    format!("Times shown in {zone_label}.\n\n{}", lines.join("\n"))
}

/// `PrecipitationTimelineDialog`.
fn precipitation_timeline_dialog(
    location_name: &str,
    forecast: &MinutelyPrecipitationForecast,
    timezone_name: Option<&str>,
) -> InfoDialog {
    let summary = non_empty(forecast.summary.as_deref())
        .unwrap_or("No summary available.")
        .trim();
    let wrapped = |label: Label| {
        Item::Label(Label {
            wrap: Some(650),
            ..label
        })
    };
    InfoDialog {
        title: format!("Precipitation Timeline - {location_name}"),
        size: (720, 540),
        items: vec![
            heading(&format!("Precipitation Timeline for {location_name}"), 1.2),
            wrapped(Label {
                gray: true,
                ..label(
                    "Pirate Weather short-range precipitation guidance for the next hour. \
                     Minute rows are model-interpolated guidance.",
                )
            }),
            heading("Summary", 1.05),
            wrapped(Label {
                name: Some("Precipitation summary"),
                ..label(summary)
            }),
            heading("Minute-by-minute timeline", 1.05),
            Item::Text(Text {
                mono: true,
                rich: true,
                ..text(
                    precipitation_timeline_text(forecast, timezone_name),
                    "Precipitation timeline text",
                )
            }),
        ],
        focus: Some(5),
    }
}

// ---------------------------------------------------------------------------
// Air quality (`air_quality_dialog.py`)
// ---------------------------------------------------------------------------

/// `_AIR_QUALITY_GUIDANCE`, with `_DEFAULT_AIR_QUALITY_GUIDANCE`.
fn air_quality_guidance(category: &str) -> &'static str {
    match category {
        "Good" => "Air quality is satisfactory. No precautions needed.",
        "Moderate" => {
            "Unusually sensitive people should consider limiting prolonged outdoor exertion."
        }
        "Unhealthy for Sensitive Groups" => {
            "People with respiratory conditions, children, and older adults should limit \
             prolonged outdoor exertion."
        }
        "Unhealthy" => "Everyone should limit prolonged outdoor exertion.",
        "Very Unhealthy" => "Everyone should avoid prolonged outdoor exertion.",
        "Hazardous" => "Everyone should avoid all outdoor exertion. Stay indoors.",
        _ => "Check current local air quality guidance before prolonged outdoor activity.",
    }
}

/// `_POLLUTANT_LABELS` (keys are upper-case pollutant codes).
fn pollutant_label(code: &str) -> Option<&'static str> {
    Some(match code {
        "PM2_5" => "PM2.5 (Fine Particles)",
        "PM10" => "PM10 (Coarse Particles)",
        "O3" | "OZONE" => "Ozone",
        "NO2" => "Nitrogen Dioxide",
        "SO2" => "Sulfur Dioxide",
        "CO" => "Carbon Monoxide",
        _ => return None,
    })
}

/// `", ".join(dict.fromkeys(items))`.
fn join_unique(items: &[&str]) -> String {
    let mut seen: Vec<&str> = Vec::new();
    for item in items {
        if !seen.contains(item) {
            seen.push(item);
        }
    }
    seen.join(", ")
}

/// `_build_summary_section`: the "Current air quality summary" text.
fn air_quality_summary(env: &EnvironmentalConditions) -> String {
    let category = non_empty(env.air_quality_category.as_deref());
    let aqi = env
        .air_quality_index
        .map(|aqi| format!("AQI: {}", round_int(aqi)));
    let mut lines = vec![match (aqi, category) {
        (Some(aqi), Some(category)) => format!("{aqi} ({category})"),
        (Some(aqi), None) => aqi,
        (None, Some(category)) => category.to_string(),
        (None, None) => "AQI: Not available".into(),
    }];

    lines.push(match non_empty(env.air_quality_pollutant.as_deref()) {
        Some(pollutant) => format!(
            "Dominant pollutant: {}",
            pollutant_label(&pollutant.to_uppercase()).unwrap_or(pollutant)
        ),
        None => "Dominant pollutant: Not available".into(),
    });
    lines.push(format!(
        "Health guidance: {}",
        air_quality_guidance(category.unwrap_or(""))
    ));
    lines.push(
        match env
            .air_quality_updated_at
            .as_ref()
            .or(env.updated_at.as_ref())
        {
            Some(updated) => last_updated(updated),
            None => "Last updated: Not available".into(),
        },
    );
    if let Some(area) = non_empty(env.air_quality_reporting_area.as_deref().map(str::trim)) {
        lines.push(format!("Reporting area: {area}"));
    }

    let current_source = non_empty(env.air_quality_source.as_deref().map(str::trim));
    let sources: Vec<&str> = env
        .sources
        .iter()
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .collect();
    let is_airnow = |s: &str| casefold(s).contains("airnow");
    if current_source.is_some_and(is_airnow) || sources.iter().any(|s| is_airnow(s)) {
        lines.push("Source: EPA AirNow and participating air quality agencies".into());
        let hourly_sources: Vec<&str> = sources
            .iter()
            .copied()
            .filter(|s| !is_airnow(s) && casefold(s).contains("air quality"))
            .collect();
        if !hourly_sources.is_empty() {
            lines.push(format!(
                "Hourly forecast and pollutant concentrations: {}",
                join_unique(&hourly_sources)
            ));
        }
        lines.push("Status: Preliminary data; values may change after quality control.".into());
    } else if let Some(source) = current_source {
        lines.push(format!("Source: {source}"));
    } else if !sources.is_empty() {
        lines.push(format!("Source: {}", join_unique(&sources)));
    } else {
        lines.push("Source: Not available".into());
    }
    lines.join("\n")
}

/// `_build_pollutant_section`: the first hour's measurements.
fn pollutant_levels(env: &EnvironmentalConditions) -> Option<String> {
    let current = env.hourly_air_quality.first()?;
    let dominant = non_empty(env.air_quality_pollutant.as_deref()).map(str::to_uppercase);
    let lines: Vec<String> = [
        ("PM2_5", current.pm2_5),
        ("PM10", current.pm10),
        ("O3", current.ozone),
        ("NO2", current.nitrogen_dioxide),
        ("SO2", current.sulphur_dioxide),
        ("CO", current.carbon_monoxide),
    ]
    .into_iter()
    .filter_map(|(code, value)| {
        let value = value?;
        let name = pollutant_label(code).unwrap_or(code);
        let marker = if dominant.as_deref() == Some(code) {
            " (dominant)"
        } else {
            ""
        };
        Some(format!("{name}: {value:.1} µg/m³{marker}"))
    })
    .collect();
    Some(if lines.is_empty() {
        "No measurements available.".into()
    } else {
        lines.join("\n")
    })
}

/// `AirQualityDialog`.
fn air_quality_dialog(location_name: &str, env: Option<&EnvironmentalConditions>) -> InfoDialog {
    let title = format!("Air Quality - {location_name}");
    let Some(env) = env.filter(|e| e.has_data()) else {
        return InfoDialog {
            title,
            size: (600, 500),
            items: vec![Item::Label(Label {
                scale: 1.1,
                gap: 20,
                ..label("Air quality data is not available for this location.")
            })],
            focus: None,
        };
    };
    let hourly: Vec<String> = env
        .hourly_air_quality
        .iter()
        .take(12)
        .map(|hour| format!("{}: AQI {}", clock_time(&hour.timestamp), hour.aqi))
        .collect();
    let section_text = |value: Option<String>, name, missing| match value {
        Some(value) => Item::Text(Text {
            height: 100,
            gap: 8,
            ..text(value, name)
        }),
        None => note(missing, 8),
    };
    InfoDialog {
        title,
        size: (600, 500),
        items: vec![
            heading("Current Air Quality", 1.1),
            Item::Text(Text {
                height: 150,
                grow: false,
                gap: 8,
                ..text(air_quality_summary(env), "Current air quality summary")
            }),
            heading("Hourly Forecast", 1.1),
            section_text(
                (!hourly.is_empty()).then(|| hourly.join("\n")),
                "Hourly Forecast",
                "Hourly forecast data is not available.",
            ),
            heading("Current Pollutant Levels", 1.1),
            section_text(
                pollutant_levels(env),
                "Current Pollutant Levels",
                "Pollutant data is not available.",
            ),
        ],
        focus: Some(1),
    }
}

// ---------------------------------------------------------------------------
// UV index (`uv_index_dialog.py`)
// ---------------------------------------------------------------------------

/// `_UV_INDEX_GUIDANCE`, with its fallback.
fn uv_guidance(category: &str) -> &'static str {
    match category {
        "Low" => "No protection needed. You can safely stay outside.",
        "Moderate" => "Seek shade during midday hours. Wear protective clothing.",
        "High" => {
            "Reduce time in the sun between 10am and 4pm. Seek shade, wear protective clothing."
        }
        "Very High" => "Take extra precautions. Minimize sun exposure between 10am and 4pm.",
        "Extreme" => {
            "Try to avoid sun exposure between 10am and 4pm. Shirt, sunscreen, and hat are \
             essential."
        }
        _ => "Monitor UV levels and use sun protection as needed.",
    }
}

/// `_UV_SUN_SAFETY`.
fn sun_safety(category: &str) -> Option<&'static str> {
    Some(match category {
        "Low" => {
            "• SPF 15+ sunscreen for extended outdoor activities\n\
             • Sunglasses on bright days\n\
             • No special precautions needed for most people"
        }
        "Moderate" => {
            "• SPF 30+ sunscreen, reapply every 2 hours\n\
             • Wear sunglasses and a wide-brimmed hat\n\
             • Seek shade during midday hours\n\
             • Cover up with clothing when possible"
        }
        "High" => {
            "• SPF 30+ sunscreen is essential\n\
             • Wear protective clothing, hat, and sunglasses\n\
             • Seek shade, especially during midday\n\
             • Limit time in direct sun between 10am-4pm\n\
             • Stay hydrated"
        }
        "Very High" => {
            "• SPF 50+ sunscreen, reapply frequently\n\
             • Protective clothing, wide-brimmed hat, UV-blocking sunglasses\n\
             • Stay in shade whenever possible\n\
             • Minimize outdoor activities between 10am-4pm\n\
             • Extra caution for children and sensitive skin"
        }
        "Extreme" => {
            "• AVOID outdoor activities between 10am-4pm if possible\n\
             • SPF 50+ sunscreen is critical, reapply every 1-2 hours\n\
             • Full protective clothing, hat, and sunglasses required\n\
             • Seek air-conditioned spaces\n\
             • Watch for signs of heat illness\n\
             • Extremely high risk of skin and eye damage"
        }
        _ => return None,
    })
}

/// `UVIndexDialog`.
fn uv_index_dialog(location_name: &str, env: Option<&EnvironmentalConditions>) -> InfoDialog {
    let title = format!("UV Index - {location_name}");
    let Some(env) = env.filter(|e| e.has_data()) else {
        return InfoDialog {
            title,
            size: (600, 500),
            items: vec![Item::Label(Label {
                scale: 1.1,
                gap: 20,
                ..label("UV index data is not available for this location.")
            })],
            focus: None,
        };
    };
    let category = non_empty(env.uv_category.as_deref());
    let mut items = vec![heading("Current UV Index", 1.1)];
    // The summary lines sit 8 px under the heading and 4 px apart.
    let mut gap = 8;
    let uv = env
        .uv_index
        .map(|uv| format!("UV Index: {}", round_int(uv)));
    let uv_text = match (uv, category) {
        (Some(uv), Some(category)) => Some(format!("{uv} ({category})")),
        (Some(uv), None) => Some(uv),
        (None, category) => category.map(str::to_string),
    };
    if let Some(uv_text) = uv_text {
        items.push(Item::Label(Label {
            scale: 1.05,
            gap,
            ..label(uv_text)
        }));
        gap = 4;
    }
    items.push(Item::Label(Label {
        gray: true,
        wrap: Some(550),
        gap,
        ..label(format!(
            "Health guidance: {}",
            uv_guidance(category.unwrap_or(""))
        ))
    }));
    if let Some(updated) = &env.updated_at {
        items.push(note(last_updated(updated), 4));
    }

    items.push(heading("Hourly Forecast", 1.1));
    let mut focus = None;
    if env.hourly_uv_index.is_empty() {
        items.push(note("Hourly forecast data is not available.", 8));
    } else {
        // Python reads `hour.time`, which `HourlyUVIndex` lacks, so every
        // row is labelled "Hour N" rather than with its timestamp.
        let lines: Vec<String> = env
            .hourly_uv_index
            .iter()
            .take(12)
            .enumerate()
            .map(|(i, hour)| format!("Hour {}: UV {}", i + 1, round_int(hour.uv_index)))
            .collect();
        focus = Some(items.len());
        items.push(Item::Text(Text {
            height: 100,
            gap: 8,
            ..text(lines.join("\n"), "Hourly Forecast")
        }));
    }

    items.push(heading("Sun Safety Recommendations", 1.1));
    items.push(match category.and_then(sun_safety) {
        Some(recommendations) => Item::Text(Text {
            height: 100,
            gap: 8,
            ..text(recommendations.to_string(), "Sun Safety Recommendations")
        }),
        None => note("Sun safety recommendations are not available.", 8),
    });
    InfoDialog {
        title,
        size: (600, 500),
        items,
        focus,
    }
}

// ---------------------------------------------------------------------------
// Showing the dialogs
// ---------------------------------------------------------------------------

/// Build `spec` over `parent`, run it modally and destroy it.
fn show(parent: &dyn WxWidget, spec: &InfoDialog) {
    let dialog = Dialog::builder(parent, &spec.title)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(spec.size.0, spec.size.1)
        .build();
    let panel = Panel::builder(&dialog).build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();
    let mut focus = None;
    for (i, item) in spec.items.iter().enumerate() {
        match item {
            Item::Label(l) => {
                sizer.add_spacer(l.gap);
                let ctrl = StaticText::builder(&panel).with_label(&l.text).build();
                if let Some(mut font) = ctrl.get_font() {
                    if l.bold {
                        font.make_bold();
                    }
                    let size = f64::from(font.get_point_size()) * l.scale;
                    font.set_point_size(size.round() as i32);
                    ctrl.set_font(&font);
                }
                if l.gray {
                    ctrl.set_foreground_color(SystemSettings::get_colour(SystemColour::GrayText));
                }
                if let Some(width) = l.wrap {
                    ctrl.wrap(width);
                }
                if let Some(name) = l.name {
                    ctrl.set_name(name);
                }
                sizer.add(&ctrl, 0, SizerFlag::Left | SizerFlag::Right, 15);
            }
            Item::Text(t) => {
                sizer.add_spacer(t.gap);
                let mut style = TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly;
                if t.rich {
                    style |= TextCtrlStyle::Rich2;
                }
                let ctrl = TextCtrl::builder(&panel)
                    .with_value(&t.value)
                    .with_style(style)
                    .with_size(Size::new(-1, t.height))
                    .build();
                if t.mono {
                    let font = Font::new_with_details(
                        10,
                        FontFamily::Teletype.as_i32(),
                        FontStyle::Normal.as_i32(),
                        FontWeight::Normal.as_i32(),
                        false,
                        "",
                    );
                    if let Some(font) = font {
                        ctrl.set_font(&font);
                    }
                }
                if let Some(name) = t.name {
                    ctrl.set_name(name);
                }
                let flags = SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right;
                sizer.add(&ctrl, i32::from(t.grow), flags, 15);
                if spec.focus == Some(i) {
                    focus = Some(ctrl);
                }
            }
        }
    }

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    buttons.add_stretch_spacer(1);
    let close = Button::builder(&panel)
        .with_id(ID_CLOSE)
        .with_label("Close")
        .build();
    close.on_click(move |_| dialog.end_modal(ID_CLOSE));
    buttons.add(&close, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 15);
    panel.set_sizer(sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);
    match focus {
        Some(ctrl) => ctrl.set_focus(),
        None => close.set_focus(),
    }

    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            dialog.end_modal(ID_CLOSE);
        } else {
            e.skip(true);
        }
    });
    dialog.show_modal();
    dialog.destroy();
}

/// The main window, the current location and `app.current_weather_data`,
/// or Python's "Please select a location first." warning.
fn context() -> Option<(Frame, Location, Option<WeatherData>)> {
    let w = window()?;
    let (location, weather) = {
        let state = with_state()?;
        let st = state.borrow();
        (
            st.config.current_location.clone(),
            st.current_weather_data.clone(),
        )
    };
    let Some(location) = location else {
        message_box(
            &w.frame,
            MSG_SELECT_LOCATION_FIRST,
            CAPTION_NO_LOCATION,
            MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
        );
        return None;
    };
    Some((w.frame, location, weather))
}

/// View > Weather History (Ctrl+H): `show_weather_history_dialog`.
pub(crate) fn show_weather_history() {
    let Some((frame, location, weather)) = context() else {
        return;
    };
    let sections = history_sections(weather.as_ref());
    show(&frame, &weather_history_dialog(&location.name, &sections));
}

/// View > Precipitation Timeline: `show_precipitation_timeline_dialog`.
pub(crate) fn show_precipitation_timeline() {
    let Some((frame, location, weather)) = context() else {
        return;
    };
    let Some(forecast) = weather
        .and_then(|w| w.minutely_precipitation)
        .filter(MinutelyPrecipitationForecast::has_data)
    else {
        message_box(
            &frame,
            MSG_NO_TIMELINE,
            CAPTION_NO_TIMELINE,
            MessageDialogStyle::OK | MessageDialogStyle::IconInformation,
        );
        return;
    };
    let spec =
        precipitation_timeline_dialog(&location.name, &forecast, location.timezone.as_deref());
    show(&frame, &spec);
}

/// View > Air Quality: `show_air_quality_dialog`.
pub(crate) fn show_air_quality() {
    let Some((frame, location, weather)) = context() else {
        return;
    };
    let env = weather.and_then(|w| w.environmental);
    show(&frame, &air_quality_dialog(&location.name, env.as_ref()));
}

/// View > UV Index: `show_uv_index_dialog`.
pub(crate) fn show_uv_index() {
    let Some((frame, location, weather)) = context() else {
        return;
    };
    let env = weather.and_then(|w| w.environmental);
    show(&frame, &uv_index_dialog(&location.name, env.as_ref()));
}

#[cfg(test)]
mod tests {
    //! Golden parity with the Python dialogs, generated by
    //! `rust/tools/golden/dataui.py`.

    use aw_core::model::{CurrentConditions, ForecastPeriod, TrendInsight};
    use serde_json::{json, Value};

    use super::*;

    fn golden() -> Value {
        serde_json::from_str(include_str!(
            "../../../../testdata/golden/dataui/cases.json"
        ))
        .unwrap()
    }

    fn from<T: serde::de::DeserializeOwned>(v: &Value) -> T {
        serde_json::from_value(v.clone()).unwrap()
    }

    /// The controls the Python generator records, in creation order.
    fn controls(spec: &InfoDialog) -> Value {
        let mut out: Vec<Value> = spec
            .items
            .iter()
            .map(|item| match item {
                Item::Label(l) => json!({
                    "kind": "label", "label": l.text, "name": l.name.unwrap_or("staticText"),
                    "bold": l.bold, "scale": l.scale, "gray": l.gray, "wrap": l.wrap,
                }),
                Item::Text(t) => json!({
                    "kind": "text", "name": t.name.unwrap_or("text"), "value": t.value,
                    "mono": t.mono, "password": false,
                }),
            })
            .collect();
        out.push(json!({"kind": "button", "id": ID_CLOSE, "label": "Close", "name": "button"}));
        Value::Array(out)
    }

    fn assert_dialog(spec: &InfoDialog, expected: &Value, case: &str) {
        assert_eq!(spec.title, expected["title"], "{case}");
        assert_eq!(controls(spec), expected["controls"], "{case}");
        let focus = spec.focus.unwrap_or(spec.items.len());
        assert_eq!(
            focus,
            expected["focus"].as_u64().unwrap() as usize,
            "{case}"
        );
    }

    #[test]
    fn weather_history_matches_python() {
        for case in golden()["history"].as_array().unwrap() {
            let name = case["name"].as_str().unwrap();
            let weather = case["weather"].as_object().map(|w| WeatherData {
                current: from::<Option<CurrentConditions>>(&w["current"]),
                daily_history: from::<Vec<ForecastPeriod>>(&w["daily_history"]),
                trend_insights: from::<Vec<TrendInsight>>(&w["trend_insights"]),
                ..Default::default()
            });
            let sections = history_sections(weather.as_ref());
            assert_eq!(
                sections,
                from::<Vec<(String, String)>>(&case["sections"]),
                "{name}"
            );
            let spec = weather_history_dialog(case["location"].as_str().unwrap(), &sections);
            assert_dialog(&spec, case, name);
        }
    }

    #[test]
    fn precipitation_timeline_matches_python() {
        for case in golden()["precipitation"].as_array().unwrap() {
            let name = case["name"].as_str().unwrap();
            let forecast: MinutelyPrecipitationForecast = from(&case["forecast"]);
            let tz = case["timezone"].as_str();
            assert_eq!(
                precipitation_timeline_text(&forecast, tz),
                case["text"],
                "{name}"
            );
            let spec =
                precipitation_timeline_dialog(case["location"].as_str().unwrap(), &forecast, tz);
            assert_dialog(&spec, case, name);
        }
    }

    #[test]
    fn air_quality_and_uv_index_match_python() {
        for case in golden()["environmental"].as_array().unwrap() {
            let name = case["name"].as_str().unwrap();
            let env: Option<EnvironmentalConditions> = from(&case["environmental"]);
            let location = case["location"].as_str().unwrap();
            assert_dialog(
                &air_quality_dialog(location, env.as_ref()),
                &case["air_quality"],
                name,
            );
            assert_dialog(
                &uv_index_dialog(location, env.as_ref()),
                &case["uv_index"],
                name,
            );
        }
    }
}
