"""
Tests for ``WeatherAlert.affected_zones`` serialization in the cache layer.

Unit 9 of the Forecast Products PR 1 plan adds an additive ``affected_zones``
field to :class:`WeatherAlert`. This module exercises:

- Round-trip through ``_serialize_alert`` / ``_deserialize_alert`` preserves
  the field exactly.
- Legacy cache entries (written before Unit 9) deserialize with
  ``affected_zones == []`` and never raise.
"""

from __future__ import annotations

from accessiweather.cache import _deserialize_alert, _serialize_alert
from accessiweather.models.alerts import WeatherAlert


def test_affected_zones_round_trip() -> None:
    """Populated ``affected_zones`` survives serialize -> deserialize unchanged."""
    alert = WeatherAlert(
        title="Special Weather Statement",
        description="A strong thunderstorm will impact portions of the region.",
        severity="Moderate",
        urgency="Expected",
        certainty="Likely",
        event="Special Weather Statement",
        headline="SPS headline",
        id="urn:oid:2.49.0.1.840.0.test",
        source="NWS",
        affected_zones=["PHZ007", "PHZ008"],
    )

    payload = _serialize_alert(alert)
    assert payload["affected_zones"] == ["PHZ007", "PHZ008"]

    restored = _deserialize_alert(payload)
    assert restored.affected_zones == ["PHZ007", "PHZ008"]
    # All other fields still make it across — sanity check on the additive change.
    assert restored.id == alert.id
    assert restored.event == alert.event


def test_affected_zones_omitted_when_empty() -> None:
    """Empty ``affected_zones`` is omitted from the payload — legacy shape."""
    alert = WeatherAlert(
        title="Test Alert",
        description="Body",
    )
    payload = _serialize_alert(alert)
    assert "affected_zones" not in payload


def test_legacy_cache_entry_deserializes_with_empty_zones() -> None:
    """A cache dict written before Unit 9 deserializes with ``affected_zones == []``."""
    legacy_payload = {
        "title": "Flood Warning",
        "description": "Legacy alert body",
        "severity": "Severe",
        "urgency": "Immediate",
        "certainty": "Observed",
        "event": "Flood Warning",
        "headline": None,
        "instruction": None,
        "onset": None,
        "expires": None,
        "areas": ["Somerset County"],
        "id": "legacy-1",
        "source": "NWS",
        # Note: no ``affected_zones`` key — this is the legacy shape.
    }

    restored = _deserialize_alert(legacy_payload)

    assert restored.affected_zones == []
    assert restored.title == "Flood Warning"
    assert restored.areas == ["Somerset County"]
