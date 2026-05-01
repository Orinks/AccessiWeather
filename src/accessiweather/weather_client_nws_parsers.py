"""Parsers for NWS weather client responses."""
# ruff: noqa: F403, F405

from __future__ import annotations

from .weather_client_nws_common import *  # noqa: F403


def parse_nws_current_conditions(
    data: dict,
    location: Location | None = None,
) -> CurrentConditions:
    """
    Parse NWS current conditions payload into a CurrentConditions model.

    Args:
    ----
        data: NWS API response payload
        location: Location object with timezone info. If provided, timestamps
                  will be converted to the location's local timezone.

    """
    props = data.get("properties", {})

    temp_c = props.get("temperature", {}).get("value")
    temp_f = (temp_c * 9 / 5) + 32 if temp_c is not None else None

    humidity = props.get("relativeHumidity", {}).get("value")
    humidity = round(humidity) if humidity is not None else None

    dewpoint_c = props.get("dewpoint", {}).get("value")
    dewpoint_f = (dewpoint_c * 9 / 5) + 32 if dewpoint_c is not None else None

    visibility_m = props.get("visibility", {}).get("value")
    visibility_miles = visibility_m / 1609.344 if visibility_m is not None else None
    visibility_km = visibility_m / 1000 if visibility_m is not None else None

    uv_index_value = props.get("uvIndex", {}).get("value")
    uv_index = None
    if uv_index_value is not None:
        try:
            uv_index = float(uv_index_value)
        except (TypeError, ValueError):
            uv_index = None

    wind_speed = props.get("windSpeed", {})
    wind_speed_value = wind_speed.get("value")
    wind_speed_unit = wind_speed.get("unitCode")
    wind_speed_mph, wind_speed_kph = convert_wind_speed_to_mph_and_kph(
        wind_speed_value, wind_speed_unit
    )

    wind_direction = props.get("windDirection", {}).get("value")

    pressure_pa = props.get("barometricPressure", {}).get("value")
    pressure_in = convert_pa_to_inches(pressure_pa)

    # Seasonal fields - wind chill and heat index
    wind_chill_c = props.get("windChill", {}).get("value")
    wind_chill_f = (wind_chill_c * 9 / 5) + 32 if wind_chill_c is not None else None

    heat_index_c = props.get("heatIndex", {}).get("value")
    heat_index_f = (heat_index_c * 9 / 5) + 32 if heat_index_c is not None else None

    # Determine feels_like based on wind chill or heat index
    feels_like_f = None
    feels_like_c = None
    if wind_chill_f is not None and (temp_f is None or wind_chill_f < temp_f):
        feels_like_f = wind_chill_f
        feels_like_c = wind_chill_c
    elif heat_index_f is not None and (temp_f is None or heat_index_f > temp_f):
        feels_like_f = heat_index_f
        feels_like_c = heat_index_c

    return CurrentConditions(
        temperature_f=temp_f,
        temperature_c=temp_c,
        condition=props.get("textDescription"),
        humidity=humidity,
        dewpoint_f=dewpoint_f,
        dewpoint_c=dewpoint_c,
        wind_speed_mph=wind_speed_mph,
        wind_speed_kph=wind_speed_kph,
        wind_direction=wind_direction,
        pressure_in=pressure_in,
        pressure_mb=convert_pa_to_mb(pressure_pa),
        feels_like_f=feels_like_f,
        feels_like_c=feels_like_c,
        visibility_miles=visibility_miles,
        visibility_km=visibility_km,
        uv_index=uv_index,
        # Seasonal fields
        wind_chill_f=wind_chill_f,
        wind_chill_c=wind_chill_c,
        heat_index_f=heat_index_f,
        heat_index_c=heat_index_c,
    )


