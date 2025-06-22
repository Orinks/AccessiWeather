"""Common base class for all WeatherApp handlers

This module contains the common base class for all WeatherApp handlers.
"""

import logging
from typing import Any

import wx
import wx.adv

logger = logging.getLogger(__name__)


class WeatherAppHandlerBase:
    """Common base class for all WeatherApp handlers

    This class provides type annotations for attributes that will be provided by WeatherApp.
    It is meant to be inherited by all handler classes, not used directly.
    """

    # Type annotations for attributes that will be provided by WeatherApp
    timer: wx.Timer
    # alerts_timer has been removed in favor of unified update mechanism
    location_choice: wx.Choice
    location_service: Any
    forecast_text: wx.TextCtrl
    alerts_list: wx.ListCtrl
    current_alerts: list[dict[str, Any]]
    updating: bool
    last_update: float
    config: dict[str, Any]
    _config_path: str
    api_client: Any
    weather_service: Any
    notification_service: Any
    discussion_fetcher: Any
    _on_discussion_fetched: Any
    _on_discussion_error: Any
    taskbar_icon: wx.adv.TaskBarIcon | None
    _in_nationwide_mode: bool
    _nationwide_wpc_full: str | None
    _nationwide_spc_full: str | None
    remove_btn: wx.Button
    alert_btn: wx.Button
    discussion_btn: wx.Button
    _discussion_loading_dialog: wx.ProgressDialog | None
    _discussion_timer: wx.Timer | None
    debug_mode: bool
    debug_alerts: bool

    # Methods that will be provided by WeatherApp
    def UpdateWeatherData(self) -> None:
        """Placeholder for WeatherApp.UpdateWeatherData method"""

    def UpdateLocationDropdown(self) -> None:
        """Placeholder for WeatherApp.UpdateLocationDropdown method"""

    def SetStatusText(self, text: str) -> None:  # noqa: U100
        """Placeholder for wx.Frame.SetStatusText method"""

    def Bind(self, *args: Any, **kwargs: Any) -> None:  # noqa: U100
        """Placeholder for wx.Frame.Bind method"""

    def Unbind(self, *args: Any, **kwargs: Any) -> None:  # noqa: U100
        """Placeholder for wx.Frame.Unbind method"""

    def Hide(self) -> None:
        """Placeholder for wx.Frame.Hide method"""

    def _save_config(self, show_errors: bool = True) -> bool:  # noqa: U100
        """Placeholder for WeatherApp._save_config method"""
        return True
