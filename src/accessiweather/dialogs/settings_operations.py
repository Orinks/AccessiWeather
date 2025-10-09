"""Async operations and helpers for the settings dialog."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import platform
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover - fallback for Python <3.8
    try:  # pragma: no cover - optional dependency
        import importlib_metadata  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - metadata unavailable
        importlib_metadata = None  # type: ignore[assignment]

from . import settings_handlers

logger = logging.getLogger(__name__)
LOG_PREFIX = "SettingsOperations"


async def _call_dialog_method(dialog, method_name, *args, **kwargs):
    """Call a dialog message method using the dialog window when available."""
    try:
        if dialog.window and hasattr(dialog.window, method_name):
            method = getattr(dialog.window, method_name)
            result = await method(*args, **kwargs)
        else:
            method = getattr(dialog.app.main_window, method_name)
            result = await method(*args, **kwargs)
    except Exception:
        method = getattr(dialog.app.main_window, method_name)
        result = await method(*args, **kwargs)
    finally:
        with contextlib.suppress(Exception):
            dialog._ensure_dialog_focus()
    return result


async def reset_to_defaults(dialog):
    """Reset configuration to defaults and refresh the dialog UI."""
    try:
        dialog._ensure_dialog_focus()

        logger.info("%s: Reset to defaults requested", LOG_PREFIX)
        success = False
        with contextlib.suppress(Exception):
            success = dialog.config_manager.reset_to_defaults()

        if not success:
            await dialog._show_dialog_error(
                "Settings Error",
                "Failed to reset configuration to defaults.",
            )
            return

        with contextlib.suppress(Exception):
            dialog.current_settings = dialog.config_manager.get_settings()

        settings_handlers.apply_settings_to_ui(dialog)

        if getattr(dialog, "update_status_label", None):
            dialog.update_status_label.text = "Settings were reset to defaults"

        await _call_dialog_method(
            dialog,
            "info_dialog",
            "Settings Reset",
            "All settings were reset to defaults.",
        )

    except Exception as exc:
        logger.exception("%s: Failed during reset-to-defaults operation", LOG_PREFIX)
        with contextlib.suppress(Exception):
            await dialog._show_dialog_error(
                "Settings Error",
                f"An error occurred while resetting to defaults: {exc}",
            )


async def full_data_reset(dialog):
    """Perform a full data reset and refresh the dialog."""
    try:
        dialog._ensure_dialog_focus()

        logger.info("%s: Full data reset requested", LOG_PREFIX)
        success = False
        with contextlib.suppress(Exception):
            success = dialog.config_manager.reset_all_data()

        if not success:
            await dialog._show_dialog_error(
                "Data Reset Error",
                "Failed to reset all application data.",
            )
            return

        with contextlib.suppress(Exception):
            dialog.current_settings = dialog.config_manager.get_settings()

        settings_handlers.apply_settings_to_ui(dialog)

        if getattr(dialog, "update_status_label", None):
            dialog.update_status_label.text = "All application data were reset"

        await _call_dialog_method(
            dialog,
            "info_dialog",
            "Data Reset",
            "All application data were reset.",
        )

    except Exception as exc:
        logger.exception("%s: Failed during full data reset", LOG_PREFIX)
        with contextlib.suppress(Exception):
            await dialog._show_dialog_error(
                "Data Reset Error",
                f"An error occurred while resetting data: {exc}",
            )


async def open_config_directory(dialog):
    """Open the application's configuration directory using the OS explorer."""
    try:
        dialog._ensure_dialog_focus()

        raw_path = Path(dialog.config_manager.config_dir)
        try:
            path = raw_path.expanduser().resolve()
        except Exception as exc:
            logger.warning(
                "%s: Failed to resolve config directory path %s: %s",
                LOG_PREFIX,
                raw_path,
                exc,
            )
            await dialog._show_dialog_error(
                "Open Config Directory",
                "The configuration directory could not be resolved. Please verify your configuration path.",
            )
            return

        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.exception("%s: Failed to create config directory %s", LOG_PREFIX, path)
            await dialog._show_dialog_error(
                "Open Config Directory",
                f"Failed to create the configuration directory:\n{exc}",
            )
            return

        if not path.is_dir():
            logger.error(
                "%s: Configuration path exists but is not a directory: %s",
                LOG_PREFIX,
                path,
            )
            await dialog._show_dialog_error(
                "Open Config Directory",
                "The configuration directory could not be opened because the path is not a directory.",
            )
            return

        system = platform.system()
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    except Exception as exc:
        logger.exception("%s: Failed to open config directory", LOG_PREFIX)
        with contextlib.suppress(Exception):
            await dialog._show_dialog_error(
                "Open Config Directory",
                f"Failed to open the configuration directory: {exc}",
            )


