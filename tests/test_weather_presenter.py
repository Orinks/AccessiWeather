"""Unit tests for WeatherPresenter accuracy-sensitive output."""

from datetime import UTC, datetime, timedelta

import pytest

from accessiweather.display import WeatherPresenter
from accessiweather.models import (
    AppSettings,
    AviationData,
    CurrentConditions,
    EnvironmentalConditions,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
    WeatherData,
)


@pytest.mark.unit
def test_presenter_includes_precise_dewpoint_in_metrics():
    """Presenter should surface dewpoint derived from temperature and humidity."""
    settings = AppSettings(temperature_unit="both")
    presenter = WeatherPresenter(settings)
    location = Location(name="Test City", latitude=40.0, longitude=-75.0)

    conditions = CurrentConditions(
        temperature_f=77.0,
        humidity=65,
        feels_like_f=77.0,
        wind_speed_mph=5.0,
        wind_direction=180,
        pressure_in=30.0,
    )

    presentation = presenter.present_current(conditions, location)

    assert presentation is not None
    dewpoint_metric = next((m for m in presentation.metrics if m.label == "Dewpoint"), None)
    assert dewpoint_metric is not None
    assert "64°F (18°C)" in dewpoint_metric.value
    assert "Dewpoint: 64°F (18°C)" in presentation.fallback_text


@pytest.mark.unit
def test_presenter_includes_moon_metrics_when_available():
    settings = AppSettings(temperature_unit="fahrenheit")
    presenter = WeatherPresenter(settings)
    location = Location(name="Lunar City", latitude=40.0, longitude=-75.0)
    conditions = CurrentConditions(
        temperature_f=72.0,
        condition="Clear",
        moon_phase="Waning Crescent",
        moonrise_time=datetime(2025, 9, 27, 4, 15, tzinfo=UTC),
        moonset_time=datetime(2025, 9, 27, 16, 58, tzinfo=UTC),
    )

    presentation = presenter.present_current(conditions, location)

    assert presentation is not None
    labels = {metric.label for metric in presentation.metrics}
    assert {"Moon phase", "Moonrise", "Moonset"}.issubset(labels)
    fallback = presentation.fallback_text
    assert "Moon phase: Waning Crescent" in fallback
    assert "Moonrise:" in fallback
    assert "Moonset:" in fallback


@pytest.mark.unit
def test_presenter_respects_metric_visibility_preferences():
    settings = AppSettings(
        temperature_unit="both",
        show_dewpoint=False,
        show_visibility=False,
        show_uv_index=False,
    )
    presenter = WeatherPresenter(settings)
    location = Location(name="Hidden Metrics", latitude=35.0, longitude=-80.0)

    conditions = CurrentConditions(
        temperature_f=75.0,
        humidity=60,
        dewpoint_f=60.0,
        dewpoint_c=15.5,
        visibility_miles=8.0,
        visibility_km=12.8,
        uv_index=5.0,
    )

    presentation = presenter.present_current(conditions, location)

    assert presentation is not None
    labels = {metric.label for metric in presentation.metrics}
    assert "Dewpoint" not in labels
    assert "Visibility" not in labels
    assert "UV Index" not in labels
    fallback = presentation.fallback_text
    assert "Dewpoint" not in fallback
    assert "Visibility" not in fallback
    assert "UV Index" not in fallback


@pytest.mark.unit
def test_presenter_reports_calm_wind_when_speed_is_zero():
    settings = AppSettings(temperature_unit="fahrenheit")
    presenter = WeatherPresenter(settings)
    location = Location(name="Calm Town", latitude=0.0, longitude=0.0)
    conditions = CurrentConditions(
        temperature_f=70.0,
        condition="Clear",
        wind_speed_mph=0.0,
        wind_direction=45,
    )

    presentation = presenter.present_current(conditions, location)

    assert presentation is not None
    wind_metric = next((m for m in presentation.metrics if m.label == "Wind"), None)
    assert wind_metric is not None
    assert wind_metric.value == "Calm"
    assert "Wind: Calm" in presentation.fallback_text


