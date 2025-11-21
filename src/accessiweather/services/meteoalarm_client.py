"""Client for retrieving MeteoAlarm severe weather alerts."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from ..models import Location, WeatherAlert, WeatherAlerts
from ..utils.retry_utils import async_retry_with_backoff

logger = logging.getLogger(__name__)


class MeteoAlarmClient:
    """Fetch MeteoAlarm CAP feeds for international severe weather alerts."""

    CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2", "atom": "http://www.w3.org/2005/Atom"}

    def __init__(self, user_agent: str = "AccessiWeather/2.0", timeout: float = 10.0):
        """
        Initialize the client.

        Args:
        ----
            user_agent: HTTP User-Agent header value.
            timeout: Request timeout in seconds.

        """
        self.user_agent = user_agent
        self.timeout = timeout
        self._endpoints = (
            "https://www.meteoalarm.org/api/v1/product/cap",
            "https://www.meteoalarm.org/api/v1/product/feed",
        )

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=15.0)
    async def fetch_alerts(self, location: Location) -> WeatherAlerts:
        """Fetch alerts for the provided location."""
        if location is None:
            return WeatherAlerts(alerts=[])

        headers = {"User-Agent": self.user_agent}
        params = {"lat": location.latitude, "lon": location.longitude, "format": "cap"}
        alerts: list[WeatherAlert] = []

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for endpoint in self._endpoints:
                try:
                    response = await client.get(endpoint, params=params, headers=headers)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"MeteoAlarm request failed for {endpoint}: {exc}")
                    continue

                if response.status_code != httpx.codes.OK:
                    logger.debug(
                        "MeteoAlarm endpoint %s returned status %s", endpoint, response.status_code
                    )
                    continue

                content_type = response.headers.get("content-type", "").lower()
                try:
                    if "json" in content_type:
                        parsed_alerts = self._parse_geojson(response.json())
                    else:
                        parsed_alerts = self._parse_cap_documents(response.text)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"Failed to parse MeteoAlarm response: {exc}")
                    continue

                if parsed_alerts:
                    alerts.extend(parsed_alerts)
                    break

        if not alerts:
            return WeatherAlerts(alerts=[])

        deduped = self._deduplicate(alerts)
        logger.info("Retrieved %s MeteoAlarm alerts for %s", len(deduped), location.name)
        return WeatherAlerts(alerts=deduped)

    def _parse_geojson(self, payload: Any) -> list[WeatherAlert]:
        features: Iterable[dict[str, Any]] = []
        if isinstance(payload, dict):
            if isinstance(payload.get("features"), list):
                features = payload["features"]
            elif isinstance(payload.get("entries"), list):
                features = payload["entries"]

        alerts: list[WeatherAlert] = []
        for feature in features:
            props = feature.get("properties") if isinstance(feature, dict) else None
            if not isinstance(props, dict):
                props = feature if isinstance(feature, dict) else {}

            event = props.get("event") or props.get("title")
            headline = props.get("headline") or event
            description = props.get("description") or headline or event or "Weather alert"
            severity = props.get("severity") or "Unknown"
            urgency = props.get("urgency") or "Unknown"
            certainty = props.get("certainty") or "Unknown"
            identifier = props.get("id") or props.get("identifier")

            expires = self._parse_iso(props.get("expires") or props.get("expiry"))
            onset = self._parse_iso(props.get("onset"))

            areas: list[str] = []
            area_data = props.get("areas")
            if isinstance(area_data, list):
                areas = [str(area) for area in area_data if area]
            area_desc = props.get("areaDesc") or props.get("area_name")
            if area_desc:
                areas.append(str(area_desc))

            alert = WeatherAlert(
                title=headline or event or "Weather Alert",
                description=str(description),
                severity=str(severity).title() if severity else "Unknown",
                urgency=str(urgency).title() if urgency else "Unknown",
                certainty=str(certainty).title() if certainty else "Unknown",
                event=str(event) if event else None,
                headline=str(headline) if headline else None,
                instruction=props.get("instruction"),
                onset=onset,
                expires=expires,
                areas=areas,
                id=str(identifier) if identifier else None,
                source="MeteoAlarm",
            )
            alerts.append(alert)

        return alerts

    def _parse_cap_documents(self, xml_text: str) -> list[WeatherAlert]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:  # noqa: BLE001
            logger.debug(f"Invalid MeteoAlarm CAP document: {exc}")
            return []

        alerts: list[WeatherAlert] = []

        if root.tag.endswith("alert"):
            parsed = self._parse_cap_alert(root)
            if parsed:
                alerts.extend(parsed)
        elif root.tag.endswith("feed"):
            for entry in root.findall("atom:entry", self.CAP_NS):
                content = entry.find("atom:content", self.CAP_NS)
                if content is None:
                    continue
                alert_elem = content.find("cap:alert", self.CAP_NS)
                if alert_elem is not None:
                    parsed = self._parse_cap_alert(alert_elem)
                    if parsed:
                        alerts.extend(parsed)
        else:
            for alert_elem in root.findall(".//cap:alert", self.CAP_NS):
                parsed = self._parse_cap_alert(alert_elem)
                if parsed:
                    alerts.extend(parsed)

        return alerts

    def _parse_cap_alert(self, alert_elem: ET.Element) -> list[WeatherAlert]:
        infos = alert_elem.findall("cap:info", self.CAP_NS)
        if not infos:
            infos = alert_elem.findall("info")
        if not infos:
            return []

        info = self._select_info(infos)
        if info is None:
            return []

        event = self._find_text(info, "event")
        severity = self._find_text(info, "severity") or "Unknown"
        urgency = self._find_text(info, "urgency") or "Unknown"
        certainty = self._find_text(info, "certainty") or "Unknown"
        headline = self._find_text(info, "headline")
        description = self._find_text(info, "description") or headline or event or "Weather alert"
        instruction = self._find_text(info, "instruction")
        expires = self._parse_iso(self._find_text(info, "expires"))
        onset = self._parse_iso(self._find_text(info, "onset"))

        areas: list[str] = []
        for area in info.findall("cap:area", self.CAP_NS):
            desc = self._find_text(area, "areaDesc")
            if desc:
                areas.append(desc)
        if not areas:
            area_desc = self._find_text(info, "areaDesc")
            if area_desc:
                areas.append(area_desc)

        identifier = alert_elem.findtext("cap:identifier", namespaces=self.CAP_NS)
        if identifier is None:
            identifier = alert_elem.findtext("identifier")

        alert = WeatherAlert(
            title=headline or event or "Weather Alert",
            description=description,
            severity=severity.title() if severity else "Unknown",
            urgency=urgency.title() if urgency else "Unknown",
            certainty=certainty.title() if certainty else "Unknown",
            event=event,
            headline=headline,
            instruction=instruction,
            onset=onset,
            expires=expires,
            areas=areas,
            id=identifier,
            source="MeteoAlarm",
        )
        return [alert]

    def _select_info(self, infos: Iterable[ET.Element]) -> ET.Element | None:
        def _lang(element: ET.Element) -> str:
            lang = element.findtext("cap:language", namespaces=self.CAP_NS) or element.findtext(
                "language"
            )
            return (lang or "").lower()

        english = [info for info in infos if _lang(info).startswith("en")]
        if english:
            return english[0]
        return next(iter(infos), None)

    def _find_text(self, element: ET.Element, tag: str) -> str | None:
        value = element.findtext(f"cap:{tag}", namespaces=self.CAP_NS)
        if value is None:
            value = element.findtext(tag)
        return value.strip() if isinstance(value, str) else value

    def _parse_iso(self, value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _deduplicate(self, alerts: Iterable[WeatherAlert]) -> list[WeatherAlert]:
        seen = set()
        deduped: list[WeatherAlert] = []
        for alert in alerts:
            uid = alert.get_unique_id()
            if uid in seen:
                continue
            seen.add(uid)
            deduped.append(alert)
        return deduped[:10]