async def get_visual_crossing_api_key(dialog):
    """Open the Visual Crossing registration page and show instructions."""
    try:
        webbrowser.open("https://www.visualcrossing.com/weather-query-builder/")

        await _call_dialog_method(
            dialog,
            "info_dialog",
            "Visual Crossing API Key",
            "The Visual Crossing Weather Query Builder page has been opened in your browser.\n\n"
            "To get your free API key:\n"
            "1. Sign up for a free account\n"
            "2. Go to your account page\n"
            "3. Copy your API key\n"
            "4. Paste it into the API Key field below\n\n"
            "Free accounts include 1000 weather records per day.",
        )

    except Exception:
        logger.exception("%s: Failed to open Visual Crossing registration page", LOG_PREFIX)
        await _call_dialog_method(
            dialog,
            "error_dialog",
            "Error",
            "Failed to open the Visual Crossing registration page. "
            "Please visit https://www.visualcrossing.com/weather-query-builder/ manually.",
        )


async def validate_visual_crossing_api_key(dialog):
    """Validate the Visual Crossing API key entered by the user."""
    dialog._ensure_dialog_focus()

    api_key = str(dialog.visual_crossing_api_key_input.value).strip()
    # API keys must never be logged or echoed back in errors; treat as highly sensitive.
    if not api_key:
        await dialog._show_dialog_error(
            "API Key Required", "Please enter your Visual Crossing API key before validating."
        )
        return

    original_text = getattr(dialog.validate_api_key_button, "text", "Validate API Key")

    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - dependency missing in env
        logger.error("%s: httpx is required to validate the API key: %s", LOG_PREFIX, exc)
        await dialog._show_dialog_error(
            "Validation Error",
            "❌ Validation requires the 'httpx' dependency. Please install the development requirements.",
        )
        return

    try:
        from ..visual_crossing_client import VisualCrossingClient

        def _redact_secret(text: str | None) -> str:
            if not text:
                return ""
            return str(text).replace(api_key, "***")

        if dialog.validate_api_key_button:
            dialog.validate_api_key_button.text = "Validating..."
            dialog.validate_api_key_button.enabled = False

        client = VisualCrossingClient(api_key, "AccessiWeather/2.0")
        url = f"{client.base_url}/40.7128,-74.0060"
        params = {
            "key": api_key,
            "include": "current",
            "unitGroup": "us",
            "elements": "temp",
        }

        max_attempts = 3
        backoff_schedule = [0.5, 1.0]

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = None
            for attempt in range(1, max_attempts + 1):
                try:
                    response = await http_client.get(url, params=params)
                    break
                except (httpx.TimeoutException, httpx.RequestError) as exc:
                    if attempt == max_attempts:
                        raise

                    logger.info(
                        "%s: Visual Crossing validation attempt %s failed (%s); retrying",
                        LOG_PREFIX,
                        attempt,
                        _redact_secret(str(exc)),
                    )

                    if dialog.validate_api_key_button:
                        dialog.validate_api_key_button.text = (
                            f"Retrying... ({attempt + 1}/{max_attempts})"
                        )

                    await asyncio.sleep(backoff_schedule[attempt - 1])

                    if dialog.validate_api_key_button:
                        dialog.validate_api_key_button.text = "Validating..."

        if response.status_code == 200:
            await _call_dialog_method(
                dialog,
                "info_dialog",
                "API Key Valid",
                "✅ Your Visual Crossing API key is valid and working!\n\n"
                "You can now use Visual Crossing as your weather data source.",
            )
        elif response.status_code == 401:
            await dialog._show_dialog_error(
                "Invalid API Key",
                "❌ The API key you entered is invalid.\n\n"
                "Please check your API key and try again. Make sure you copied it correctly from your Visual Crossing account.",
            )
        elif response.status_code == 429:
            await dialog._show_dialog_error(
                "Rate Limit Exceeded",
                "⚠️ Your API key is valid, but you've exceeded your rate limit.\n\n"
                "Please wait a moment before making more requests, or check your Visual Crossing account usage.",
            )
        else:
            await dialog._show_dialog_error(
                "API Error",
                f"❌ API validation failed with status code {response.status_code}.\n\n"
                "Please check your internet connection and try again.",
            )

    except httpx.TimeoutException:
        await dialog._show_dialog_error(
            "Connection Timeout",
            "⚠️ The validation request timed out.\n\n"
            "Please check your internet connection and try again.",
        )
    except httpx.RequestError as exc:
        await dialog._show_dialog_error(
            "Connection Error",
            f"❌ Failed to connect to Visual Crossing API.\n\n"
            f"Error: {_redact_secret(str(exc))}\n\n"
            "Please check your internet connection and try again.",
        )
    except Exception as exc:
        logger.error(
            "%s: Failed to validate Visual Crossing API key: %s",
            LOG_PREFIX,
            _redact_secret(str(exc)),
        )
        await dialog._show_dialog_error(
            "Validation Error",
            "❌ An unexpected error occurred while validating your API key.\n\n"
            f"Error: {_redact_secret(str(exc))}",
        )
    finally:
        if dialog.validate_api_key_button:
            dialog.validate_api_key_button.text = original_text
            dialog.validate_api_key_button.enabled = True
        dialog._ensure_dialog_focus()