@pytest.mark.unit
def test_presenter_includes_environmental_metrics():
    settings = AppSettings(temperature_unit="fahrenheit")
    presenter = WeatherPresenter(settings)
    location = Location(name="Env City", latitude=35.0, longitude=-90.0)
    conditions = CurrentConditions(temperature_f=70.0, condition="Sunny")
    env = EnvironmentalConditions(
        air_quality_index=105,
        air_quality_category="Unhealthy for Sensitive Groups",
        air_quality_pollutant="PM2.5",
        pollen_index=75,
        pollen_category="High",
        pollen_primary_allergen="Tree",
    )

    presentation = presenter.present_current(conditions, location, environmental=env)

    assert presentation is not None
    aq_metric = next((m for m in presentation.metrics if m.label == "Air Quality"), None)
    assert aq_metric is not None
    assert "105" in aq_metric.value
    assert "Advice:" in aq_metric.value
    assert "Air Quality:" in presentation.fallback_text
    pollen_metric = next((m for m in presentation.metrics if m.label == "Pollen"), None)
    assert pollen_metric is not None
    assert "High" in pollen_metric.value


@pytest.mark.unit
def test_presenter_builds_accessible_air_quality_panel():
    settings = AppSettings()
    presenter = WeatherPresenter(settings)
    location = Location(name="AQ Town", latitude=40.0, longitude=-74.0)
    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(condition="Clear", temperature_f=72.0),
        environmental=EnvironmentalConditions(
            air_quality_index=135,
            air_quality_category="Unhealthy for Sensitive Groups",
            air_quality_pollutant="PM2_5",
            updated_at=datetime(2025, 1, 1, 15, 0, tzinfo=UTC),
            sources=["Open-Meteo Air Quality"],
        ),
    )

    presentation = presenter.present(weather_data)

    assert presentation.air_quality is not None
    air_panel = presentation.air_quality
    assert "135" in air_panel.summary
    assert "Unhealthy for Sensitive Groups" in air_panel.summary
    assert "PM2.5" in air_panel.summary
    assert air_panel.guidance is not None
    assert "sensitive" in air_panel.guidance.lower()
    assert air_panel.fallback_text.startswith("Air quality for AQ Town")
    assert "Open-Meteo Air Quality" in air_panel.sources
    assert presentation.current_conditions is not None
    current_aq_metric = next(
        (m for m in presentation.current_conditions.metrics if m.label == "Air Quality"),
        None,
    )
    assert current_aq_metric is not None
    assert "Advice:" in current_aq_metric.value
    assert "Air Quality:" in presentation.current_conditions.fallback_text


@pytest.mark.unit
def test_presenter_skips_air_quality_panel_when_unavailable():
    settings = AppSettings()
    presenter = WeatherPresenter(settings)
    location = Location(name="No AQ City", latitude=10.0, longitude=20.0)
    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(condition="Cloudy"),
        environmental=EnvironmentalConditions(),
    )

    presentation = presenter.present(weather_data)

    assert presentation.air_quality is None


@pytest.mark.unit
def test_presenter_includes_trend_summary_and_status():
    settings = AppSettings()
    presenter = WeatherPresenter(settings)
    location = Location(name="Trend Town", latitude=10.0, longitude=20.0)
    weather_data = WeatherData(location=location, current=CurrentConditions(condition="Clear"))
    weather_data.trend_insights = [
        TrendInsight(
            metric="temperature",
            direction="rising",
            change=4.0,
            unit="°F",
            timeframe_hours=24,
            summary="Temperature rising +4.0°F over 24h",
        )
    ]
    weather_data.stale = True
    weather_data.stale_since = datetime(2025, 1, 1, 12, 0)
    presentation = presenter.present(weather_data)

    assert presentation.trend_summary
    assert presentation.trend_summary[0].startswith("Temperature rising")
    assert presentation.status_messages
    assert "cached" in presentation.status_messages[0].lower()


