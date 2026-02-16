"""Tests for the ThreadManager utility."""

import threading
import time

import pytest

from accessiweather.utils.thread_manager import ThreadManager


@pytest.fixture(autouse=True)
def _fresh_manager(monkeypatch):
    """Ensure each test gets a fresh ThreadManager singleton."""
    monkeypatch.setattr(ThreadManager, "_instance", None)


def _make_worker(stop_event: threading.Event, work_time: float = 0.0):
    """Return a thread that waits on *stop_event* or sleeps *work_time*."""

    def _run():
        if work_time:
            stop_event.wait(work_time)
        else:
            stop_event.wait()

    return threading.Thread(target=_run, daemon=True)


class TestSingleton:
    def test_instance_returns_same_object(self):
        a = ThreadManager.instance()
        b = ThreadManager.instance()
        assert a is b

    def test_fresh_fixture_resets_singleton(self):
        """The autouse fixture should give us a new instance each test."""
        mgr = ThreadManager.instance()
        assert len(mgr) == 0


class TestRegisterUnregister:
    def test_register_not_started_thread(self):
        mgr = ThreadManager.instance()
        t = threading.Thread(target=lambda: None, daemon=True)
        result = mgr.register_thread(t, name="test-thread")
        assert result is t
        assert len(mgr) == 1

    def test_register_started_thread(self):
        mgr = ThreadManager.instance()
        stop = threading.Event()
        t = _make_worker(stop)
        t.start()
        try:
            mgr.register_thread(t, stop_event=stop, name="started")
            assert len(mgr) == 1
        finally:
            stop.set()
            t.join(2)

    def test_register_none_returns_none(self):
        mgr = ThreadManager.instance()
        assert mgr.register_thread(None) is None
        assert len(mgr) == 0

    def test_unregister_existing(self):
        mgr = ThreadManager.instance()
        t = threading.Thread(target=lambda: None, daemon=True)
        tid = id(t)
        mgr.register_thread(t, name="to-remove")
        mgr.unregister_thread(tid)
        assert len(mgr) == 0

    def test_unregister_nonexistent_is_safe(self):
        mgr = ThreadManager.instance()
        mgr.unregister_thread(999999)  # should not raise


class TestGetters:
    def test_get_threads(self):
        mgr = ThreadManager.instance()
        t1 = threading.Thread(target=lambda: None, daemon=True)
        t2 = threading.Thread(target=lambda: None, daemon=True)
        mgr.register_thread(t1)
        mgr.register_thread(t2)
        threads = mgr.get_threads()
        assert len(threads) == 2

    def test_get_stop_events(self):
        mgr = ThreadManager.instance()
        stop = threading.Event()
        t = threading.Thread(target=lambda: None, daemon=True)
        mgr.register_thread(t, stop_event=stop)
        events = mgr.get_stop_events()
        assert len(events) == 1
        assert events[0] is stop

    def test_get_active_threads(self):
        mgr = ThreadManager.instance()
        stop = threading.Event()
        t = _make_worker(stop)
        t.start()
        mgr.register_thread(t, stop_event=stop, name="active")
        try:
            active = mgr.get_active_threads()
            assert len(active) == 1
        finally:
            stop.set()
            t.join(2)

    def test_get_active_thread_info(self):
        mgr = ThreadManager.instance()
        stop = threading.Event()
        t = _make_worker(stop)
        t.start()
        mgr.register_thread(t, stop_event=stop, name="info-test")
        try:
            info = mgr.get_active_thread_info()
            assert len(info) == 1
            assert info[0]["name"] == "info-test"
            assert info[0]["has_stop_event"] is True
        finally:
            stop.set()
            t.join(2)

    def test_is_thread_running(self):
        mgr = ThreadManager.instance()
        stop = threading.Event()
        t = _make_worker(stop)
        t.start()
        tid = t.ident
        mgr.register_thread(t, stop_event=stop, name="running-check")
        try:
            assert mgr.is_thread_running(tid) is True
        finally:
            stop.set()
            t.join(2)

    def test_is_thread_running_unknown_id(self):
        mgr = ThreadManager.instance()
        assert mgr.is_thread_running(999999) is False


class TestStopAllThreads:
    def test_stop_all_clean(self):
        mgr = ThreadManager.instance()
        stop = threading.Event()
        t = _make_worker(stop)
        t.start()
        mgr.register_thread(t, stop_event=stop, name="clean-stop")
        remaining = mgr.stop_all_threads(timeout=2.0)
        assert remaining == []
        assert not t.is_alive()

    def test_stop_all_no_threads(self):
        mgr = ThreadManager.instance()
        remaining = mgr.stop_all_threads()
        assert remaining == []

    def test_stop_all_stubborn_thread(self):
        """A thread that ignores the stop event should appear in remaining."""
        mgr = ThreadManager.instance()
        stop = threading.Event()

        def _stubborn():
            # Ignore stop event, just sleep
            time.sleep(10)

        t = threading.Thread(target=_stubborn, daemon=True)
        t.start()
        mgr.register_thread(t, stop_event=stop, name="stubborn")
        remaining = mgr.stop_all_threads(timeout=0.3)
        assert "stubborn" in remaining

    def test_stop_multiple_threads(self):
        mgr = ThreadManager.instance()
        stops = []
        for i in range(5):
            stop = threading.Event()
            t = _make_worker(stop)
            t.start()
            mgr.register_thread(t, stop_event=stop, name=f"multi-{i}")
            stops.append(stop)
        remaining = mgr.stop_all_threads(timeout=3.0)
        assert remaining == []


class TestClearAndDunder:
    def test_clear(self):
        mgr = ThreadManager.instance()
        t = threading.Thread(target=lambda: None, daemon=True)
        stop = threading.Event()
        mgr.register_thread(t, stop_event=stop)
        mgr.clear()
        assert len(mgr) == 0
        assert mgr.get_stop_events() == []

    def test_bool_empty(self):
        mgr = ThreadManager.instance()
        assert not mgr

    def test_bool_nonempty(self):
        mgr = ThreadManager.instance()
        t = threading.Thread(target=lambda: None, daemon=True)
        mgr.register_thread(t)
        assert mgr


class TestModuleLevelFunctions:
    def test_module_functions(self):
        from accessiweather.utils.thread_manager import (
            get_thread_manager,
            register_thread,
            stop_all_threads,
            unregister_thread,
        )

        mgr = get_thread_manager()
        assert isinstance(mgr, ThreadManager)

        stop = threading.Event()
        t = _make_worker(stop)
        t.start()
        register_thread(t, stop_event=stop, name="module-fn")

        remaining = stop_all_threads(timeout=2.0)
        assert remaining == []

        # Unregister should not raise even for non-existent
        unregister_thread(999999)