async def check_for_updates(dialog):
    """Trigger an update check using the configured update service."""
    logger.info("%s: Manual update check requested", LOG_PREFIX)
    dialog._ensure_dialog_focus()

    timeout_seconds = 25.0
    max_attempts = 2
    backoff_seconds = 2.0
    final_status = "Ready to check for updates"

    try:
        if dialog.check_updates_button:
            dialog.check_updates_button.enabled = False
            dialog.check_updates_button.text = "Checking..."

        if dialog.update_status_label:
            dialog.update_status_label.text = "Checking for updates..."
        final_status = "Checking for updates..."

        if dialog.update_service:
            update_service = dialog.update_service
        else:
            from ..services import GitHubUpdateService

            update_service = GitHubUpdateService(
                app_name="AccessiWeather",
                config_dir=dialog.config_manager.config_dir if dialog.config_manager else None,
            )

        channel_value = str(dialog.update_channel_selection.value)
        channel = settings_handlers.map_channel_display_to_value(channel_value)

        if hasattr(update_service, "settings") and hasattr(update_service.settings, "channel"):
            update_service.settings.channel = channel
            if hasattr(update_service, "save_settings"):
                update_service.save_settings()

        update_info = None

        for attempt in range(1, max_attempts + 1):
            try:
                update_info = await asyncio.wait_for(
                    update_service.check_for_updates(), timeout=timeout_seconds
                )
                break
            except Exception as exc:  # noqa: BLE001 - determine retryability
                is_timeout = isinstance(exc, (asyncio.TimeoutError, OSError))
                is_httpx_error = False
                try:  # Optional dependency guard
                    import httpx  # type: ignore

                    is_httpx_error = isinstance(exc, (httpx.TimeoutException, httpx.RequestError))
                except Exception:  # pragma: no cover - httpx unavailable
                    is_httpx_error = False

                if not (is_timeout or is_httpx_error):
                    raise

                logger.warning(
                    "%s: Update check attempt %s failed: %s",
                    LOG_PREFIX,
                    attempt,
                    exc,
                )

                if attempt == max_attempts:
                    raise

                await asyncio.sleep(backoff_seconds * attempt)

        if update_info:
            final_status = f"Update available: v{update_info.version}"
            if dialog.update_status_label:
                dialog.update_status_label.text = final_status

            current_version = getattr(dialog.app, "version", None)
            if not current_version and importlib_metadata is not None:
                try:
                    current_version = importlib_metadata.version("accessiweather")
                except importlib_metadata.PackageNotFoundError:  # type: ignore[attr-defined]
                    current_version = None
                except Exception as exc:  # pragma: no cover - defensive logging path
                    logger.debug(
                        "%s: Failed to resolve current version from metadata: %s",
                        LOG_PREFIX,
                        exc,
                    )
                    current_version = None

            current_version_display = str(current_version) if current_version else "unknown"

            message = (
                f"Update Available: Version {update_info.version}\n\n"
                f"Current version: {current_version_display}\n"
                f"New version: {update_info.version}\n\n"
            )

            if update_info.release_notes:
                notes = update_info.release_notes
                message += f"Release Notes:\n{notes[:500]}"
                if len(notes) > 500:
                    message += "..."

            should_download = await _call_dialog_method(
                dialog,
                "question_dialog",
                "Update Available",
                message + "\n\nWould you like to download and install this update?",
            )

            if should_download:
                await download_update(dialog, update_service, update_info)
            else:
                final_status = "Update available (not downloaded)"
                if dialog.update_status_label:
                    dialog.update_status_label.text = final_status

        else:
            final_status = "No updates available"
            if dialog.update_status_label:
                dialog.update_status_label.text = final_status

            await _call_dialog_method(
                dialog,
                "info_dialog",
                "No Updates",
                "You are running the latest version of AccessiWeather.",
            )

        if dialog.update_status_label:
            final_status = dialog.update_status_label.text

    except Exception as exc:
        final_status = "Update check failed"
        logger.exception("%s: Failed to check for updates", LOG_PREFIX)
        await dialog._show_dialog_error(
            "Update Check Failed", f"Failed to check for updates: {exc}"
        )

    finally:
        if dialog.check_updates_button:
            dialog.check_updates_button.enabled = True
            dialog.check_updates_button.text = "Check for Updates Now"
        if dialog.update_status_label:
            dialog.update_status_label.text = final_status
        try:
            update_last_check_info(dialog)
        except Exception as exc:  # pragma: no cover - defensive call
            logger.debug("%s: Failed to refresh update metadata: %s", LOG_PREFIX, exc)
        dialog._ensure_dialog_focus()


