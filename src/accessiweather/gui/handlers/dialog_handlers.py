"""Dialog handlers for the WeatherApp class

This module contains the dialog-related handlers for the WeatherApp class.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import wx

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppDialogHandlers(WeatherAppHandlerBase):
    """Dialog handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides dialog-related event handlers for the WeatherApp class.
    """

    def ShowMessageDialog(
        self,
        message: str,
        title: str = "AccessiWeather",
        style: int = wx.OK | wx.ICON_INFORMATION,
    ) -> int:
        """Show a message dialog

        Args:
            message: Message to display
            title: Dialog title
            style: Dialog style

        Returns:
            Dialog result (e.g., wx.ID_OK, wx.ID_CANCEL)
        """
        logger.debug(f"Showing message dialog: {title} - {message}")
        result: int = wx.MessageBox(message, title, style, self)
        return result

    def ShowConfirmDialog(
        self, message: str, title: str = "Confirm", style: int = wx.YES_NO | wx.ICON_QUESTION
    ) -> bool:
        """Show a confirmation dialog

        Args:
            message: Message to display
            title: Dialog title
            style: Dialog style

        Returns:
            True if confirmed (Yes/OK), False otherwise
        """
        logger.debug(f"Showing confirmation dialog: {title} - {message}")
        result = wx.MessageBox(message, title, style, self)
        logger.debug(
            f"Confirmation dialog result: {result} (wx.ID_YES={wx.ID_YES}, wx.ID_OK={wx.ID_OK})"
        )
        is_confirmed = result in (wx.ID_YES, wx.ID_OK)
        logger.debug(f"Confirmation dialog interpreted result: {is_confirmed}")
        return is_confirmed

    def ShowProgressDialog(
        self,
        title: str,
        message: str,
        maximum: int = 100,
        parent: Optional[wx.Window] = None,
        style: int = wx.PD_APP_MODAL | wx.PD_AUTO_HIDE,
    ) -> wx.ProgressDialog:
        """Show a progress dialog

        Args:
            title: Dialog title
            message: Dialog message
            maximum: Maximum value for the progress bar
            parent: Parent window (defaults to self)
            style: Dialog style

        Returns:
            Progress dialog instance
        """
        logger.debug(f"Creating progress dialog: {title} - {message}")
        if parent is None:
            parent = self
        return wx.ProgressDialog(title, message, maximum, parent, style)

    def ShowSingleChoiceDialog(
        self,
        message: str,
        title: str,
        choices: List[str],
        parent: Optional[wx.Window] = None,
    ) -> Tuple[int, Optional[int]]:
        """Show a single choice dialog

        Args:
            message: Dialog message
            title: Dialog title
            choices: List of choices
            parent: Parent window (defaults to self)

        Returns:
            Tuple of (dialog result, selected index or None)
        """
        logger.debug(f"Showing single choice dialog: {title} - {message}")
        if parent is None:
            parent = self
        dialog = wx.SingleChoiceDialog(parent, message, title, choices)
        result = dialog.ShowModal()
        selection = dialog.GetSelection() if result == wx.ID_OK else None
        dialog.Destroy()
        return result, selection

    def ShowTextEntryDialog(
        self,
        message: str,
        title: str = "Input",
        default_value: str = "",
        style: int = wx.OK | wx.CANCEL | wx.CENTRE,
    ) -> Tuple[int, str]:
        """Show a text entry dialog

        Args:
            message: Dialog message
            title: Dialog title
            default_value: Default text value
            style: Dialog style

        Returns:
            Tuple of (dialog result, entered text)
        """
        logger.debug(f"Showing text entry dialog: {title} - {message}")
        dialog = wx.TextEntryDialog(self, message, title, default_value, style)
        result = dialog.ShowModal()
        value = dialog.GetValue() if result == wx.ID_OK else ""
        dialog.Destroy()
        return result, value

    def ShowLocationDialog(self) -> Tuple[int, Optional[Tuple[str, float, float]]]:
        """Show the location dialog

        Returns:
            Tuple of (dialog result, location data or None)
            Location data is a tuple of (name, latitude, longitude)
        """
        from ..dialogs import LocationDialog

        logger.debug("Showing location dialog")
        dialog = LocationDialog(self)
        result = dialog.ShowModal()

        location_data = None
        if result == wx.ID_OK:
            name, lat, lon = dialog.GetValues()
            if name and lat is not None and lon is not None:
                location_data = (name, lat, lon)

        dialog.Destroy()
        return result, location_data

    def ShowSettingsDialog(
        self, current_settings: Dict[str, Any]
    ) -> Tuple[int, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Show the settings dialog

        Args:
            current_settings: Current settings dictionary

        Returns:
            Tuple of (dialog result, updated settings or None, updated API settings or None)
        """
        from ..settings_dialog import SettingsDialog

        logger.debug("Showing settings dialog")
        dialog = SettingsDialog(self, current_settings)
        result = dialog.ShowModal()

        updated_settings = None
        updated_api_settings = None
        if result == wx.ID_OK:
            updated_settings = dialog.get_settings()
            updated_api_settings = dialog.get_api_settings()

        dialog.Destroy()
        return result, updated_settings, updated_api_settings

    def ShowAlertDetailsDialog(self, alert: Dict[str, Any]) -> None:
        """Show the alert details dialog

        Args:
            alert: Alert data dictionary
        """
        from ..alert_dialog import AlertDetailsDialog

        # Get alert event for title
        event = alert.get("event", "Unknown Alert")
        logger.debug(f"Showing alert details dialog for {event}")

        # Create dialog with title and alert data
        dialog = AlertDetailsDialog(self, event, alert)
        dialog.ShowModal()
        dialog.Destroy()

    def ShowWeatherDiscussionDialog(self, title: str, text: str) -> None:
        """Show the weather discussion dialog

        Args:
            title: Dialog title
            text: Discussion text
        """
        from ..dialogs import WeatherDiscussionDialog

        logger.debug(f"Showing weather discussion dialog: {title}")
        dialog = WeatherDiscussionDialog(self, title, text)
        dialog.ShowModal()
        dialog.Destroy()

    def ShowNationalDiscussionDialog(self, national_data: Dict[str, Any]) -> None:
        """Show the national discussion dialog

        Args:
            national_data: National discussion data
        """
        from ..dialogs import NationalDiscussionDialog

        logger.debug("Showing national discussion dialog")
        dialog = NationalDiscussionDialog(self, national_data)
        dialog.ShowModal()
        dialog.Destroy()
