from accessiweather.models import CurrentConditions
from accessiweather.weather_event_pipeline import (
    WeatherEvent,
    WeatherEventDispatcher,
    WeatherEventStore,
    should_emit_current_conditions_event,
)


class DummyNotifier:
    """Capture toast calls for assertions."""

    def __init__(self):
        """Initialize capture storage."""
        self.calls = []

    def send_notification(self, **kwargs):
        self.calls.append(kwargs)
        return True


class DummyAnnouncer:
    """Capture spoken announcements for assertions."""

    def __init__(self):
        """Initialize capture storage."""
        self.messages = []

    def announce(self, text: str):
        self.messages.append(text)


def test_store_ring_buffer_and_unread_counts():
    store = WeatherEventStore(max_size=2)

    e1 = WeatherEvent(channel="urgent", headline="A")
    e2 = WeatherEvent(channel="now", headline="B")
    e3 = WeatherEvent(channel="system", headline="C")

    store.append(e1)
    store.append(e2)
    store.append(e3)

    assert store.latest().headline == "C"
    assert store.latest(channel="now").headline == "B"

    counts = store.unread_counts()
    assert counts["system"] == 1
    assert counts["urgent"] == 0
    assert counts["total"] == 2


def test_dispatcher_writes_store_and_announces_without_toast_when_disabled():
    notifier = DummyNotifier()
    store = WeatherEventStore()
    dispatcher = WeatherEventDispatcher(store, notifier=notifier)
    dispatcher.announcer = DummyAnnouncer()

    event = WeatherEvent(channel="now", headline="Now", speech_text="Rain starting")
    dispatcher.dispatch_event(event, announce=True, mirror_toast=False)

    assert store.latest() == event
    assert dispatcher.announcer.messages == ["Rain starting"]
    assert notifier.calls == []


def test_dispatcher_mirrors_toast_when_enabled():
    notifier = DummyNotifier()
    store = WeatherEventStore()
    dispatcher = WeatherEventDispatcher(store, notifier=notifier)
    dispatcher.announcer = DummyAnnouncer()

    event = WeatherEvent(channel="urgent", headline="Alert", speech_text="Storm warning")
    dispatcher.dispatch_event(event, announce=False, mirror_toast=True)

    assert len(notifier.calls) == 1
    assert notifier.calls[0]["title"] == "Alert"


def test_should_emit_current_conditions_event_threshold_gating():
    prev = CurrentConditions(temperature=70.0, wind_speed=4.0, condition="Clear")

    curr_small = CurrentConditions(temperature=71.0, wind_speed=6.0, condition="Clear")
    emit_small, _ = should_emit_current_conditions_event(prev, curr_small)
    assert emit_small is False

    curr_temp_jump = CurrentConditions(temperature=73.0, wind_speed=6.0, condition="Clear")
    emit_temp, reason_temp = should_emit_current_conditions_event(prev, curr_temp_jump)
    assert emit_temp is True
    assert "Temperature changed" in reason_temp

    curr_condition_change = CurrentConditions(temperature=70.5, wind_speed=5.0, condition="Rain")
    emit_cond, reason_cond = should_emit_current_conditions_event(prev, curr_condition_change)
    assert emit_cond is True
    assert "Conditions changed" in reason_cond