async def download_update(dialog, update_service, update_info):
    """Download an update without automatically installing it."""
    timeout_seconds = 30.0
    max_attempts = 2
    backoff_seconds = 2.0
    final_status = f"Downloading update {update_info.version}..."
    logger.info("%s: Downloading update %s", LOG_PREFIX, getattr(update_info, "version", "unknown"))

    try:
        if dialog.update_status_label:
            dialog.update_status_label.text = final_status

        downloaded_file = None

        for attempt in range(1, max_attempts + 1):
            try:
                downloaded_file = await asyncio.wait_for(
                    update_service.download_update(update_info), timeout=timeout_seconds
                )
                break
            except Exception as exc:  # noqa: BLE001 - inspect transient failures
                is_timeout = isinstance(exc, (asyncio.TimeoutError, OSError))
                is_httpx_error = False
                try:
                    import httpx  # type: ignore

                    is_httpx_error = isinstance(exc, (httpx.TimeoutException, httpx.RequestError))
                except Exception:  # pragma: no cover - httpx unavailable
                    is_httpx_error = False

                if not (is_timeout or is_httpx_error):
                    raise

                logger.warning(
                    "%s: Update download attempt %s failed: %s",
                    LOG_PREFIX,
                    attempt,
                    exc,
                )

                if attempt == max_attempts:
                    raise

                await asyncio.sleep(backoff_seconds * attempt)

        if downloaded_file:
            final_status = f"Update {update_info.version} downloaded"
            if dialog.update_status_label:
                dialog.update_status_label.text = final_status

            await _call_dialog_method(
                dialog,
                "info_dialog",
                "Update Downloaded",
                f"Update {update_info.version} has been downloaded successfully.\n\n"
                f"Location: {downloaded_file}\n\n"
                "Please close the application and run the installer to complete the update.",
            )
        else:
            final_status = "Update download failed"
            if dialog.update_status_label:
                dialog.update_status_label.text = final_status

            await _call_dialog_method(
                dialog,
                "error_dialog",
                "Download Failed",
                "Failed to download the update. Please try again later.",
            )

    except Exception as exc:
        final_status = "Update download failed"
        logger.exception("%s: Update download failed", LOG_PREFIX)
        await _call_dialog_method(
            dialog,
            "error_dialog",
            "Download Failed",
            f"Failed to download update: {exc}",
        )
    finally:
        if dialog.update_status_label:
            dialog.update_status_label.text = final_status
        dialog._ensure_dialog_focus()


