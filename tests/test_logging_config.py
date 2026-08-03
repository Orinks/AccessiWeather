"""Tests for default file logging and its portable-mode destination."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from accessiweather import logging_config
from accessiweather.main import setup_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """Detach and restore root handlers so tests never leak log files."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    root.handlers = []
    try:
        yield
    finally:
        for handler in root.handlers[:]:
            handler.close()
            root.removeHandler(handler)
        root.handlers = saved_handlers
        root.setLevel(saved_level)


def _file_handlers() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if hasattr(h, "baseFilename")]


def _log_path() -> Path:
    handlers = _file_handlers()
    assert handlers, "expected a rotating file handler on the root logger"
    return Path(handlers[0].baseFilename)


def test_file_logging_is_on_by_default(tmp_path):
    setup_logging(config_dir=str(tmp_path))

    assert _log_path() == tmp_path / "logs" / "accessiweather.log"


def test_log_records_actually_reach_the_file(tmp_path):
    setup_logging(config_dir=str(tmp_path))
    logging.getLogger("accessiweather.test").info("radio auto-tune skipped")
    for handler in _file_handlers():
        handler.flush()

    assert "radio auto-tune skipped" in _log_path().read_text(encoding="utf-8")


def test_portable_copy_logs_beside_its_own_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    setup_logging(portable_mode=True)

    # Portable copies must not write into the user profile.
    assert _log_path() == tmp_path.resolve() / "config" / "logs" / "accessiweather.log"


def test_explicit_config_dir_wins_over_portable_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "accessiweather.paths.detect_portable_mode",
        lambda: pytest.fail("portable detection must be skipped for --config-dir"),
    )

    setup_logging(config_dir=str(tmp_path))

    assert _log_path() == tmp_path / "logs" / "accessiweather.log"


def test_debug_flag_sets_debug_level(tmp_path):
    setup_logging(debug=True, config_dir=str(tmp_path))

    assert logging.getLogger().level == logging.DEBUG


def test_unwritable_log_directory_falls_back_to_console(tmp_path, monkeypatch):
    def _boom(**_kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(logging_config, "resolve_default_config_root", _boom)

    setup_logging(config_dir=str(tmp_path))

    # The app must still start and still log somewhere.
    assert _file_handlers() == []
    assert logging.getLogger().handlers
