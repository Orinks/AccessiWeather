"""Presentation view models for weather display surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .environmental import AirQualityPresentation

if TYPE_CHECKING:
    from ...impact_summary import ImpactSummary


@dataclass(slots=True)
class Metric:
    """Key-value pair used for presenting weather measurements."""

    label: str
    value: str


@dataclass(slots=True)
class HourlyPeriodPresentation:
    """Simplified hourly forecast period for structured display."""

    time: str
    temperature: str | None
    conditions: str | None
    wind: str | None
    humidity: str | None = None
    dewpoint: str | None = None
    precipitation_probability: str | None = None
    snowfall: str | None = None
    uv_index: str | None = None
    cloud_cover: str | None = None
    wind_gust: str | None = None
    precipitation_amount: str | None = None


@dataclass(slots=True)
class ForecastPeriodPresentation:
    """Daily forecast period presentation."""

    name: str
    temperature: str | None
    conditions: str | None
    wind: str | None
    details: str | None
    precipitation_probability: str | None = None
    snowfall: str | None = None
    uv_index: str | None = None
    cloud_cover: str | None = None
    wind_gust: str | None = None
    precipitation_amount: str | None = None


@dataclass(slots=True)
class CurrentConditionsPresentation:
    """Structured view of the current conditions."""

    title: str
    description: str
    metrics: list[Metric] = field(default_factory=list)
    fallback_text: str = ""
    trends: list[str] = field(default_factory=list)
    impact_summary: ImpactSummary | None = None

    @property
    def trend_summary(self) -> list[str]:  # pragma: no cover - backward compatibility
        """Alias for legacy callers expecting ``trend_summary``."""
        return self.trends


@dataclass(slots=True)
class ForecastPresentation:
    """Structured forecast view including hourly highlights."""

    title: str
    periods: list[ForecastPeriodPresentation] = field(default_factory=list)
    hourly_periods: list[HourlyPeriodPresentation] = field(default_factory=list)
    hourly_summary: str | None = None
    generated_at: str | None = None
    fallback_text: str = ""
    daily_section_text: str = ""
    hourly_section_text: str = ""
    mobility_briefing: str | None = None
    marine_section_text: str = ""
    marine_summary: str | None = None
    marine_highlights: list[str] = field(default_factory=list)
    confidence_label: str | None = None
    summary: str | None = None
    impact_summary: ImpactSummary | None = None


@dataclass(slots=True)
class AviationPresentation:
    """Structured aviation weather presentation."""

    title: str
    airport_name: str | None = None
    station_id: str | None = None
    taf_summary: str | None = None
    raw_taf: str | None = None
    sigmets: list[str] = field(default_factory=list)
    cwas: list[str] = field(default_factory=list)
    fallback_text: str = ""


@dataclass(slots=True)
class AlertPresentation:
    """Structured weather alert presentation."""

    title: str
    severity: str | None = None
    urgency: str | None = None
    event: str | None = None
    areas: list[str] = field(default_factory=list)
    expires: str | None = None
    description: str | None = None
    instructions: str | None = None
    fallback_text: str = ""


@dataclass(slots=True)
class AlertsPresentation:
    """Collection of alert presentations with fallback text."""

    title: str
    alerts: list[AlertPresentation] = field(default_factory=list)
    fallback_text: str = ""
    change_summary: str | None = None


@dataclass(slots=True)
class SourceAttributionPresentation:
    """Presentation of data source attribution for transparency."""

    contributing_sources: list[str] = field(default_factory=list)
    failed_sources: list[str] = field(default_factory=list)
    incomplete_sections: list[str] = field(default_factory=list)
    summary_text: str = ""
    aria_label: str = ""


@dataclass(slots=True)
class WeatherPresentation:
    """Top-level presentation for all weather content."""

    location_name: str
    summary_text: str
    current_conditions: CurrentConditionsPresentation | None = None
    forecast: ForecastPresentation | None = None
    alerts: AlertsPresentation | None = None
    air_quality: AirQualityPresentation | None = None
    aviation: AviationPresentation | None = None
    trend_summary: list[str] = field(default_factory=list)
    status_messages: list[str] = field(default_factory=list)
    source_attribution: SourceAttributionPresentation | None = None

    @property
    def current(self) -> CurrentConditionsPresentation | None:  # pragma: no cover - compat
        """Backward-compatible alias for older presentation attribute name."""
        return self.current_conditions

    @current.setter
    def current(
        self, value: CurrentConditionsPresentation | None
    ) -> None:  # pragma: no cover - compat
        self.current_conditions = value
