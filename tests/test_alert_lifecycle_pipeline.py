"""Tests for alert lifecycle diff wired into WeatherClient + WeatherPresenter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from accessiweather.alert_lifecycle import AlertLifecycleDiff
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    WeatherAlerts,
    WeatherData,
)
from accessiweather.models.alerts import WeatherAlert
from accessiweather.weather_client import WeatherClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alert(
    alert_id: str, title: str = "Test Alert", severity: str = "Moderate"
) -> WeatherAlert:
    """Create a minimal WeatherAlert with a fixed id."""
    return WeatherAlert(
        title=title,
        description="Description text.",
        severity=severity,
        urgency="Expected",
        id=alert_id,
    )


def _make_alerts(*ids: str) -> WeatherAlerts:
    return WeatherAlerts(alerts=[_make_alert(aid) for aid in ids])


def _make_nws_return(
    alerts: WeatherAlerts,
) -> tuple:
    """Return a tuple matching _fetch_nws_data's return signature."""
    return (
        CurrentConditions(temperature=72.0),
        Forecast(periods=[]),
        "Discussion text",
        None,
        alerts,
        HourlyForecast(periods=[]),
    )


@pytest.fixture
def nws_client() -> WeatherClient:
    """WeatherClient configured to use NWS (non-auto) so we can test single-source path."""
    settings = AppSettings(enable_alerts=True)
    client = WeatherClient(settings=settings)
    client.data_source = "nws"
    return client


@pytest.fixture
def us_location() -> Location:
    return Location(name="NYC", latitude=40.7128, longitude=-74.0060, country_code="US")


# ---------------------------------------------------------------------------
# _location_key
# ---------------------------------------------------------------------------


class TestLocationKey:
    def test_returns_lat_lon_string(self):
        client = WeatherClient()
        loc = Location(name="Test", latitude=40.7128, longitude=-74.0060)
        key = client._location_key(loc)
        assert key == "40.7128,-74.0060"

    def test_same_location_same_key(self):
        client = WeatherClient()
        loc_a = Location(name="A", latitude=40.7128, longitude=-74.0060)
        loc_b = Location(name="B", latitude=40.7128, longitude=-74.0060)
        assert client._location_key(loc_a) == client._location_key(loc_b)

    def test_different_locations_different_keys(self):
        client = WeatherClient()
        loc_a = Location(name="NYC", latitude=40.7128, longitude=-74.0060)
        loc_b = Location(name="LA", latitude=34.0522, longitude=-118.2437)
        assert client._location_key(loc_a) != client._location_key(loc_b)


# ---------------------------------------------------------------------------
# NWS single-source path — alert lifecycle diff
# ---------------------------------------------------------------------------


