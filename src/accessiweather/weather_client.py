"""Simplified weather API client for AccessiWeather.

This module provides a direct, async weather API client that fetches data
from NWS and OpenMeteo APIs without complex service layer abstractions.
"""

import logging
from datetime import datetime

import httpx

from .models import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)
from .visual_crossing_client import VisualCrossingApiError, VisualCrossingClient

logger = logging.getLogger(__name__)


class WeatherClient:
    """Simple async weather API client."""

    def __init__(
        self,
        user_agent: str = "AccessiWeather/1.0",
        data_source: str = "auto",
        visual_crossing_api_key: str = "",
    ):
        """Initialize the instance."""
        self.user_agent = user_agent
        self.nws_base_url = "https://api.weather.gov"
        self.openmeteo_base_url = "https://api.open-meteo.com/v1"
        self.timeout = 10.0
        self.data_source = data_source  # "auto", "nws", "openmeteo", "visualcrossing"
        self.visual_crossing_api_key = visual_crossing_api_key

        # Initialize Visual Crossing client if API key is provided
        self.visual_crossing_client = None
        if visual_crossing_api_key:
            self.visual_crossing_client = VisualCrossingClient(visual_crossing_api_key, user_agent)

    async def get_weather_data(self, location: Location) -> WeatherData:
        """Get complete weather data for a location."""
        logger.info(f"Fetching weather data for {location.name}")

        # Determine which API to use based on data source and location
        logger.debug("Determining API choice")
        api_choice = self._determine_api_choice(location)
        api_name = {
            "nws": "NWS",
            "openmeteo": "Open-Meteo",
            "visualcrossing": "Visual Crossing",
        }.get(api_choice, "NWS")
        logger.info(f"Using {api_name} API for {location.name} (data_source: {self.data_source})")

        logger.debug("Creating WeatherData object")
        weather_data = WeatherData(location=location, last_updated=datetime.now())

        if api_choice == "visualcrossing":
            # Use Visual Crossing API
            try:
                if not self.visual_crossing_client:
                    raise VisualCrossingApiError("Visual Crossing API key not configured")

                current = await self.visual_crossing_client.get_current_conditions(location)
                forecast = await self.visual_crossing_client.get_forecast(location)
                hourly_forecast = await self.visual_crossing_client.get_hourly_forecast(location)
                alerts = await self.visual_crossing_client.get_alerts(location)

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = "Forecast discussion not available from Visual Crossing."
                weather_data.alerts = alerts

                # Process alerts for notifications if we have any
                if alerts and alerts.has_alerts():
                    logger.info(
                        f"Processing {len(alerts.alerts)} Visual Crossing alerts for notifications"
                    )
                    await self._process_visual_crossing_alerts(alerts, location)

                logger.info(f"Successfully fetched Visual Crossing data for {location.name}")

            except VisualCrossingApiError as e:
                logger.warning(f"Visual Crossing API failed for {location.name}: {e}")

                # Try fallback based on location
                if self._is_us_location(location):
                    logger.info(f"Trying NWS fallback for US location: {location.name}")
                    try:
                        current = await self._get_nws_current_conditions(location)
                        forecast, discussion = await self._get_nws_forecast_and_discussion(location)
                        hourly_forecast = await self._get_nws_hourly_forecast(location)
                        alerts = await self._get_nws_alerts(location)

                        weather_data.current = current
                        weather_data.forecast = forecast
                        weather_data.hourly_forecast = hourly_forecast
                        weather_data.discussion = discussion
                        weather_data.alerts = alerts

                        logger.info(f"Successfully fetched NWS fallback data for {location.name}")
                    except Exception as e2:
                        logger.error(
                            f"Both Visual Crossing and NWS failed for {location.name}: VC={e}, NWS={e2}"
                        )
                        self._set_empty_weather_data(weather_data)
                else:
                    logger.info(
                        f"Trying Open-Meteo fallback for international location: {location.name}"
                    )
                    try:
                        current = await self._get_openmeteo_current_conditions(location)
                        forecast = await self._get_openmeteo_forecast(location)
                        hourly_forecast = await self._get_openmeteo_hourly_forecast(location)

                        weather_data.current = current
                        weather_data.forecast = forecast
                        weather_data.hourly_forecast = hourly_forecast
                        weather_data.discussion = (
                            "Forecast discussion not available from Open-Meteo."
                        )
                        weather_data.alerts = WeatherAlerts(alerts=[])

                        logger.info(
                            f"Successfully fetched Open-Meteo fallback data for {location.name}"
                        )
                    except Exception as e2:
                        logger.error(
                            f"Both Visual Crossing and Open-Meteo failed for {location.name}: VC={e}, OM={e2}"
                        )
                        self._set_empty_weather_data(weather_data)

        elif api_choice == "openmeteo":
            # Use Open-Meteo API
            try:
                current = await self._get_openmeteo_current_conditions(location)
                forecast = await self._get_openmeteo_forecast(location)
                hourly_forecast = await self._get_openmeteo_hourly_forecast(location)

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = "Forecast discussion not available from Open-Meteo."
                weather_data.alerts = WeatherAlerts(alerts=[])  # Open-Meteo doesn't provide alerts

                logger.info(f"Successfully fetched Open-Meteo data for {location.name}")

            except Exception as e:
                logger.warning(f"Open-Meteo API failed for {location.name}: {e}")

                # Try NWS as fallback if location is in US
                if self._is_us_location(location):
                    logger.info(f"Trying NWS fallback for US location: {location.name}")
                    try:
                        current = await self._get_nws_current_conditions(location)
                        forecast, discussion = await self._get_nws_forecast_and_discussion(location)
                        hourly_forecast = await self._get_nws_hourly_forecast(location)
                        alerts = await self._get_nws_alerts(location)

                        weather_data.current = current
                        weather_data.forecast = forecast
                        weather_data.hourly_forecast = hourly_forecast
                        weather_data.discussion = discussion
                        weather_data.alerts = alerts

                        logger.info(f"Successfully fetched NWS fallback data for {location.name}")
                    except Exception as e2:
                        logger.error(
                            f"Both Open-Meteo and NWS failed for {location.name}: OpenMeteo={e}, NWS={e2}"
                        )
                        self._set_empty_weather_data(weather_data)
                else:
                    logger.error(
                        f"Open-Meteo failed for international location {location.name}: {e}"
                    )
                    self._set_empty_weather_data(weather_data)
        else:
            # Use NWS API
            try:
                current = await self._get_nws_current_conditions(location)
                forecast, discussion = await self._get_nws_forecast_and_discussion(location)
                hourly_forecast = await self._get_nws_hourly_forecast(location)
                alerts = await self._get_nws_alerts(location)

                weather_data.current = current
                weather_data.forecast = forecast
                weather_data.hourly_forecast = hourly_forecast
                weather_data.discussion = discussion
                weather_data.alerts = alerts

                # Check if we actually got valid data
                if current is None and forecast is None:
                    # If essential data is missing, try Open-Meteo fallback
                    logger.info(
                        f"NWS returned empty data for {location.name}, trying Open-Meteo fallback"
                    )
                    try:
                        current = await self._get_openmeteo_current_conditions(location)
                        forecast = await self._get_openmeteo_forecast(location)
                        hourly_forecast = await self._get_openmeteo_hourly_forecast(location)

                        weather_data.current = current
                        weather_data.forecast = forecast
                        weather_data.hourly_forecast = hourly_forecast
                        weather_data.discussion = (
                            "Forecast discussion not available from Open-Meteo."
                        )
                        weather_data.alerts = WeatherAlerts(alerts=[])

                        # Check if Open-Meteo returned valid data
                        if current is None and forecast is None:
                            logger.error(f"Open-Meteo also returned empty data for {location.name}")
                            self._set_empty_weather_data(weather_data)
                        else:
                            logger.info(
                                f"Successfully fetched Open-Meteo fallback data for {location.name}"
                            )
                    except Exception as e2:
                        logger.error(f"Both NWS and Open-Meteo failed for {location.name}: {e2}")
                        self._set_empty_weather_data(weather_data)
                else:
                    logger.info(f"Successfully fetched NWS data for {location.name}")

            except Exception as e:
                logger.warning(f"NWS API failed for {location.name}: {e}")

                # Try Open-Meteo as fallback
                logger.info(f"Trying Open-Meteo fallback for {location.name}")
                try:
                    current = await self._get_openmeteo_current_conditions(location)
                    forecast = await self._get_openmeteo_forecast(location)
                    hourly_forecast = await self._get_openmeteo_hourly_forecast(location)

                    weather_data.current = current
                    weather_data.forecast = forecast
                    weather_data.hourly_forecast = hourly_forecast
                    weather_data.discussion = "Forecast discussion not available from Open-Meteo."
                    weather_data.alerts = WeatherAlerts(
                        alerts=[]
                    )  # Open-Meteo doesn't provide alerts

                    logger.info(
                        f"Successfully fetched Open-Meteo fallback data for {location.name}"
                    )
                except Exception as e2:
                    logger.error(
                        f"Both NWS and Open-Meteo failed for {location.name}: NWS={e}, OpenMeteo={e2}"
                    )
                    self._set_empty_weather_data(weather_data)

        return weather_data

    async def _process_visual_crossing_alerts(self, alerts: WeatherAlerts, location: Location):
        """Process Visual Crossing alerts for notifications."""
        try:
            # Import the alert notification system
            # Create config directory for alert state
            import os
            import tempfile

            from .alert_manager import AlertManager
            from .alert_notification_system import AlertNotificationSystem

            config_dir = os.path.join(tempfile.gettempdir(), "accessiweather_alerts")

            # Create alert manager with more permissive settings for testing
            from .alert_manager import AlertSettings

            # Create settings that will allow all alerts through
            settings = AlertSettings()
            settings.min_severity_priority = 1  # Allow all severities including "unknown"
            settings.notifications_enabled = True

            alert_manager = AlertManager(config_dir, settings)
            notification_system = AlertNotificationSystem(alert_manager)

            # Add debugging information
            logger.info(f"Processing Visual Crossing alerts for {location.name}")
            logger.info(f"Number of alerts to process: {len(alerts.alerts)}")

            # Log alert details for debugging
            for i, alert in enumerate(alerts.alerts):
                logger.info(f"Alert {i + 1}: {alert.event} - {alert.severity} - {alert.headline}")

            # Check notification settings
            settings = notification_system.get_settings()
            logger.info(
                f"Notification settings - enabled: {settings.notifications_enabled}, min_severity: {settings.min_severity_priority}"
            )

            # Process and send notifications
            notifications_sent = await notification_system.process_and_notify(alerts)

            if notifications_sent > 0:
                logger.info(
                    f"✅ Sent {notifications_sent} Visual Crossing alert notifications for {location.name}"
                )
            else:
                logger.warning(f"⚠️ No Visual Crossing alert notifications sent for {location.name}")

                # Get statistics for debugging
                stats = notification_system.get_statistics()
                logger.info(f"Alert statistics: {stats}")

        except Exception as e:
            logger.error(f"Failed to process Visual Crossing alerts for notifications: {e}")

    def _determine_api_choice(self, location: Location) -> str:
        """Determine which API to use for the given location."""
        # Validate data source
        valid_sources = ["auto", "nws", "openmeteo", "visualcrossing"]
        if self.data_source not in valid_sources:
            logger.warning(f"Invalid data source '{self.data_source}', defaulting to 'auto'")
            self.data_source = "auto"

        if self.data_source == "visualcrossing":
            # Check if Visual Crossing client is available
            if not self.visual_crossing_client:
                logger.warning(
                    "Visual Crossing selected but no API key provided, falling back to auto"
                )
                return "nws" if self._is_us_location(location) else "openmeteo"
            return "visualcrossing"
        if self.data_source == "openmeteo":
            return "openmeteo"
        if self.data_source == "nws":
            return "nws"
        if self.data_source == "auto":
            # Use NWS for US locations, Open-Meteo for international locations
            return "nws" if self._is_us_location(location) else "openmeteo"
        # Fallback for any unexpected cases
        logger.warning(f"Unexpected data source '{self.data_source}', defaulting to auto")
        return "nws" if self._is_us_location(location) else "openmeteo"

    def _is_us_location(self, location: Location) -> bool:
        """Check if location is within the United States (rough approximation)."""
        # Continental US bounds (approximate)
        return 24.0 <= location.latitude <= 49.0 and -125.0 <= location.longitude <= -66.0

    def _set_empty_weather_data(self, weather_data: WeatherData) -> None:
        """Set empty weather data when all APIs fail."""
        weather_data.current = CurrentConditions()
        weather_data.forecast = Forecast(periods=[])
        weather_data.hourly_forecast = HourlyForecast(periods=[])
        weather_data.discussion = "Weather data not available."
        weather_data.alerts = WeatherAlerts(alerts=[])

    async def _get_nws_current_conditions(self, location: Location) -> CurrentConditions | None:
        """Get current conditions from NWS API."""
        try:
            # Get grid point for location
            grid_url = f"{self.nws_base_url}/points/{location.latitude},{location.longitude}"

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}

                # Get grid point
                response = await client.get(grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

                # Get observation stations
                stations_url = grid_data["properties"]["observationStations"]
                response = await client.get(stations_url, headers=headers)
                response.raise_for_status()
                stations_data = response.json()

                if not stations_data["features"]:
                    logger.warning("No observation stations found")
                    return None

                # Get latest observation from first station
                station_id = stations_data["features"][0]["properties"]["stationIdentifier"]
                obs_url = f"{self.nws_base_url}/stations/{station_id}/observations/latest"

                response = await client.get(obs_url, headers=headers)
                response.raise_for_status()
                obs_data = response.json()

                return self._parse_nws_current_conditions(obs_data)

        except Exception as e:
            logger.error(f"Failed to get NWS current conditions: {e}")
            return None

    async def _get_nws_forecast_and_discussion(
        self, location: Location
    ) -> tuple[Forecast | None, str | None]:
        """Get forecast and discussion from NWS API."""
        try:
            # Get grid point for location
            grid_url = f"{self.nws_base_url}/points/{location.latitude},{location.longitude}"

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}

                # Get grid point
                response = await client.get(grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

                # Get forecast
                forecast_url = grid_data["properties"]["forecast"]
                response = await client.get(forecast_url, headers=headers)
                response.raise_for_status()
                forecast_data = response.json()

                # Get forecast discussion (AFD)
                discussion = await self._get_nws_discussion(client, headers, grid_data)

                return self._parse_nws_forecast(forecast_data), discussion

        except Exception as e:
            logger.error(f"Failed to get NWS forecast and discussion: {e}")
            return None, None

    async def _get_nws_discussion(self, client, headers, grid_data) -> str:
        """Get NWS Area Forecast Discussion (AFD) for the location."""
        try:
            # Get forecast URL to extract office ID
            forecast_url = grid_data.get("properties", {}).get("forecast")
            if not forecast_url:
                logger.warning("No forecast URL found in grid data")
                return "Forecast discussion not available."

            # Extract office ID from forecast URL
            # URL format: https://api.weather.gov/gridpoints/PHI/49,75/forecast
            parts = forecast_url.split("/")
            if len(parts) < 6:
                logger.warning(f"Unexpected forecast URL format: {forecast_url}")
                return "Forecast discussion not available."

            office_id = parts[-3]  # Extract office ID (e.g., "PHI")
            logger.info(f"Fetching AFD for office: {office_id}")

            # Get AFD products for this office
            products_url = f"{self.nws_base_url}/products/types/AFD/locations/{office_id}"
            response = await client.get(products_url, headers=headers)

            if response.status_code != 200:
                logger.warning(f"Failed to get AFD products: HTTP {response.status_code}")
                return "Forecast discussion not available."

            products_data = response.json()

            # Check if we have any AFD products
            if not products_data.get("@graph") or not products_data["@graph"]:
                logger.warning(f"No AFD products found for office {office_id}")
                return "Forecast discussion not available for this location."

            # Get the latest AFD product
            latest_product = products_data["@graph"][0]
            latest_product_id = latest_product.get("id")

            if not latest_product_id:
                logger.warning("No product ID found in latest AFD product")
                return "Forecast discussion not available."

            # Fetch the actual AFD text
            product_url = f"{self.nws_base_url}/products/{latest_product_id}"
            response = await client.get(product_url, headers=headers)

            if response.status_code != 200:
                logger.warning(f"Failed to get AFD product text: HTTP {response.status_code}")
                return "Forecast discussion not available."

            product_data = response.json()
            product_text = product_data.get("productText")

            if not product_text:
                logger.warning("No product text found in AFD product")
                return "Forecast discussion not available."

            logger.info(f"Successfully fetched AFD for office {office_id}")
            return product_text

        except Exception as e:
            logger.error(f"Failed to get NWS discussion: {e}")
            return "Forecast discussion not available due to error."

    async def _get_nws_alerts(self, location: Location) -> WeatherAlerts | None:
        """Get weather alerts from NWS API."""
        try:
            alerts_url = f"{self.nws_base_url}/alerts/active"
            params = {
                "point": f"{location.latitude},{location.longitude}",
                "status": "actual",
                "message_type": "alert",
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(alerts_url, params=params, headers=headers)
                response.raise_for_status()
                alerts_data = response.json()

                return self._parse_nws_alerts(alerts_data)

        except Exception as e:
            logger.error(f"Failed to get NWS alerts: {e}")
            return WeatherAlerts(alerts=[])

    async def _get_nws_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Get hourly forecast from NWS API."""
        try:
            # Get grid point data first
            grid_url = f"{self.nws_base_url}/points/{location.latitude},{location.longitude}"

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                headers = {"User-Agent": self.user_agent}
                response = await client.get(grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

                # Get hourly forecast URL
                hourly_forecast_url = grid_data.get("properties", {}).get("forecastHourly")
                if not hourly_forecast_url:
                    logger.warning("No hourly forecast URL found in grid data")
                    return None

                # Fetch hourly forecast
                response = await client.get(hourly_forecast_url, headers=headers)
                response.raise_for_status()
                hourly_data = response.json()

                return self._parse_nws_hourly_forecast(hourly_data)

        except Exception as e:
            logger.error(f"Failed to get NWS hourly forecast: {e}")
            return None

    async def _get_openmeteo_current_conditions(
        self, location: Location
    ) -> CurrentConditions | None:
        """Get current conditions from OpenMeteo API."""
        try:
            url = f"{self.openmeteo_base_url}/forecast"
            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,pressure_msl",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "auto",
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                return self._parse_openmeteo_current_conditions(data)

        except Exception as e:
            logger.error(f"Failed to get OpenMeteo current conditions: {e}")
            return None

    async def _get_openmeteo_forecast(self, location: Location) -> Forecast | None:
        """Get forecast from OpenMeteo API."""
        try:
            url = f"{self.openmeteo_base_url}/forecast"
            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max,wind_direction_10m_dominant",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
                "forecast_days": 7,
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                return self._parse_openmeteo_forecast(data)

        except Exception as e:
            logger.error(f"Failed to get OpenMeteo forecast: {e}")
            return None

    async def _get_openmeteo_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Get hourly forecast from OpenMeteo API."""
        try:
            url = f"{self.openmeteo_base_url}/forecast"
            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "hourly": "temperature_2m,weather_code,wind_speed_10m,wind_direction_10m",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
                "forecast_days": 2,  # Get 48 hours of data
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                return self._parse_openmeteo_hourly_forecast(data)

        except Exception as e:
            logger.error(f"Failed to get OpenMeteo hourly forecast: {e}")
            return None

    def _parse_nws_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse NWS current conditions data."""
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

        wind_speed = props.get("windSpeed", {})
        wind_speed_value = wind_speed.get("value")
        wind_speed_unit = wind_speed.get("unitCode")
        wind_speed_mph, wind_speed_kph = self._convert_wind_speed_to_mph_and_kph(
            wind_speed_value, wind_speed_unit
        )

        wind_direction = props.get("windDirection", {}).get("value")

        pressure_pa = props.get("barometricPressure", {}).get("value")
        pressure_in = self._convert_pa_to_inches(pressure_pa)

        timestamp = props.get("timestamp")
        last_updated = None
        if timestamp:
            try:
                last_updated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                logger.debug(f"Failed to parse observation timestamp: {timestamp}")

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
            pressure_mb=self._convert_pa_to_mb(pressure_pa),
            feels_like_f=None,
            feels_like_c=None,
            visibility_miles=visibility_miles,
            visibility_km=visibility_km,
            last_updated=last_updated or datetime.now(),
        )

    def _parse_nws_forecast(self, data: dict) -> Forecast:
        """Parse NWS forecast data."""
        periods = []

        for period_data in data.get("properties", {}).get("periods", []):
            period = ForecastPeriod(
                name=period_data.get("name", ""),
                temperature=period_data.get("temperature"),
                temperature_unit=period_data.get("temperatureUnit", "F"),
                short_forecast=period_data.get("shortForecast"),
                detailed_forecast=period_data.get("detailedForecast"),
                wind_speed=period_data.get("windSpeed"),
                wind_direction=period_data.get("windDirection"),
                icon=period_data.get("icon"),
            )
            periods.append(period)

        return Forecast(periods=periods, generated_at=datetime.now())

    def _parse_nws_alerts(self, data: dict) -> WeatherAlerts:
        """Parse NWS alerts data."""
        alerts = []

        for alert_data in data.get("features", []):
            props = alert_data.get("properties", {})

            # Extract alert ID from the NWS API response
            # The ID can be in different places depending on the API response format
            alert_id = None
            if "id" in alert_data:
                alert_id = alert_data["id"]
            elif "identifier" in props:
                alert_id = props["identifier"]
            elif "@id" in props:
                alert_id = props["@id"]

            # Parse onset and expires times
            onset = None
            expires = None

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
                areas=props.get("areaDesc", "").split("; ") if props.get("areaDesc") else [],
                id=alert_id,  # Store the NWS alert ID for unique identification
            )
            alerts.append(alert)

            if alert_id:
                logger.debug(f"Parsed alert with ID: {alert_id}")
            else:
                logger.debug(f"Parsed alert without ID, will generate: {alert.get_unique_id()}")

        logger.info(f"Parsed {len(alerts)} alerts from NWS API")
        return WeatherAlerts(alerts=alerts)

    def _parse_nws_hourly_forecast(self, data: dict) -> HourlyForecast:
        """Parse NWS hourly forecast data."""
        periods = []

        for period_data in data.get("properties", {}).get("periods", []):
            # Parse start time
            start_time_str = period_data.get("startTime")
            start_time = None
            if start_time_str:
                try:
                    # Parse ISO format: "2024-01-01T12:00:00-05:00"
                    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"Failed to parse start time: {start_time_str}")

            # Parse end time
            end_time_str = period_data.get("endTime")
            end_time = None
            if end_time_str:
                try:
                    end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"Failed to parse end time: {end_time_str}")

            period = HourlyForecastPeriod(
                start_time=start_time or datetime.now(),
                end_time=end_time,
                temperature=period_data.get("temperature"),
                temperature_unit=period_data.get("temperatureUnit", "F"),
                short_forecast=period_data.get("shortForecast"),
                wind_speed=period_data.get("windSpeed"),
                wind_direction=period_data.get("windDirection"),
                icon=period_data.get("icon"),
            )
            periods.append(period)

        return HourlyForecast(periods=periods, generated_at=datetime.now())

    def _parse_openmeteo_current_conditions(self, data: dict) -> CurrentConditions:
        """Parse OpenMeteo current conditions data."""
        current = data.get("current", {})

        return CurrentConditions(
            temperature_f=current.get("temperature_2m"),
            temperature_c=self._convert_f_to_c(current.get("temperature_2m")),
            condition=self._weather_code_to_description(current.get("weather_code")),
            humidity=current.get("relative_humidity_2m"),
            wind_speed_mph=current.get("wind_speed_10m"),
            wind_direction=self._degrees_to_cardinal(current.get("wind_direction_10m")),
            pressure_mb=current.get("pressure_msl"),
            feels_like_f=current.get("apparent_temperature"),
            last_updated=datetime.now(),
        )

    def _parse_openmeteo_forecast(self, data: dict) -> Forecast:
        """Parse OpenMeteo forecast data."""
        daily = data.get("daily", {})
        periods = []

        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        # min_temps = daily.get("temperature_2m_min", [])  # Not currently used
        weather_codes = daily.get("weather_code", [])

        for i, date in enumerate(dates):
            if i < len(max_temps) and i < len(weather_codes):
                period = ForecastPeriod(
                    name=self._format_date_name(date, i),
                    temperature=max_temps[i],
                    temperature_unit="F",
                    short_forecast=self._weather_code_to_description(weather_codes[i]),
                )
                periods.append(period)

        return Forecast(periods=periods, generated_at=datetime.now())

    def _parse_openmeteo_hourly_forecast(self, data: dict) -> HourlyForecast:
        """Parse OpenMeteo hourly forecast data."""
        periods = []
        hourly = data.get("hourly", {})

        times = hourly.get("time", [])
        temperatures = hourly.get("temperature_2m", [])
        weather_codes = hourly.get("weather_code", [])
        wind_speeds = hourly.get("wind_speed_10m", [])
        wind_directions = hourly.get("wind_direction_10m", [])

        for i, time_str in enumerate(times):
            # Parse time
            start_time = None
            if time_str:
                try:
                    # OpenMeteo format: "2024-01-01T12:00"
                    start_time = datetime.fromisoformat(time_str)
                except ValueError:
                    logger.warning(f"Failed to parse OpenMeteo time: {time_str}")
                    start_time = datetime.now()

            # Get values for this hour (with bounds checking)
            temperature = temperatures[i] if i < len(temperatures) else None
            weather_code = weather_codes[i] if i < len(weather_codes) else None
            wind_speed = wind_speeds[i] if i < len(wind_speeds) else None
            wind_direction = wind_directions[i] if i < len(wind_directions) else None

            period = HourlyForecastPeriod(
                start_time=start_time or datetime.now(),
                temperature=temperature,
                temperature_unit="F",
                short_forecast=self._weather_code_to_description(weather_code),
                wind_speed=f"{wind_speed} mph" if wind_speed is not None else None,
                wind_direction=self._degrees_to_cardinal(wind_direction),
            )
            periods.append(period)

        return HourlyForecast(periods=periods, generated_at=datetime.now())

    # Utility methods
    def _convert_mps_to_mph(self, mps: float | None) -> float | None:
        """Convert meters per second to miles per hour."""
        return mps * 2.237 if mps is not None else None

    def _convert_wind_speed_to_mph(
        self, value: float | None, unit_code: str | None
    ) -> float | None:
        """Normalize WMO wind speed units to miles per hour."""
        if value is None:
            return None
        if not unit_code:
            return value
        unit_code = unit_code.lower()
        if unit_code.endswith(("m_s-1", "mps")):
            return value * 2.237
        if unit_code.endswith(("km_h-1", "kmh")):
            return value * 0.621371
        if unit_code.endswith("mi_h-1"):
            return value
        if unit_code.endswith("kn"):
            return value * 1.15078
        return value

    def _convert_wind_speed_to_kph(
        self, value: float | None, unit_code: str | None
    ) -> float | None:
        if value is None:
            return None
        if not unit_code:
            return value
        unit_code = unit_code.lower()
        if unit_code.endswith(("m_s-1", "mps")):
            return value * 3.6
        if unit_code.endswith(("km_h-1", "kmh")):
            return value
        if unit_code.endswith("mi_h-1"):
            return value * 1.60934
        if unit_code.endswith("kn"):
            return value * 1.852
        return value

    def _convert_wind_speed_to_mph_and_kph(
        self, value: float | None, unit_code: str | None
    ) -> tuple[float | None, float | None]:
        return (
            self._convert_wind_speed_to_mph(value, unit_code),
            self._convert_wind_speed_to_kph(value, unit_code),
        )

    def _convert_pa_to_inches(self, pa: float | None) -> float | None:
        """Convert pascals to inches of mercury."""
        return pa * 0.0002953 if pa is not None else None

    def _convert_pa_to_mb(self, pa: float | None) -> float | None:
        return pa / 100 if pa is not None else None

    def _convert_f_to_c(self, fahrenheit: float | None) -> float | None:
        """Convert Fahrenheit to Celsius."""
        return (fahrenheit - 32) * 5 / 9 if fahrenheit is not None else None

    def _degrees_to_cardinal(self, degrees: float | None) -> str | None:
        """Convert wind direction degrees to cardinal direction."""
        if degrees is None:
            return None

        directions = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
        index = round(degrees / 22.5) % 16
        return directions[index]

    def _weather_code_to_description(self, code: int | None) -> str | None:
        """Convert OpenMeteo weather code to description."""
        if code is None:
            return None

        # Simplified weather code mapping
        code_map = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            95: "Thunderstorm",
        }

        return code_map.get(code, f"Weather code {code}")

    def _format_date_name(self, date_str: str, index: int) -> str:
        """Format date string to readable name."""
        if index == 0:
            return "Today"
        if index == 1:
            return "Tomorrow"
        # Parse date and format as day name
        try:
            date_obj = datetime.fromisoformat(date_str)
            return date_obj.strftime("%A")
        except (ValueError, TypeError):
            return f"Day {index + 1}"
