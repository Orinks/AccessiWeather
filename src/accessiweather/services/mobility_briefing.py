"""Near-term mobility briefing helpers for AccessiWeather."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..models import WeatherData

_ACTIONABLE_GUST_THRESHOLD_MPH = 25.0
_VISIBILITY_CONCERN_THRESHOLD_MILES = 6.0
_PRECIP_INTENSITY_THRESHOLD = 0.01


def _coerce_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _infer_reference_time(weather_data: WeatherData) -> datetime | None:
    candidate_times: list[datetime] = []

    forecast = weather_data.minutely_precipitation
    if forecast and forecast.points:
        first_point_time = _coerce_utc(forecast.points[0].time)
        if first_point_time is not None:
            candidate_times.append(first_point_time)

    hourly = weather_data.hourly_forecast
    if hourly and hourly.periods:
        first_period_time = _coerce_utc(hourly.periods[0].start_time)
        if first_period_time is not None:
            candidate_times.append(first_period_time)

    if hourly and hourly.generated_at is not None:
        generated_at = _coerce_utc(hourly.generated_at)
        if generated_at is not None:
            candidate_times.append(generated_at)

    return min(candidate_times) if candidate_times else None


def _normalize_reference_time(
    reference_time: datetime | None, weather_data: WeatherData
) -> datetime:
    if reference_time is None:
        inferred_reference_time = _infer_reference_time(weather_data)
        if inferred_reference_time is not None:
            return inferred_reference_time
        return datetime.now(UTC)
    if reference_time.tzinfo is None:
        return reference_time.replace(tzinfo=UTC)
    return reference_time.astimezone(UTC)


def _first_precip_start_minutes(weather_data: WeatherData, now: datetime) -> int | None:
    forecast = weather_data.minutely_precipitation
    if not forecast or not forecast.points:
        return None

    for point in forecast.points:
        point_time = point.time if point.time.tzinfo else point.time.replace(tzinfo=UTC)
        delta = point_time.astimezone(UTC) - now
        minutes = int(delta.total_seconds() // 60)
        if minutes < 0 or minutes > 90:
            continue
        intensity = point.precipitation_intensity or 0.0
        probability = point.precipitation_probability or 0.0
        if intensity >= _PRECIP_INTENSITY_THRESHOLD or probability >= 0.5:
            return minutes
    return None


def _gust_increase_phrase(weather_data: WeatherData, now: datetime) -> str | None:
    hourly = weather_data.hourly_forecast
    if not hourly or not hourly.periods:
        return None

    candidate_periods = []
    for period in hourly.periods:
        start = (
            period.start_time if period.start_time.tzinfo else period.start_time.replace(tzinfo=UTC)
        )
        delta = start.astimezone(UTC) - now
        if delta < timedelta(0) or delta > timedelta(minutes=90):
            continue
        candidate_periods.append((period, delta))

    if not candidate_periods:
        return None

    first_gust = candidate_periods[0][0].wind_gust_mph or 0.0
    max_period, max_delta = max(candidate_periods, key=lambda item: item[0].wind_gust_mph or 0.0)
    max_gust = max_period.wind_gust_mph or 0.0
    if max_gust < _ACTIONABLE_GUST_THRESHOLD_MPH:
        return None
    if max_gust <= first_gust + 5:
        return None

    minutes = int(max_delta.total_seconds() // 60)
    if minutes <= 0:
        return "gusts increase soon"
    return f"gusts increase within {minutes} minutes"


def _hourly_fallback_phrase(weather_data: WeatherData, now: datetime) -> str | None:
    hourly = weather_data.hourly_forecast
    if not hourly or not hourly.periods:
        return None

    candidate_periods = []
    for period in hourly.periods:
        start = (
            period.start_time if period.start_time.tzinfo else period.start_time.replace(tzinfo=UTC)
        )
        delta = start.astimezone(UTC) - now
        if delta < timedelta(0) or delta > timedelta(minutes=90):
            continue
        candidate_periods.append(period)

    if not candidate_periods:
        return None

    for period in candidate_periods:
        precip_prob = period.precipitation_probability or 0.0
        if precip_prob >= 60 or (period.short_forecast and "rain" in period.short_forecast.lower()):
            return period.short_forecast or "Rain likely"
    return None


def _visibility_phrase(weather_data: WeatherData, now: datetime) -> str | None:
    hourly = weather_data.hourly_forecast
    if hourly and hourly.periods:
        candidate_visibilities = []
        for period in hourly.periods:
            start = (
                period.start_time
                if period.start_time.tzinfo
                else period.start_time.replace(tzinfo=UTC)
            )
            delta = start.astimezone(UTC) - now
            if delta < timedelta(0) or delta > timedelta(minutes=90):
                continue
            if period.visibility_miles is not None:
                candidate_visibilities.append(period.visibility_miles)
        if candidate_visibilities:
            min_visibility = min(candidate_visibilities)
            if min_visibility < _VISIBILITY_CONCERN_THRESHOLD_MILES:
                return f"visibility may drop to around {min_visibility:.0f} miles"
            return "visibility stays good"

    current = weather_data.current
    if (
        current
        and current.visibility_miles is not None
        and current.visibility_miles >= _VISIBILITY_CONCERN_THRESHOLD_MILES
    ):
        return "visibility stays good"
    return None


def build_mobility_briefing(
    weather_data: WeatherData,
    *,
    reference_time: datetime | None = None,
) -> str | None:
    """Build a concise next-90-minutes mobility briefing, if actionable."""
    now = _normalize_reference_time(reference_time, weather_data)
    phrases: list[str] = []

    precip_start_minutes = _first_precip_start_minutes(weather_data, now)
    if precip_start_minutes is not None:
        if precip_start_minutes <= 0:
            phrases.append("Rain is starting now")
        else:
            phrases.append(f"Dry for {precip_start_minutes} minutes, then rain likely")
    else:
        hourly_phrase = _hourly_fallback_phrase(weather_data, now)
        if hourly_phrase is not None:
            phrases.append(hourly_phrase)

    gust_phrase = _gust_increase_phrase(weather_data, now)
    if gust_phrase is not None:
        phrases.append(gust_phrase)

    visibility_phrase = _visibility_phrase(weather_data, now)
    if visibility_phrase is not None and (phrases or visibility_phrase != "visibility stays good"):
        phrases.append(visibility_phrase)

    if not phrases:
        return None

    sentence = "; ".join(phrases).strip()
    if not sentence:
        return None
    sentence = sentence[0].upper() + sentence[1:]
    if not sentence.endswith("."):
        sentence += "."
    return sentence