@pytest.mark.unit
def test_presenter_backfills_pressure_trend_from_hourly():
    settings = AppSettings()
    presenter = WeatherPresenter(settings)
    location = Location(name="Pressure Ville", latitude=30.0, longitude=-95.0)
    now = datetime.now()

    current = CurrentConditions(
        temperature_f=72.0,
        pressure_in=29.80,
        pressure_mb=29.80 * 33.8639,
        condition="Fair",
    )

    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=now + timedelta(hours=6),
                pressure_in=29.90,
                pressure_mb=29.90 * 33.8639,
            )
        ]
    )

    current_presentation = presenter.present_current(
        current,
        location,
        hourly_forecast=hourly,
    )

    assert current_presentation is not None
    pressure_metric = next(
        (metric for metric in current_presentation.metrics if metric.label == "Pressure trend"),
        None,
    )
    assert pressure_metric is not None
    assert "inHg over next 6h" in pressure_metric.value
    assert "Rising" in pressure_metric.value

    weather_data = WeatherData(
        location=location,
        current=current,
        hourly_forecast=hourly,
        trend_insights=[],
    )

    presentation = presenter.present(weather_data)
    assert presentation.trend_summary
    assert any(line.startswith("Pressure rising") for line in presentation.trend_summary)


@pytest.mark.unit
def test_presenter_omits_pressure_trend_when_disabled():
    settings = AppSettings(show_pressure_trend=False)
    presenter = WeatherPresenter(settings)
    location = Location(name="No Pressure", latitude=30.0, longitude=-95.0)
    now = datetime.now()

    current = CurrentConditions(
        temperature_f=72.0,
        pressure_in=29.80,
        pressure_mb=29.80 * 33.8639,
        condition="Fair",
        uv_index=6.0,
    )

    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=now + timedelta(hours=6),
                pressure_in=29.90,
                pressure_mb=29.90 * 33.8639,
            )
        ]
    )

    trends = [
        TrendInsight(
            metric="pressure",
            direction="rising",
            change=0.1,
            unit="inHg",
            timeframe_hours=6,
            summary="Pressure rising +0.10inHg over 6h",
        )
    ]

    presentation = presenter.present_current(
        current,
        location,
        trends=trends,
        hourly_forecast=hourly,
    )

    assert presentation is not None
    labels = {metric.label for metric in presentation.metrics}
    assert "Pressure trend" not in labels
    if presentation.trend_summary:
        assert all("Pressure" not in line for line in presentation.trend_summary)


@pytest.mark.unit
def test_presenter_builds_aviation_section_from_taf():
    settings = AppSettings()
    presenter = WeatherPresenter(settings)
    location = Location(name="Queens", latitude=40.6413, longitude=-73.7781)
    weather_data = WeatherData(
        location=location,
        aviation=AviationData(
            raw_taf="TAF KJFK 010000Z 0100/0206 18012KT P6SM FEW050",
            station_id="KJFK",
            airport_name="John F. Kennedy International",
        ),
    )

    presentation = presenter.present(weather_data)

    assert presentation.aviation is not None
    aviation = presentation.aviation
    assert aviation.station_id == "KJFK"
    assert aviation.taf_summary is not None
    assert "Terminal Aerodrome Forecast" in aviation.fallback_text
    assert "KJFK" in aviation.fallback_text