async def download_and_install_update(dialog, update_service, update_info):
    """Download and immediately install an update, showing progress to the user."""
    try:
        from .update_progress_dialog import UpdateProgressDialog

        progress_dialog = UpdateProgressDialog(dialog.app, "Downloading Update")
        progress_dialog.show_and_prepare()

        async def progress_callback(progress, downloaded, total):
            await progress_dialog.update_progress(progress, downloaded, total)
            return not progress_dialog.is_cancelled

        download_path = await update_service.download_update(update_info, progress_callback)

        if progress_dialog.is_cancelled:
            await progress_dialog.complete_error("Update cancelled by user")
            return

        if not download_path:
            await progress_dialog.complete_error("Failed to download update")
            return

        await progress_dialog.set_status("Installing update...", "Please wait...")

        success = await update_service.apply_update(download_path)

        if success:
            await progress_dialog.complete_success("Update installed successfully")

            restart_choice = await _call_dialog_method(
                dialog,
                "question_dialog",
                "Restart Required",
                "The update has been installed successfully. "
                "AccessiWeather needs to restart to complete the update. "
                "Restart now?",
            )

            if restart_choice:
                if dialog.future and not dialog.future.done():
                    dialog.future.set_result(True)
                if dialog.window:
                    dialog.window.close()
                    dialog.window = None
                await _call_dialog_method(
                    dialog,
                    "info_dialog",
                    "Restart",
                    "Please restart AccessiWeather manually to complete the update.",
                )
        else:
            await progress_dialog.complete_error("Failed to install update")

        await progress_dialog
        progress_dialog.close()

    except Exception as exc:
        logger.exception("%s: Failed to perform update", LOG_PREFIX)
        await _call_dialog_method(
            dialog,
            "error_dialog",
            "Update Failed",
            f"Failed to perform update: {exc}",
        )


def initialize_update_info(dialog):
    """Initialize update-related labels when the dialog is created."""
    try:
        update_last_check_info(dialog)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("%s: Failed to initialize update info: %s", LOG_PREFIX, exc)