class TestNWSAlertLifecyclePipeline:
    """Integration tests for the alert lifecycle diff on the NWS single-source path."""

    @pytest.mark.asyncio
    async def test_first_fetch_all_alerts_new(self, nws_client, us_location):
        """First fetch for a location: all current alerts appear as NEW."""
        incoming_alerts = _make_alerts("alert-1", "alert-2")

        with (
            patch.object(nws_client, "_fetch_nws_data", new_callable=AsyncMock) as mock_nws,
            patch.object(nws_client, "_launch_enrichment_tasks", return_value={}),
            patch.object(nws_client, "_await_enrichments", new_callable=AsyncMock),
        ):
            mock_nws.return_value = _make_nws_return(incoming_alerts)
            weather_data = await nws_client._do_fetch_weather_data(us_location)

        diff = weather_data.alert_lifecycle_diff
        assert diff is not None, "alert_lifecycle_diff should be set on first fetch"
        assert len(diff.new_alerts) == 2
        new_ids = {c.alert_id for c in diff.new_alerts}
        assert new_ids == {"alert-1", "alert-2"}
        assert diff.has_changes is True

    @pytest.mark.asyncio
    async def test_second_fetch_same_alerts_no_changes(self, nws_client, us_location):
        """Second fetch with identical alerts: has_changes is False."""
        same_alerts = _make_alerts("alert-1", "alert-2")

        with (
            patch.object(nws_client, "_fetch_nws_data", new_callable=AsyncMock) as mock_nws,
            patch.object(nws_client, "_launch_enrichment_tasks", return_value={}),
            patch.object(nws_client, "_await_enrichments", new_callable=AsyncMock),
        ):
            mock_nws.return_value = _make_nws_return(same_alerts)
            # First fetch — primes _previous_alerts
            await nws_client._do_fetch_weather_data(us_location)
            # Second fetch — same alerts
            weather_data = await nws_client._do_fetch_weather_data(us_location)

        diff = weather_data.alert_lifecycle_diff
        assert diff is not None
        assert diff.has_changes is False, "No change expected when alerts are identical"

    @pytest.mark.asyncio
    async def test_second_fetch_cancelled_alert_detected(self, nws_client, us_location):
        """Second fetch with one alert removed: cancelled_alerts is non-empty."""
        first_alerts = _make_alerts("alert-1", "alert-2")
        second_alerts = _make_alerts("alert-1")  # alert-2 dropped

        with (
            patch.object(nws_client, "_fetch_nws_data", new_callable=AsyncMock) as mock_nws,
            patch.object(nws_client, "_launch_enrichment_tasks", return_value={}),
            patch.object(nws_client, "_await_enrichments", new_callable=AsyncMock),
        ):
            mock_nws.return_value = _make_nws_return(first_alerts)
            await nws_client._do_fetch_weather_data(us_location)

            mock_nws.return_value = _make_nws_return(second_alerts)
            weather_data = await nws_client._do_fetch_weather_data(us_location)

        diff = weather_data.alert_lifecycle_diff
        assert diff is not None
        assert len(diff.cancelled_alerts) == 1
        assert diff.cancelled_alerts[0].alert_id == "alert-2"
        assert diff.has_changes is True

    @pytest.mark.asyncio
    async def test_weather_data_has_alert_lifecycle_diff_field(self, nws_client, us_location):
        """WeatherData.alert_lifecycle_diff is not None after any NWS fetch."""
        with (
            patch.object(nws_client, "_fetch_nws_data", new_callable=AsyncMock) as mock_nws,
            patch.object(nws_client, "_launch_enrichment_tasks", return_value={}),
            patch.object(nws_client, "_await_enrichments", new_callable=AsyncMock),
        ):
            mock_nws.return_value = _make_nws_return(_make_alerts("alert-x"))
            weather_data = await nws_client._do_fetch_weather_data(us_location)

        assert hasattr(weather_data, "alert_lifecycle_diff")
        assert isinstance(weather_data.alert_lifecycle_diff, AlertLifecycleDiff)

    @pytest.mark.asyncio
    async def test_previous_alerts_cache_updated_per_location(self, nws_client):
        """_previous_alerts is keyed per location and not mixed across locations."""
        loc_a = Location(name="A", latitude=40.0000, longitude=-74.0000, country_code="US")
        loc_b = Location(name="B", latitude=35.0000, longitude=-80.0000, country_code="US")
        alerts_a = _make_alerts("alert-a")
        alerts_b = _make_alerts("alert-b")

        with (
            patch.object(nws_client, "_fetch_nws_data", new_callable=AsyncMock) as mock_nws,
            patch.object(nws_client, "_launch_enrichment_tasks", return_value={}),
            patch.object(nws_client, "_await_enrichments", new_callable=AsyncMock),
        ):
            mock_nws.return_value = _make_nws_return(alerts_a)
            await nws_client._do_fetch_weather_data(loc_a)

            mock_nws.return_value = _make_nws_return(alerts_b)
            await nws_client._do_fetch_weather_data(loc_b)

        key_a = nws_client._location_key(loc_a)
        key_b = nws_client._location_key(loc_b)

        assert key_a in nws_client._previous_alerts
        assert key_b in nws_client._previous_alerts
        # Ensure they are stored independently
        assert nws_client._previous_alerts[key_a].alerts[0].id == "alert-a"
        assert nws_client._previous_alerts[key_b].alerts[0].id == "alert-b"


# ---------------------------------------------------------------------------
# WeatherData dataclass — field presence
# ---------------------------------------------------------------------------


class TestWeatherDataAlertLifecycleField:
    def test_alert_lifecycle_diff_defaults_to_none(self):
        """WeatherData.alert_lifecycle_diff defaults to None."""
        loc = Location(name="Test", latitude=0.0, longitude=0.0)
        wd = WeatherData(location=loc)
        assert wd.alert_lifecycle_diff is None

    def test_alert_lifecycle_diff_can_be_set(self):
        """WeatherData.alert_lifecycle_diff can be assigned an AlertLifecycleDiff."""
        loc = Location(name="Test", latitude=0.0, longitude=0.0)
        wd = WeatherData(location=loc)
        diff = AlertLifecycleDiff()
        wd.alert_lifecycle_diff = diff
        assert wd.alert_lifecycle_diff is diff


# ---------------------------------------------------------------------------
# Auto-mode lightweight poll must aggregate duplicates so the diff against
# the full-refresh snapshot (which stores MERGED alerts) doesn't see phantom
# updates every 10 minutes.
# ---------------------------------------------------------------------------


