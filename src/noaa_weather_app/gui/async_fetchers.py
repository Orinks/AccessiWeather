"""Asynchronous data fetching components for NOAA Weather App

This module provides thread-based asynchronous fetching of weather data.
"""

import threading
import wx
import logging

logger = logging.getLogger(__name__)


class ForecastFetcher:
    """Handles asynchronous fetching of forecast data"""
    
    def __init__(self, api_client):
        """Initialize forecast fetcher
        
        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        
    def fetch(self, lat, lon, on_success=None, on_error=None):
        """Fetch forecast data asynchronously
        
        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
        """
        # Only start if not already running
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Forecast fetch already in progress")
            return
            
        self.thread = threading.Thread(
            target=self._fetch_thread,
            args=(lat, lon, on_success, on_error)
        )
        self.thread.daemon = True
        self.thread.start()
    
    def _fetch_thread(self, lat, lon, on_success, on_error):
        """Thread function to fetch the forecast
        
        Args:
            lat: Latitude
            lon: Longitude
            on_success: Success callback
            on_error: Error callback
        """
        try:
            forecast_data = self.api_client.get_forecast(lat, lon)
            if on_success:
                # Call callback on main thread
                wx.CallAfter(on_success, forecast_data)
        except Exception as e:
            logger.error(f"Failed to retrieve forecast: {str(e)}")
            if on_error:
                # Call callback on main thread
                wx.CallAfter(on_error, f"Unable to retrieve forecast data: {str(e)}")


class AlertsFetcher:
    """Handles asynchronous fetching of alerts data"""
    
    def __init__(self, api_client):
        """Initialize alerts fetcher
        
        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        
    def fetch(self, lat, lon, on_success=None, on_error=None):
        """Fetch alerts data asynchronously
        
        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
        """
        # Only start if not already running
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Alerts fetch already in progress")
            return
            
        self.thread = threading.Thread(
            target=self._fetch_thread,
            args=(lat, lon, on_success, on_error)
        )
        self.thread.daemon = True
        self.thread.start()
    
    def _fetch_thread(self, lat, lon, on_success, on_error):
        """Thread function to fetch the alerts
        
        Args:
            lat: Latitude
            lon: Longitude
            on_success: Success callback
            on_error: Error callback
        """
        try:
            alerts_data = self.api_client.get_alerts(lat, lon)
            if on_success:
                # Call callback on main thread
                wx.CallAfter(on_success, alerts_data)
        except Exception as e:
            logger.error(f"Failed to retrieve alerts: {str(e)}")
            if on_error:
                # Call callback on main thread
                wx.CallAfter(on_error, f"Unable to retrieve alerts data: {str(e)}")


class DiscussionFetcher:
    """Handles asynchronous fetching of weather discussion data"""
    
    def __init__(self, api_client):
        """Initialize discussion fetcher
        
        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        
    def fetch(self, lat, lon, on_success=None, on_error=None, additional_data=None):
        """Fetch discussion data asynchronously
        
        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
            additional_data: Additional data to pass to callbacks
        """
        # Only start if not already running
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Discussion fetch already in progress")
            return
            
        self.thread = threading.Thread(
            target=self._fetch_thread,
            args=(lat, lon, on_success, on_error, additional_data)
        )
        self.thread.daemon = True
        self.thread.start()
    
    def _fetch_thread(self, lat, lon, on_success, on_error, additional_data):
        """Thread function to fetch the discussion
        
        Args:
            lat: Latitude
            lon: Longitude
            on_success: Success callback
            on_error: Error callback
            additional_data: Additional data to pass to callbacks
        """
        try:
            discussion_text = self.api_client.get_forecast_discussion(lat, lon)
            if on_success:
                if additional_data:
                    # Call callback on main thread with additional data
                    wx.CallAfter(on_success, discussion_text, *additional_data)
                else:
                    # Call callback on main thread
                    wx.CallAfter(on_success, discussion_text)
        except Exception as e:
            logger.error(f"Failed to retrieve discussion: {str(e)}")
            if on_error:
                if additional_data:
                    # Call callback on main thread with additional data
                    wx.CallAfter(on_error, f"Unable to retrieve discussion: {str(e)}", *additional_data)
                else:
                    # Call callback on main thread
                    wx.CallAfter(on_error, f"Unable to retrieve discussion: {str(e)}")