def update_last_check_info(dialog):
    """Refresh the last-update label with any available data."""
    label = getattr(dialog, "last_check_label", None)
    if not label:
        return

    placeholder = "Last check: Not implemented yet"
    last_check_ts: float | None = None
    last_status: str | None = None
    max_json_bytes = 1_000_000  # 1MB safety limit

    try:
        service = getattr(dialog, "update_service", None)
        cache_data = None

        def _safe_load_json(path: Path) -> dict | None:
            try:
                if path.stat().st_size > max_json_bytes:
                    logger.warning(
                        "%s: Skipping update metadata at %s because the file exceeds %s bytes",
                        LOG_PREFIX,
                        path,
                        max_json_bytes,
                    )
                    return None
            except OSError as exc:  # pragma: no cover - filesystem edge cases
                logger.debug(
                    "%s: Could not stat update metadata file %s: %s", LOG_PREFIX, path, exc
                )
                return None

            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    "%s: Malformed JSON in update metadata %s: %s", LOG_PREFIX, path, exc
                )
                return None
            except OSError as exc:
                logger.warning("%s: Failed to read update metadata %s: %s", LOG_PREFIX, path, exc)
                return None

            if not isinstance(data, dict):
                logger.warning(
                    "%s: Unexpected data type for update metadata %s: %s",
                    LOG_PREFIX,
                    path,
                    type(data).__name__,
                )
                return None
            return data

        # Prefer in-memory cache when available
        if service is not None and getattr(service, "_cache", None):
            cache_data = service._cache

        # Otherwise, attempt to load persisted cache from disk
        if cache_data is None:
            cache_path = None
            if service is not None and getattr(service, "cache_path", None):
                cache_path = Path(service.cache_path)
            elif getattr(dialog, "config_manager", None):
                cache_path = Path(dialog.config_manager.config_dir) / "github_releases_cache.json"

            if cache_path and cache_path.exists():
                cache_data = _safe_load_json(cache_path)

        if isinstance(cache_data, dict):
            candidate_ts = cache_data.get("last_check") or cache_data.get("lastCheck")
            if isinstance(candidate_ts, (int, float, str)):
                last_check_ts = candidate_ts
            elif candidate_ts is not None:
                logger.debug(
                    "%s: Ignoring unexpected last check value type: %s",
                    LOG_PREFIX,
                    type(candidate_ts),
                )

            candidate_status = cache_data.get("last_status") or cache_data.get("status")
            if isinstance(candidate_status, str):
                last_status = candidate_status
            elif candidate_status is not None:
                logger.debug(
                    "%s: Ignoring unexpected last status type: %s",
                    LOG_PREFIX,
                    type(candidate_status),
                )

        # Look for metadata persisted in settings (if any)
        settings_data = None
        if service is not None and getattr(service, "settings", None):
            settings_data = getattr(service.settings, "__dict__", {})
        else:
            settings_path = None
            if service is not None and getattr(service, "settings_path", None):
                settings_path = Path(service.settings_path)
            elif getattr(dialog, "config_manager", None):
                settings_path = Path(dialog.config_manager.config_dir) / "update_settings.json"

            if settings_path and settings_path.exists():
                settings_data = _safe_load_json(settings_path)

        if isinstance(settings_data, dict):
            last_check_ts = (
                last_check_ts
                or settings_data.get("last_check_timestamp")
                or settings_data.get("last_check")
            )
            last_status = (
                last_status
                or settings_data.get("last_check_status")
                or settings_data.get("last_status")
            )

            if last_check_ts is not None and not isinstance(last_check_ts, (int, float, str)):
                logger.debug(
                    "%s: Ignoring unexpected last_check_ts type from settings: %s",
                    LOG_PREFIX,
                    type(last_check_ts),
                )
                last_check_ts = None

            if last_status is not None and not isinstance(last_status, str):
                logger.debug(
                    "%s: Ignoring unexpected last_status type from settings: %s",
                    LOG_PREFIX,
                    type(last_status),
                )
                last_status = None

        display_text = placeholder

        if last_check_ts:
            try:
                ts_float = float(last_check_ts)
                dt_value = datetime.fromtimestamp(ts_float)
                formatted = dt_value.strftime("%b %d, %Y %H:%M").replace(" 0", " ")
                display_text = f"Last check: {formatted}"
                if last_status:
                    display_text += f" ({last_status})"
            except Exception as exc:  # pragma: no cover - formatting guard
                logger.warning("%s: Failed to format last check timestamp: %s", LOG_PREFIX, exc)
                if last_status:
                    display_text = f"Last check status: {last_status}"
        elif last_status:
            display_text = f"Last check status: {last_status}"

        label.text = display_text

    except Exception:  # pragma: no cover
        logger.exception("%s: Failed to update last check info", LOG_PREFIX)
        label.text = placeholder