def parse_nws_forecast(data: dict) -> Forecast:
    """Parse NWS forecast payload into a Forecast model."""
    periods = []

    raw_periods = data.get("properties", {}).get("periods", [])

    for period_data in raw_periods:
        temperature, temperature_unit = _extract_temperature(
            period_data.get("temperature"), period_data.get("temperatureUnit")
        )

        wind_direction_value = _extract_scalar(period_data.get("windDirection"))
        wind_direction = str(wind_direction_value) if wind_direction_value is not None else None

        # Parse timestamps
        start_time = None
        end_time = None
        if period_data.get("startTime"):
            try:
                start_time = datetime.fromisoformat(period_data["startTime"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                logger.warning(f"Failed to parse startTime: {period_data.get('startTime')}")

        if period_data.get("endTime"):
            try:
                end_time = datetime.fromisoformat(period_data["endTime"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                logger.warning(f"Failed to parse endTime: {period_data.get('endTime')}")

        period = ForecastPeriod(
            name=period_data.get("name", ""),
            temperature=temperature,
            temperature_unit=str(temperature_unit),
            short_forecast=period_data.get("shortForecast"),
            detailed_forecast=period_data.get("detailedForecast"),
            wind_speed=_format_wind_speed(period_data.get("windSpeed")),
            wind_speed_mph=_extract_wind_speed_mph(period_data.get("windSpeed")),
            wind_direction=wind_direction,
            icon=period_data.get("icon"),
            start_time=start_time,
            end_time=end_time,
            precipitation_probability=_extract_float(period_data.get("probabilityOfPrecipitation")),
        )
        periods.append(period)

    # Pair daytime/nighttime periods to populate high/low temperatures.
    # NWS returns alternating day/night periods (isDaytime flag). Set the
    # nighttime temperature as temperature_low on the preceding daytime period.
    for i, period_data in enumerate(raw_periods):
        if period_data.get("isDaytime") and i + 1 < len(raw_periods):
            next_data = raw_periods[i + 1]
            if not next_data.get("isDaytime"):
                night_temp, _ = _extract_temperature(
                    next_data.get("temperature"), next_data.get("temperatureUnit")
                )
                if night_temp is not None:
                    periods[i].temperature_low = night_temp

    return Forecast(periods=periods, generated_at=datetime.now())


def parse_nws_alerts(data: dict) -> WeatherAlerts:
    """Parse NWS alerts payload into a WeatherAlerts collection."""
    alerts: list[WeatherAlert] = []

    for alert_data in data.get("features", []):
        props = alert_data.get("properties", {})

        alert_id = None
        if "id" in alert_data:
            alert_id = alert_data["id"]
        elif "identifier" in props:
            alert_id = props["identifier"]
        elif "@id" in props:
            alert_id = props["@id"]

        onset = None
        expires = None
        sent = None
        effective = None

        if props.get("onset"):
            try:
                onset = datetime.fromisoformat(props["onset"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse onset time: {props['onset']}")

        if props.get("expires"):
            try:
                expires = datetime.fromisoformat(props["expires"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse expires time: {props['expires']}")

        if props.get("sent"):
            try:
                sent = datetime.fromisoformat(props["sent"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse sent time: {props['sent']}")

        if props.get("effective"):
            try:
                effective = datetime.fromisoformat(props["effective"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse effective time: {props['effective']}")

        references = []
        for ref in props.get("references", []):
            ref_id = ref.get("identifier") or ref.get("@id") or ref.get("id")
            if ref_id:
                references.append(ref_id)

        alert = WeatherAlert(
            title=props.get("headline", "Weather Alert"),
            description=props.get("description", ""),
            severity=props.get("severity", "Unknown"),
            urgency=props.get("urgency", "Unknown"),
            certainty=props.get("certainty", "Unknown"),
            event=props.get("event"),
            headline=props.get("headline"),
            instruction=props.get("instruction"),
            onset=onset,
            expires=expires,
            sent=sent,
            effective=effective,
            areas=props.get("areaDesc", "").split("; ") if props.get("areaDesc") else [],
            references=references,
            id=alert_id,
            source="NWS",
            message_type=props.get("messageType"),
        )
        alerts.append(alert)

        if alert_id:
            logger.debug(f"Parsed alert with ID: {alert_id}")
        else:
            logger.debug("Parsed alert without ID, will generate unique ID")

    # Deduplicate by alert ID, keeping first occurrence
    seen_ids: set[str] = set()
    deduped: list[WeatherAlert] = []
    for alert in alerts:
        if alert.id and alert.id in seen_ids:
            logger.debug(f"Skipping duplicate alert ID: {alert.id}")
            continue
        if alert.id:
            seen_ids.add(alert.id)
        deduped.append(alert)
    alerts = deduped

    logger.info(f"Parsed {len(alerts)} alerts from NWS API")
    return WeatherAlerts(alerts=alerts)


def parse_nws_hourly_forecast(data: dict, location: Location | None = None) -> HourlyForecast:
    """Parse NWS hourly forecast payload into an HourlyForecast model."""
    from zoneinfo import ZoneInfo

    periods = []

    # Get location timezone if available
    location_tz = None
    if location and location.timezone:
        try:
            location_tz = ZoneInfo(location.timezone)
        except Exception:
            logger.warning(f"Failed to load timezone: {location.timezone}")

    for period_data in data.get("properties", {}).get("periods", []):
        start_time_str = period_data.get("startTime")
        start_time = None
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                # Convert to location's timezone if available
                if location_tz and start_time:
                    start_time = start_time.astimezone(location_tz)
            except ValueError:
                logger.warning(f"Failed to parse start time: {start_time_str}")

        end_time_str = period_data.get("endTime")
        end_time = None
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                # Convert to location's timezone if available
                if location_tz and end_time:
                    end_time = end_time.astimezone(location_tz)
            except ValueError:
                logger.warning(f"Failed to parse end time: {end_time_str}")

        temperature, temperature_unit = _extract_temperature(
            period_data.get("temperature"), period_data.get("temperatureUnit")
        )

        wind_direction_value = _extract_scalar(period_data.get("windDirection"))
        wind_direction = str(wind_direction_value) if wind_direction_value is not None else None

        period = HourlyForecastPeriod(
            start_time=start_time or datetime.now(),
            end_time=end_time,
            temperature=temperature,
            temperature_unit=str(temperature_unit),
            short_forecast=period_data.get("shortForecast"),
            wind_speed=_format_wind_speed(period_data.get("windSpeed")),
            wind_direction=wind_direction,
            icon=period_data.get("icon"),
            precipitation_probability=_extract_float(period_data.get("probabilityOfPrecipitation")),
        )
        periods.append(period)

    return HourlyForecast(periods=periods, generated_at=datetime.now())


def parse_nws_gridpoint_pressure(data: dict) -> dict[datetime, tuple[float | None, float | None]]:
    """Parse NWS gridpoint pressure values keyed by valid-time start."""
    pressure = data.get("properties", {}).get("pressure", {})
    values = pressure.get("values", []) if isinstance(pressure, dict) else []
    pressure_by_time: dict[datetime, tuple[float | None, float | None]] = {}

    for item in values:
        if not isinstance(item, dict):
            continue
        start_time = _parse_valid_time_start(item.get("validTime"))
        pressure_pa = item.get("value")
        if start_time is None or pressure_pa is None:
            continue
        pressure_by_time[start_time] = (
            convert_pa_to_inches(pressure_pa),
            convert_pa_to_mb(pressure_pa),
        )

    return pressure_by_time


def apply_nws_gridpoint_pressure(
    hourly: HourlyForecast,
    pressure_by_time: dict[datetime, tuple[float | None, float | None]],
) -> HourlyForecast:
    """Populate NWS hourly periods with pressure from the gridpoint pressure layer."""
    if not pressure_by_time:
        return hourly

    updated_periods: list[HourlyForecastPeriod] = []
    changed = False
    for period in hourly.periods:
        if period.pressure_in is not None or period.pressure_mb is not None:
            updated_periods.append(period)
            continue

        pressure_pair = _nearest_pressure_pair(period.start_time, pressure_by_time)
        if pressure_pair is None:
            updated_periods.append(period)
            continue

        updated_periods.append(
            replace(
                period,
                pressure_in=pressure_pair[0],
                pressure_mb=pressure_pair[1],
            )
        )
        changed = True

    if not changed:
        return hourly
    return HourlyForecast(
        periods=updated_periods,
        generated_at=hourly.generated_at,
        summary=hourly.summary,
    )


def _nearest_pressure_pair(
    start_time: datetime,
    pressure_by_time: dict[datetime, tuple[float | None, float | None]],
) -> tuple[float | None, float | None] | None:
    """Return pressure from the closest gridpoint valid time within 90 minutes."""
    target_ts = _timestamp_utc(start_time)
    best_pair = None
    best_delta = None
    for valid_time, pressure_pair in pressure_by_time.items():
        delta = abs(_timestamp_utc(valid_time) - target_ts)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_pair = pressure_pair

    if best_delta is None or best_delta > 90 * 60:
        return None
    return best_pair


def _parse_valid_time_start(valid_time: str | None) -> datetime | None:
    """Parse the start timestamp from an NWS ISO interval validTime value."""
    if not valid_time:
        return None
    start = valid_time.split("/", 1)[0]
    try:
        return datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        logger.debug("Failed to parse NWS gridpoint validTime: %s", valid_time)
        return None


def _timestamp_utc(value: datetime) -> float:
    """Normalize aware and naive datetimes to UTC timestamps."""
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.timestamp()