@pytest.mark.unit
def test_presenter_includes_forecast_extended_fields():
    """Presenter should include precipitation probability, snowfall, and UV index in forecasts."""
    from accessiweather.models import Forecast, ForecastPeriod

    settings = AppSettings(temperature_unit="fahrenheit")
    presenter = WeatherPresenter(settings)
    location = Location(name="Extended Fields City", latitude=40.0, longitude=-75.0)

    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name="Today",
                temperature=75.0,
                temperature_unit="F",
                short_forecast="Partly Cloudy",
                precipitation_probability=45.0,
                snowfall=0.0,
                uv_index=8.5,  # >= 8 is "Very High"
            ),
            ForecastPeriod(
                name="Tonight",
                temperature=55.0,
                temperature_unit="F",
                short_forecast="Snow Likely",
                precipitation_probability=80.0,
                snowfall=2.5,
                uv_index=0.0,
            ),
        ]
    )

    presentation = presenter.present_forecast(forecast, location)

    assert presentation is not None
    assert len(presentation.periods) == 2

    # Check first period (Today)
    today = presentation.periods[0]
    assert today.precipitation_probability == "45%"
    assert today.snowfall is None  # 0.0 snowfall should not be shown
    assert today.uv_index == "8 (Very High)"

    # Check second period (Tonight with snow)
    tonight = presentation.periods[1]
    assert tonight.precipitation_probability == "80%"
    assert tonight.snowfall == "2.5 in"
    assert tonight.uv_index == "0 (Low)"

    # Check fallback text includes the new fields
    assert "Precipitation: 45%" in presentation.fallback_text
    assert "Precipitation: 80%" in presentation.fallback_text
    assert "Snowfall: 2.5 in" in presentation.fallback_text
    assert "UV Index:" in presentation.fallback_text


@pytest.mark.unit
def test_presenter_includes_hourly_extended_fields():
    """Presenter should include extended fields in hourly forecast periods."""
    from datetime import timedelta

    settings = AppSettings(temperature_unit="fahrenheit")
    presenter = WeatherPresenter(settings)
    location = Location(name="Hourly City", latitude=40.0, longitude=-75.0)

    now = datetime.now(UTC)
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=now + timedelta(hours=1),
                temperature=72.0,
                short_forecast="Sunny",
                precipitation_probability=10.0,
                snowfall=0.0,
                uv_index=9.0,
            ),
            HourlyForecastPeriod(
                start_time=now + timedelta(hours=2),
                temperature=70.0,
                short_forecast="Light Snow",
                precipitation_probability=65.0,
                snowfall=0.3,
                uv_index=2.0,
            ),
        ]
    )

    from accessiweather.models import Forecast, ForecastPeriod

    forecast = Forecast(periods=[ForecastPeriod(name="Today", temperature=72.0)])

    presentation = presenter.present_forecast(forecast, location, hourly_forecast=hourly)

    assert presentation is not None
    assert len(presentation.hourly_periods) == 2

    # Check first hourly period
    hour1 = presentation.hourly_periods[0]
    assert hour1.precipitation_probability == "10%"
    assert hour1.snowfall is None  # 0.0 snowfall should not be shown
    assert hour1.uv_index == "9 (Very High)"

    # Check second hourly period with snow
    hour2 = presentation.hourly_periods[1]
    assert hour2.precipitation_probability == "65%"
    assert hour2.snowfall == "0.3 in"
    assert hour2.uv_index == "2 (Low)"

    # Check fallback text includes hourly extended fields
    assert "Precip 10%" in presentation.fallback_text
    assert "Snow 0.3 in" in presentation.fallback_text
    assert "UV 9 (Very High)" in presentation.fallback_text


@pytest.mark.unit
def test_presenter_handles_missing_extended_fields():
    """Presenter should gracefully handle missing extended fields."""
    from accessiweather.models import Forecast, ForecastPeriod

    settings = AppSettings(temperature_unit="fahrenheit")
    presenter = WeatherPresenter(settings)
    location = Location(name="Sparse Data City", latitude=40.0, longitude=-75.0)

    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name="Today",
                temperature=75.0,
                temperature_unit="F",
                short_forecast="Partly Cloudy",
                # No extended fields set
            ),
        ]
    )

    presentation = presenter.present_forecast(forecast, location)

    assert presentation is not None
    assert len(presentation.periods) == 1

    today = presentation.periods[0]
    assert today.precipitation_probability is None
    assert today.snowfall is None
    assert today.uv_index is None

    # Fallback text should not contain placeholders for missing fields
    assert "Precipitation:" not in presentation.fallback_text
    assert "Snowfall:" not in presentation.fallback_text
    assert "UV Index:" not in presentation.fallback_text
