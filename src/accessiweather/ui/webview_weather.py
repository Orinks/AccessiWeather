"""
WebView-based weather display components for faster UI rendering.

Uses toga.WebView to render current conditions and forecast as HTML,
which is significantly faster than creating many individual Toga widgets.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import toga
from toga.style import Pack

if TYPE_CHECKING:
    from ..display.weather_presenter import (
        CurrentConditionsPresentation,
        ForecastPresentation,
    )

logger = logging.getLogger(__name__)

# Base CSS for weather displays - optimized for accessibility
WEATHER_CSS = """
<style>
    * {
        box-sizing: border-box;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 14px;
        line-height: 1.5;
        margin: 0;
        padding: 10px;
        background: #ffffff;
        color: #1a1a1a;
    }
    h2 {
        font-size: 16px;
        font-weight: bold;
        margin: 12px 0 6px 0;
        color: #0066cc;
    }
    h3 {
        font-size: 14px;
        font-weight: bold;
        margin: 10px 0 4px 0;
    }
    .metric {
        margin: 4px 0;
        padding-left: 8px;
    }
    .metric-label {
        font-weight: 600;
    }
    .trend {
        margin: 4px 0;
        padding-left: 8px;
        color: #555;
    }
    .period {
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #e0e0e0;
    }
    .period:last-child {
        border-bottom: none;
    }
    .period-name {
        font-weight: bold;
        color: #0066cc;
    }
    .period-detail {
        margin: 2px 0;
        padding-left: 12px;
    }
    .hourly-section {
        background: #f5f5f5;
        padding: 8px;
        margin-bottom: 12px;
        border-radius: 4px;
    }
    .hourly-item {
        margin: 4px 0;
        padding-left: 8px;
    }
    .timestamp {
        font-style: italic;
        color: #666;
        margin-top: 10px;
        font-size: 12px;
    }
    .no-data {
        color: #666;
        font-style: italic;
    }
    /* High contrast mode support */
    @media (prefers-contrast: high) {
        body { background: #000; color: #fff; }
        h2, .period-name { color: #ffff00; }
        .trend { color: #ccc; }
        .period { border-bottom-color: #666; }
        .hourly-section { background: #222; }
    }
</style>
"""


def _escape_html(text: str | None) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def render_current_conditions_html(
    presentation: CurrentConditionsPresentation | None,
) -> str:
    """Render current conditions as accessible HTML."""
    if presentation is None:
        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">{WEATHER_CSS}</head>
<body role="main" aria-label="Current weather conditions">
<p class="no-data">No current conditions data available.</p>
</body></html>"""

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        f'<head><meta charset="utf-8">{WEATHER_CSS}</head>',
        '<body role="main" aria-label="Current weather conditions">',
    ]

    # Title and description
    if presentation.title:
        html_parts.append(
            f'<h2 role="heading" aria-level="1">{_escape_html(presentation.title)}</h2>'
        )
    if presentation.description:
        html_parts.append(f"<p>{_escape_html(presentation.description)}</p>")

    # Metrics
    if presentation.metrics:
        html_parts.append('<section aria-label="Weather measurements">')
        for metric in presentation.metrics:
            html_parts.append(
                f'<div class="metric"><span class="metric-label">{_escape_html(metric.label)}:</span> '
                f"{_escape_html(metric.value)}</div>"
            )
        html_parts.append("</section>")

    # Trends
    if presentation.trends:
        html_parts.append('<section aria-label="Weather trends">')
        html_parts.append('<h3 role="heading" aria-level="2">Trends</h3>')
        for trend in presentation.trends:
            html_parts.append(f'<div class="trend">• {_escape_html(trend)}</div>')
        html_parts.append("</section>")

    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def render_forecast_html(presentation: ForecastPresentation | None) -> str:
    """Render forecast as accessible HTML with heading navigation."""
    if presentation is None or not presentation.periods:
        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">{WEATHER_CSS}</head>
<body role="main" aria-label="Weather forecast">
<p class="no-data">No forecast data available.</p>
</body></html>"""

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        f'<head><meta charset="utf-8">{WEATHER_CSS}</head>',
        '<body role="main" aria-label="Weather forecast">',
    ]

    # Hourly summary section
    if presentation.hourly_periods:
        html_parts.append('<section class="hourly-section" aria-label="Next 6 hours forecast">')
        html_parts.append('<h2 role="heading" aria-level="2">Next 6 Hours</h2>')
        for hourly in presentation.hourly_periods:
            parts = [hourly.time]
            if hourly.temperature:
                parts.append(hourly.temperature)
            if hourly.conditions:
                parts.append(hourly.conditions)
            if hourly.wind:
                parts.append(f"Wind {hourly.wind}")
            html_parts.append(f'<div class="hourly-item">{_escape_html(" - ".join(parts))}</div>')
        html_parts.append("</section>")

    # Daily forecast periods
    html_parts.append('<section aria-label="Extended forecast">')
    for period in presentation.periods:
        html_parts.append('<article class="period">')
        html_parts.append(
            f'<h2 role="heading" aria-level="2" class="period-name">'
            f"{_escape_html(period.name)}</h2>"
        )
        if period.temperature:
            html_parts.append(
                f'<div class="period-detail">Temperature: {_escape_html(period.temperature)}</div>'
            )
        if period.conditions:
            html_parts.append(
                f'<div class="period-detail">Conditions: {_escape_html(period.conditions)}</div>'
            )
        if period.wind:
            html_parts.append(f'<div class="period-detail">Wind: {_escape_html(period.wind)}</div>')
        if period.details:
            html_parts.append(f'<div class="period-detail">{_escape_html(period.details)}</div>')
        html_parts.append("</article>")
    html_parts.append("</section>")

    # Generated timestamp
    if presentation.generated_at:
        html_parts.append(
            f'<p class="timestamp">Forecast generated: {_escape_html(presentation.generated_at)}</p>'
        )

    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def create_conditions_webview(height: int = 120) -> toga.WebView:
    """Create a WebView widget for current conditions display."""
    webview = toga.WebView(
        style=Pack(height=height, flex=1),
    )
    # Set initial content
    webview.set_content("about:blank", render_current_conditions_html(None))
    try:
        webview.aria_label = "Current conditions"
        webview.aria_description = (
            "Current weather conditions including temperature, humidity, wind, and pressure"
        )
    except AttributeError:
        pass
    return webview


def create_forecast_webview(height: int = 200) -> toga.WebView:
    """Create a WebView widget for forecast display."""
    webview = toga.WebView(
        style=Pack(height=height, flex=1),
    )
    # Set initial content
    webview.set_content("about:blank", render_forecast_html(None))
    try:
        webview.aria_label = "Forecast"
        webview.aria_description = (
            "Extended weather forecast with heading navigation. "
            "Use heading shortcuts to jump between forecast days."
        )
    except AttributeError:
        pass
    return webview


def update_conditions_webview(
    webview: toga.WebView,
    presentation: CurrentConditionsPresentation | None,
) -> None:
    """Update the conditions WebView with new data."""
    try:
        html = render_current_conditions_html(presentation)
        webview.set_content("about:blank", html)
        logger.debug("Updated conditions WebView")
    except Exception as exc:
        logger.error("Failed to update conditions WebView: %s", exc)


def update_forecast_webview(
    webview: toga.WebView,
    presentation: ForecastPresentation | None,
) -> None:
    """Update the forecast WebView with new data."""
    try:
        html = render_forecast_html(presentation)
        webview.set_content("about:blank", html)
        logger.debug("Updated forecast WebView")
    except Exception as exc:
        logger.error("Failed to update forecast WebView: %s", exc)
