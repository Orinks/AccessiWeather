"""
HTML formatters for weather display.

Generates HTML markup for current conditions and forecast displays
with semantic structure and accessibility attributes.
"""

from __future__ import annotations

from ..weather_presenter import (
    CurrentConditionsPresentation,
    ForecastPresentation,
)

# Base CSS styles for weather displays
_BASE_CSS = """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    color: #333;
    background-color: #fff;
    margin: 0;
    padding: 12px;
}
h1, h2, h3 {
    margin: 0 0 8px 0;
    color: #1a1a1a;
}
h1 { font-size: 18px; }
h2 { font-size: 16px; }
h3 { font-size: 14px; }
.description {
    font-size: 16px;
    font-weight: 500;
    margin-bottom: 12px;
    color: #444;
}
dl {
    margin: 0;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 4px 12px;
}
dt {
    font-weight: 600;
    color: #555;
}
dd {
    margin: 0;
    color: #333;
}
.trends {
    margin-top: 12px;
    padding-top: 8px;
    border-top: 1px solid #e0e0e0;
}
.trends ul {
    margin: 4px 0 0 0;
    padding-left: 20px;
}
.trends li {
    margin-bottom: 4px;
}
article {
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #e8e8e8;
}
article:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
}
.period-name {
    font-weight: 600;
    color: #1a1a1a;
}
.period-temp {
    font-size: 15px;
    font-weight: 500;
}
.period-conditions {
    color: #555;
}
.period-wind {
    color: #666;
    font-size: 13px;
}
.period-details {
    margin-top: 4px;
    color: #555;
    font-size: 13px;
}
.hourly-section {
    margin-bottom: 16px;
    padding: 8px;
    background-color: #f8f8f8;
    border-radius: 4px;
}
.hourly-section h3 {
    margin-bottom: 8px;
}
.hourly-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.hourly-item {
    flex: 1 1 80px;
    min-width: 70px;
    text-align: center;
    padding: 4px;
    background: #fff;
    border-radius: 4px;
    border: 1px solid #e0e0e0;
}
.hourly-time {
    font-weight: 600;
    font-size: 12px;
}
.hourly-temp {
    font-size: 14px;
    font-weight: 500;
}
.hourly-conditions {
    font-size: 11px;
    color: #666;
}
.generated-at {
    margin-top: 12px;
    font-size: 12px;
    color: #888;
    font-style: italic;
}
"""


def _escape_html(text: str | None) -> str:
    """Escape HTML special characters."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def generate_current_conditions_html(
    presentation: CurrentConditionsPresentation | None,
) -> str:
    """
    Generate HTML markup for current conditions display.

    Args:
        presentation: The current conditions presentation object.

    Returns:
        Complete HTML document as a string.

    """
    if presentation is None:
        return _generate_empty_html("No current conditions data available.")

    title = _escape_html(presentation.title)
    description = _escape_html(presentation.description)

    # Build metrics as definition list
    metrics_html = ""
    if presentation.metrics:
        metrics_items = []
        for metric in presentation.metrics:
            label = _escape_html(metric.label)
            value = _escape_html(metric.value)
            metrics_items.append(f"<dt>{label}</dt><dd>{value}</dd>")
        metrics_html = f'<dl aria-label="Weather metrics">\n{"".join(metrics_items)}\n</dl>'

    # Build trends section
    trends_html = ""
    if presentation.trends:
        trend_items = []
        for trend in presentation.trends:
            trend_items.append(f"<li>{_escape_html(trend)}</li>")
        trends_html = f"""
<section class="trends" aria-label="Weather trends">
<h3>Trends</h3>
<ul>
{"".join(trend_items)}
</ul>
</section>"""

    body_content = f'''
<article role="region" aria-label="{title}">
<h1>{title}</h1>
<p class="description" aria-live="polite">{description}</p>
{metrics_html}
{trends_html}
</article>
'''

    return _wrap_html_document(body_content, "Current Conditions")


def generate_forecast_html(presentation: ForecastPresentation | None) -> str:
    """
    Generate HTML markup for forecast display.

    Args:
        presentation: The forecast presentation object.

    Returns:
        Complete HTML document as a string.

    """
    if presentation is None:
        return _generate_empty_html("No forecast data available.")

    title = _escape_html(presentation.title)

    # Build hourly section if available
    hourly_html = ""
    if presentation.hourly_periods:
        hourly_items = []
        for period in presentation.hourly_periods:
            time_str = _escape_html(period.time)
            temp = _escape_html(period.temperature) if period.temperature else ""
            conditions = _escape_html(period.conditions) if period.conditions else ""
            hourly_items.append(f"""
<div class="hourly-item" role="listitem">
<div class="hourly-time">{time_str}</div>
<div class="hourly-temp">{temp}</div>
<div class="hourly-conditions">{conditions}</div>
</div>""")
        hourly_html = f"""
<section class="hourly-section" aria-label="Next 6 hours forecast">
<h3>Next 6 Hours</h3>
<div class="hourly-grid" role="list">
{"".join(hourly_items)}
</div>
</section>"""

    # Build forecast periods
    periods_html = ""
    if presentation.periods:
        period_items = []
        for period in presentation.periods:
            name = _escape_html(period.name)
            temp = _escape_html(period.temperature) if period.temperature else "N/A"
            conditions = _escape_html(period.conditions) if period.conditions else ""
            wind = _escape_html(period.wind) if period.wind else ""
            details = _escape_html(period.details) if period.details else ""

            wind_html = f'<p class="period-wind">Wind: {wind}</p>' if wind else ""
            details_html = f'<p class="period-details">{details}</p>' if details else ""

            period_items.append(f"""
<article role="region" aria-label="Forecast for {name}">
<h2 class="period-name">{name}</h2>
<p class="period-temp">{temp}</p>
<p class="period-conditions">{conditions}</p>
{wind_html}
{details_html}
</article>""")
        periods_html = "".join(period_items)

    # Generated at timestamp
    generated_html = ""
    if presentation.generated_at:
        generated_html = f"""
<p class="generated-at">Forecast generated: {_escape_html(presentation.generated_at)}</p>"""

    body_content = f'''
<section role="region" aria-label="{title}">
<h1>{title}</h1>
{hourly_html}
{periods_html}
{generated_html}
</section>
'''

    return _wrap_html_document(body_content, "Weather Forecast")


def _generate_empty_html(message: str) -> str:
    """Generate HTML for empty/unavailable data state."""
    escaped_message = _escape_html(message)
    body_content = f"""
<article role="region" aria-label="No data available">
<p>{escaped_message}</p>
</article>
"""
    return _wrap_html_document(body_content, "Weather")


def _wrap_html_document(body_content: str, title: str) -> str:
    """Wrap content in a complete HTML5 document."""
    escaped_title = _escape_html(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escaped_title}</title>
<style>
{_BASE_CSS}
</style>
</head>
<body>
{body_content}
</body>
</html>"""