class TestLightweightPollMatchesFullRefreshAggregation:
    """
    Regression tests for renotification caused by raw/merged alternation.

    Full refresh (auto mode) stores ``AlertAggregator.aggregate_alerts(...)``
    output in ``_previous_alerts``. The lightweight poll used to store RAW
    NWS alerts, so the cache alternated between merged and raw on every
    refresh cycle. That caused ``diff_alerts`` to fire phantom "updated"
    notifications every ``update_interval_minutes`` even when nothing changed.
    """

    @pytest.fixture
    def auto_client(self) -> WeatherClient:
        settings = AppSettings(enable_alerts=True)
        client = WeatherClient(settings=settings)
        client.data_source = "auto"
        return client

    @pytest.mark.asyncio
    async def test_no_phantom_updates_when_full_refresh_merged_same_alerts(
        self, auto_client, us_location
    ):
        """Priming the cache with merged alerts must not trigger updates on poll."""
        from accessiweather.weather_client_alerts import AlertAggregator

        # Two overlapping NWS alerts (same event, overlapping areas) that
        # the full refresh's AlertAggregator will merge into a single alert
        # with the longer description.
        raw = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    id="nws-urn-alert-a",
                    title="Winter Storm Warning",
                    event="Winter Storm Warning",
                    description="Short description.",
                    severity="Severe",
                    urgency="Expected",
                    headline="Winter Storm Warning in effect",
                    instruction="Take precautions.",
                    areas=["County X"],
                    source="NWS",
                ),
                WeatherAlert(
                    id="nws-urn-alert-b",
                    title="Winter Storm Warning",
                    event="Winter Storm Warning",
                    description="A much longer and more detailed description text.",
                    severity="Severe",
                    urgency="Expected",
                    headline="Winter Storm Warning in effect",
                    instruction="Take precautions.",
                    areas=["County X", "County Y"],
                    source="NWS",
                ),
            ]
        )
        merged = AlertAggregator().aggregate_alerts(raw, None)
        assert len(merged.alerts) == 1, "sanity: overlapping NWS alerts must merge"

        # Simulate the post-full-refresh cache state: merged alerts stored.
        loc_key = auto_client._location_key(us_location)
        auto_client._previous_alerts[loc_key] = merged

        # Simulate lightweight poll: mock NWS to return the same raw alerts.
        auto_client._get_nws_discussion_only = AsyncMock(return_value=("AFD text", None))
        auto_client._get_nws_alerts = AsyncMock(return_value=raw)
        auto_client._fetch_nws_cancel_references = AsyncMock(return_value=set())

        weather_data = await auto_client.get_notification_event_data(us_location)

        diff = weather_data.alert_lifecycle_diff
        assert diff is not None
        # No phantom new/updated alerts: the lightweight poll must see the
        # same canonical alert shape that the full refresh stored.
        assert diff.new_alerts == []
        assert diff.updated_alerts == []
        assert diff.escalated_alerts == []
        assert diff.extended_alerts == []
        assert diff.has_changes is False, (
            f"Phantom change detected: {diff.summary!r}. "
            "Lightweight poll must aggregate the same way full refresh does."
        )

    @pytest.mark.asyncio
    async def test_cached_previous_alerts_match_full_refresh_shape(self, auto_client, us_location):
        """
        After a lightweight poll, _previous_alerts must hold the aggregated form.

        If the lightweight poll stored raw alerts, the next full refresh would
        diff merged-vs-raw and fire spurious updates. Store the aggregated
        form so both paths round-trip to the same snapshot.
        """
        from accessiweather.weather_client_alerts import AlertAggregator

        raw = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    id="nws-urn-alert-a",
                    title="Flood Warning",
                    event="Flood Warning",
                    description="Short.",
                    severity="Severe",
                    urgency="Expected",
                    areas=["County X"],
                    source="NWS",
                ),
                WeatherAlert(
                    id="nws-urn-alert-b",
                    title="Flood Warning",
                    event="Flood Warning",
                    description="Longer description with more detail.",
                    severity="Severe",
                    urgency="Expected",
                    areas=["County X"],
                    source="NWS",
                ),
            ]
        )
        expected_merged = AlertAggregator().aggregate_alerts(raw, None)

        auto_client._get_nws_discussion_only = AsyncMock(return_value=(None, None))
        auto_client._get_nws_alerts = AsyncMock(return_value=raw)
        auto_client._fetch_nws_cancel_references = AsyncMock(return_value=set())

        await auto_client.get_notification_event_data(us_location)

        loc_key = auto_client._location_key(us_location)
        cached = auto_client._previous_alerts[loc_key]
        cached_ids = sorted(a.get_unique_id() for a in cached.alerts)
        expected_ids = sorted(a.get_unique_id() for a in expected_merged.alerts)
        assert cached_ids == expected_ids, (
            "Lightweight poll must store aggregated alerts so the next full "
            "refresh diff doesn't fire spurious updates."
        )
        cached_hashes = sorted(a.get_content_hash() for a in cached.alerts)
        expected_hashes = sorted(a.get_content_hash() for a in expected_merged.alerts)
        assert cached_hashes == expected_hashes
