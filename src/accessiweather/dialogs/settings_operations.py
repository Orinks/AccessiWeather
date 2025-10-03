"""Async operations and helpers for the settings dialog."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import platform
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

from . import settings_handlers

logger = logging.getLogger(__name__)


async def reset_to_defaults(dialog):
    """Reset configuration to defaults and refresh the dialog UI."""
    try:
        dialog._ensure_dialog_focus()

        logger.info("User requested reset of configuration to defaults")
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

        try:
            if dialog.window and hasattr(dialog.window, "info_dialog"):
                await dialog.window.info_dialog(
                    "Settings Reset", "All settings were reset to defaults."
                )
            else:
                await dialog.app.main_window.info_dialog(
                    "Settings Reset", "All settings were reset to defaults."
                )
                dialog._ensure_dialog_focus()
        except Exception:
            await dialog.app.main_window.info_dialog(
                "Settings Reset", "All settings were reset to defaults."
            )
            dialog._ensure_dialog_focus()

    except Exception as exc:
        logger.error("Failed during reset-to-defaults operation: %s", exc)
        with contextlib.suppress(Exception):
            await dialog._show_dialog_error(
                "Settings Error",
                f"An error occurred while resetting to defaults: {exc}",
            )


async def full_data_reset(dialog):
    """Perform a full data reset and refresh the dialog."""
    try:
        dialog._ensure_dialog_focus()

        logger.info("User requested full data reset")
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

        try:
            if dialog.window and hasattr(dialog.window, "info_dialog"):
                await dialog.window.info_dialog("Data Reset", "All application data were reset.")
            else:
                await dialog.app.main_window.info_dialog(
                    "Data Reset", "All application data were reset."
                )
                dialog._ensure_dialog_focus()
        except Exception:
            await dialog.app.main_window.info_dialog(
                "Data Reset", "All application data were reset."
            )
            dialog._ensure_dialog_focus()

    except Exception as exc:
        logger.error("Failed during full data reset: %s", exc)
        with contextlib.suppress(Exception):
            await dialog._show_dialog_error(
                "Data Reset Error",
                f"An error occurred while resetting data: {exc}",
            )


async def open_config_directory(dialog):
    """Open the application's configuration directory using the OS explorer."""
    try:
        dialog._ensure_dialog_focus()
        path = Path(dialog.config_manager.config_dir)
        with contextlib.suppress(Exception):
            path.mkdir(parents=True, exist_ok=True)

        system = platform.system()
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    except Exception as exc:
        logger.error("Failed to open config directory: %s", exc)
        with contextlib.suppress(Exception):
            await dialog._show_dialog_error(
                "Open Config Directory",
                f"Failed to open the configuration directory: {exc}",
            )


async def get_visual_crossing_api_key(dialog):
    """Open the Visual Crossing registration page and show instructions."""
    try:
        webbrowser.open("https://www.visualcrossing.com/weather-query-builder/")

        await dialog.app.main_window.info_dialog(
            "Visual Crossing API Key",
            "The Visual Crossing Weather Query Builder page has been opened in your browser.\n\n"
            "To get your free API key:\n"
            "1. Sign up for a free account\n"
            "2. Go to your account page\n"
            "3. Copy your API key\n"
            "4. Paste it into the API Key field below\n\n"
            "Free accounts include 1000 weather records per day.",
        )

    except Exception as exc:
        logger.error("Failed to open Visual Crossing registration page: %s", exc)
        await dialog.app.main_window.error_dialog(
            "Error",
            "Failed to open the Visual Crossing registration page. "
            "Please visit https://www.visualcrossing.com/weather-query-builder/ manually.",
        )


async def validate_visual_crossing_api_key(dialog):
    """Validate the Visual Crossing API key entered by the user."""
    dialog._ensure_dialog_focus()

    api_key = str(dialog.visual_crossing_api_key_input.value).strip()
    if not api_key:
        await dialog._show_dialog_error(
            "API Key Required", "Please enter your Visual Crossing API key before validating."
        )
        return

    original_text = getattr(dialog.validate_api_key_button, "text", "Validate API Key")

    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - dependency missing in env
        logger.error("httpx is required to validate the API key: %s", exc)
        await dialog._show_dialog_error(
            "Validation Error",
            "❌ Validation requires the 'httpx' dependency. Please install the development requirements.",
        )
        return

    try:
        from ..visual_crossing_client import VisualCrossingClient

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

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get(url, params=params)

        if response.status_code == 200:
            await dialog.app.main_window.info_dialog(
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
            f"Error: {exc}\n\n"
            "Please check your internet connection and try again.",
        )
    except Exception as exc:
        logger.error("Failed to validate Visual Crossing API key: %s", exc)
        await dialog._show_dialog_error(
            "Validation Error",
            f"❌ An unexpected error occurred while validating your API key.\n\nError: {exc}",
        )
    finally:
        if dialog.validate_api_key_button:
            dialog.validate_api_key_button.text = original_text
            dialog.validate_api_key_button.enabled = True
        dialog._ensure_dialog_focus()


