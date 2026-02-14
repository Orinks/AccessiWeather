"""Tests for HTML formatters in display/presentation/html_formatters.py."""

from accessiweather.display.presentation.html_formatters import (
    _escape_html,
    _generate_empty_html,
    _wrap_html_document,
    generate_current_conditions_html,
    generate_forecast_html,
)
from accessiweather.display.weather_presenter import (
    CurrentConditionsPresentation,
    ForecastPeriodPresentation,
    ForecastPresentation,
    HourlyPeriodPresentation,
    Metric,
)


class TestEscapeHtml:
    def test_none_returns_empty(self):
        assert _escape_html(None) == ""

    def test_plain_text_unchanged(self):
        assert _escape_html("hello world") == "hello world"

    def test_ampersand(self):
        assert _escape_html("a & b") == "a &amp; b"

    def test_angle_brackets(self):
        assert _escape_html("<script>") == "&lt;script&gt;"

    def test_quotes(self):
        assert _escape_html('"hello\'') == "&quot;hello&#x27;"

    def test_all_special_chars(self):
        result = _escape_html('<a href="x">&\'')
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result
        assert "&quot;" in result
        assert "&#x27;" in result


class TestWrapHtmlDocument:
    def test_basic_structure(self):
        html = _wrap_html_document("<p>Hello</p>", "Test Title")
        assert "<!DOCTYPE html>" in html
        assert '<html lang="en">' in html
        assert "<title>Test Title</title>" in html
        assert "<p>Hello</p>" in html
        assert "</html>" in html

    def test_title_escaped(self):
        html = _wrap_html_document("", "Title <script>")
        assert "<title>Title &lt;script&gt;</title>" in html


class TestGenerateEmptyHtml:
    def test_contains_message(self):
        html = _generate_empty_html("No data")
        assert "No data" in html
        assert 'aria-label="No data available"' in html

    def test_escapes_message(self):
        html = _generate_empty_html("<b>bad</b>")
        assert "&lt;b&gt;bad&lt;/b&gt;" in html


class TestGenerateCurrentConditionsHtml:
    def test_none_returns_empty_state(self):
        html = generate_current_conditions_html(None)
        assert "No current conditions data available" in html

    def test_basic_presentation(self):
        pres = CurrentConditionsPresentation(
            title="Current Weather",
            description="Partly cloudy, 72°F",
        )
        html = generate_current_conditions_html(pres)
        assert "Current Weather" in html
        assert "Partly cloudy" in html
        assert 'aria-label="Current Weather"' in html
        assert 'aria-live="polite"' in html

    def test_with_metrics(self):
        pres = CurrentConditionsPresentation(
            title="Weather",
            description="Clear",
            metrics=[
                Metric(label="Temperature", value="72°F"),
                Metric(label="Humidity", value="45%"),
            ],
        )
        html = generate_current_conditions_html(pres)
        assert 'aria-label="Weather metrics"' in html
        assert "<dt>Temperature</dt>" in html
        assert "<dd>72°F</dd>" in html
        assert "<dt>Humidity</dt>" in html
        assert "<dd>45%</dd>" in html

    def test_with_trends(self):
        pres = CurrentConditionsPresentation(
            title="Weather",
            description="Warm",
            trends=["Rising temps", "Dropping pressure"],
        )
        html = generate_current_conditions_html(pres)
        assert 'aria-label="Weather trends"' in html
        assert "<li>Rising temps</li>" in html
        assert "<li>Dropping pressure</li>" in html

    def test_no_metrics_no_trends(self):
        pres = CurrentConditionsPresentation(title="W", description="D")
        html = generate_current_conditions_html(pres)
        assert "<dl" not in html
        assert "Trends" not in html

    def test_html_escaping_in_values(self):
        pres = CurrentConditionsPresentation(
            title='<script>alert("x")</script>',
            description="A & B",
            metrics=[Metric(label="<b>", value="</b>")],
            trends=["trend & more"],
        )
        html = generate_current_conditions_html(pres)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "A &amp; B" in html


class TestGenerateForecastHtml:
    def test_none_returns_empty_state(self):
        html = generate_forecast_html(None)
        assert "No forecast data available" in html

    def test_basic_forecast(self):
        pres = ForecastPresentation(title="7-Day Forecast")
        html = generate_forecast_html(pres)
        assert "7-Day Forecast" in html

    def test_with_periods(self):
        pres = ForecastPresentation(
            title="Forecast",
            periods=[
                ForecastPeriodPresentation(
                    name="Tonight",
                    temperature="55°F",
                    conditions="Clear",
                    wind="NW 5 mph",
                    details="Low near 55.",
                ),
                ForecastPeriodPresentation(
                    name="Tomorrow",
                    temperature="78°F",
                    conditions="Sunny",
                    wind=None,
                    details=None,
                ),
            ],
        )
        html = generate_forecast_html(pres)
        assert 'aria-label="Forecast for Tonight"' in html
        assert "55°F" in html
        assert "Clear" in html
        assert "Wind: NW 5 mph" in html
        assert "Low near 55." in html
        assert 'aria-label="Forecast for Tomorrow"' in html
        # Tomorrow has no wind or details, so those classes appear only once in content
        # (excluding CSS which also contains the class names)
        # Check the actual HTML elements, not CSS rules
        assert 'Wind: NW 5 mph' in html
        assert "Low near 55." in html

    def test_period_with_no_temp(self):
        pres = ForecastPresentation(
            title="F",
            periods=[
                ForecastPeriodPresentation(
                    name="Tonight", temperature=None, conditions=None, wind=None, details=None
                )
            ],
        )
        html = generate_forecast_html(pres)
        assert "N/A" in html

    def test_with_hourly_periods(self):
        pres = ForecastPresentation(
            title="Forecast",
            hourly_periods=[
                HourlyPeriodPresentation(time="3 PM", temperature="75°F", conditions="Sunny", wind=None),
                HourlyPeriodPresentation(time="4 PM", temperature="74°F", conditions=None, wind=None),
            ],
        )
        html = generate_forecast_html(pres)
        assert "Next 6 Hours" in html
        assert 'aria-label="Next 6 hours forecast"' in html
        assert "3 PM" in html
        assert "75°F" in html
        assert "Sunny" in html
        assert "4 PM" in html

    def test_with_generated_at(self):
        pres = ForecastPresentation(title="F", generated_at="2026-02-14 02:00 UTC")
        html = generate_forecast_html(pres)
        assert "Forecast generated: 2026-02-14 02:00 UTC" in html
        assert "generated-at" in html

    def test_no_generated_at(self):
        pres = ForecastPresentation(title="F")
        html = generate_forecast_html(pres)
        assert "Forecast generated:" not in html

    def test_escaping_in_forecast(self):
        pres = ForecastPresentation(
            title="<Forecast>",
            periods=[
                ForecastPeriodPresentation(
                    name="Day & Night",
                    temperature='50"F',
                    conditions="<cloudy>",
                    wind="N'E",
                    details="Details & more",
                )
            ],
            generated_at="<time>",
        )
        html = generate_forecast_html(pres)
        assert "<Forecast>" not in html
        assert "&lt;Forecast&gt;" in html
        assert "Day &amp; Night" in html