async def check_for_updates(dialog):
    """Trigger an update check using the configured update service."""
    logger.info("Manual update check requested")
    dialog._ensure_dialog_focus()

    try:
        if dialog.check_updates_button:
            dialog.check_updates_button.enabled = False
            dialog.check_updates_button.text = "Checking..."

        if dialog.update_status_label:
            dialog.update_status_label.text = "Checking for updates..."

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

        update_info = await update_service.check_for_updates()

        if update_info:
            if dialog.update_status_label:
                dialog.update_status_label.text = f"Update available: v{update_info.version}"

            message = (
                f"Update Available: Version {update_info.version}\n\n"
                f"Current version: 2.0\n"
                f"New version: {update_info.version}\n\n"
            )

            if update_info.release_notes:
                notes = update_info.release_notes
                message += f"Release Notes:\n{notes[:500]}"
                if len(notes) > 500:
                    message += "..."

            should_download = await dialog.app.main_window.question_dialog(
                "Update Available",
                message + "\n\nWould you like to download and install this update?",
            )

            if should_download:
                await download_update(dialog, update_service, update_info)
            else:
                if dialog.update_status_label:
                    dialog.update_status_label.text = "Update available (not downloaded)"

        else:
            if dialog.update_status_label:
                dialog.update_status_label.text = "No updates available"

            try:
                if dialog.window and hasattr(dialog.window, "info_dialog"):
                    await dialog.window.info_dialog(
                        "No Updates", "You are running the latest version of AccessiWeather."
                    )
                else:
                    await dialog.app.main_window.info_dialog(
                        "No Updates", "You are running the latest version of AccessiWeather."
                    )
                    dialog._ensure_dialog_focus()
            except Exception:
                await dialog.app.main_window.info_dialog(
                    "No Updates", "You are running the latest version of AccessiWeather."
                )
                dialog._ensure_dialog_focus()

        update_last_check_info(dialog)

    except Exception as exc:
        logger.error("Failed to check for updates: %s", exc)
        if dialog.update_status_label:
            dialog.update_status_label.text = "Update check failed"

        await dialog._show_dialog_error(
            "Update Check Failed", f"Failed to check for updates: {exc}"
        )

    finally:
        if dialog.check_updates_button:
            dialog.check_updates_button.enabled = True
            dialog.check_updates_button.text = "Check for Updates Now"
        dialog._ensure_dialog_focus()


async def download_update(dialog, update_service, update_info):
    """Download an update without automatically installing it."""
    try:
        if dialog.update_status_label:
            dialog.update_status_label.text = f"Downloading update {update_info.version}..."

        downloaded_file = await update_service.download_update(update_info)

        if downloaded_file:
            if dialog.update_status_label:
                dialog.update_status_label.text = f"Update {update_info.version} downloaded"

            await dialog.app.main_window.info_dialog(
                "Update Downloaded",
                f"Update {update_info.version} has been downloaded successfully.\n\n"
                f"Location: {downloaded_file}\n\n"
                "Please close the application and run the installer to complete the update.",
            )
        else:
            if dialog.update_status_label:
                dialog.update_status_label.text = "Update download failed"

            await dialog.app.main_window.error_dialog(
                "Download Failed", "Failed to download the update. Please try again later."
            )

    except Exception as exc:
        logger.error("Update download failed: %s", exc)
        if dialog.update_status_label:
            dialog.update_status_label.text = "Update download failed"

        await dialog.app.main_window.error_dialog(
            "Download Failed", f"Failed to download update: {exc}"
        )


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

            restart_choice = await dialog.app.main_window.question_dialog(
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
                await dialog.app.main_window.info_dialog(
                    "Restart", "Please restart AccessiWeather manually to complete the update."
                )
        else:
            await progress_dialog.complete_error("Failed to install update")

        await progress_dialog
        progress_dialog.close()

    except Exception as exc:
        logger.error("Failed to perform update: %s", exc)
        await dialog.app.main_window.error_dialog(
            "Update Failed", f"Failed to perform update: {exc}"
        )


def initialize_update_info(dialog):
    """Initialize update-related labels when the dialog is created."""
    try:
        update_last_check_info(dialog)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to initialize update info: %s", exc)


def update_last_check_info(dialog):
    """Refresh the last-update label with any available data."""
    label = getattr(dialog, "last_check_label", None)
    if not label:
        return

    placeholder = "Last check: Not implemented yet"
    last_check_ts: float | None = None
    last_status: str | None = None

    try:
        service = getattr(dialog, "update_service", None)
        cache_data = None

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
                try:
                    with open(cache_path, encoding="utf-8") as fh:
                        cache_data = json.load(fh)
                except Exception as exc:  # pragma: no cover - best-effort load
                    logger.warning("Failed to load update cache: %s", exc)

        if isinstance(cache_data, dict):
            last_check_ts = cache_data.get("last_check") or cache_data.get("lastCheck")
            last_status = cache_data.get("last_status") or cache_data.get("status")

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
                try:
                    with open(settings_path, encoding="utf-8") as fh:
                        settings_data = json.load(fh)
                except Exception as exc:  # pragma: no cover - best-effort load
                    logger.warning("Failed to load update settings metadata: %s", exc)

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
                logger.warning("Failed to format last check timestamp: %s", exc)
                if last_status:
                    display_text = f"Last check status: {last_status}"
        elif last_status:
            display_text = f"Last check status: {last_status}"

        label.text = display_text

    except Exception as exc:  # pragma: no cover
        logger.error("Failed to update last check info: %s", exc)
        label.text = placeholder
