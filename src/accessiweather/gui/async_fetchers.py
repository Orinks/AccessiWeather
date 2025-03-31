"""Asynchronous data fetching components for AccessiWeather

This module provides thread-based asynchronous fetching of weather data.
"""

import threading
import wx
import logging

logger = logging.getLogger(__name__)


# Helper function to safely use CallAfter
def safe_call_after(callback, *args, **kwargs):
    """Safely use wx.CallAfter to schedule callback on the main thread.
    
    Args:
        callback: Function to call on the main thread
        *args: Arguments to pass to the callback
        **kwargs: Keyword arguments to pass to the callback
    """
    try:
        # Always use wx.CallAfter to ensure main thread execution
        wx.CallAfter(callback, *args, **kwargs)
        logger.debug("Scheduled callback using wx.CallAfter")
    except (AssertionError, RuntimeError) as e:
        # This might happen if wx.App isn't fully initialized or is destroyed
        # Log the error. Depending on context, raising might be better.
        logger.error(f"Could not schedule callback via wx.CallAfter: {e}")
        # Consider re-raising or handling differently if needed


class ForecastFetcher:
    """Handles asynchronous fetching of forecast data"""
    
    def __init__(self, api_client):
        """Initialize forecast fetcher
        
        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        self._stop_event = threading.Event()
        
    def fetch(self, lat, lon, on_success=None, on_error=None):
        """Fetch forecast data asynchronously
        
        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
        """
        # Cancel any existing fetch
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Cancelling in-progress forecast fetch")
            self._stop_event.set()
            # Join with a short timeout to avoid blocking UI indefinitely
            self.thread.join(0.5)
        
        # Reset stop event for new fetch
        self._stop_event.clear()
            
        # Create and start new thread
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
            # Check if we've been asked to stop
            if self._stop_event.is_set():
                logger.debug("Forecast fetch cancelled before API call")
                return
            
            # Get forecast data from API
            forecast_data = self.api_client.get_forecast(lat, lon)
            
            # Check again if we've been asked to stop before delivering results
            if self._stop_event.is_set():
                logger.debug("Forecast fetch completed but cancelled")
                return
            
            # Call success callback if provided
            if on_success and not self._stop_event.is_set():
                # Call callback on main thread
                safe_call_after(on_success, forecast_data)
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Failed to retrieve forecast: {str(e)}")
                if on_error:
                    # Call error callback on main thread
                    error_msg = f"Unable to retrieve forecast data: {str(e)}"
                    safe_call_after(on_error, error_msg)


class AlertsFetcher:
    """Handles asynchronous fetching of alerts data"""
    
    def __init__(self, api_client):
        """Initialize alerts fetcher
        
        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        self._stop_event = threading.Event()
        
    def fetch(self, lat, lon, on_success=None, on_error=None):
        """Fetch alerts data asynchronously
        
        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
        """
        # Cancel any existing fetch
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Cancelling in-progress alerts fetch")
            self._stop_event.set()
            # Join with a short timeout to avoid blocking UI indefinitely
            self.thread.join(0.5)
        
        # Reset stop event for new fetch
        self._stop_event.clear()
            
        # Create and start new thread
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
            # Check if we've been asked to stop
            if self._stop_event.is_set():
                logger.debug("Alerts fetch cancelled before API call")
                return
                
            # Get alerts data from API
            alerts_data = self.api_client.get_alerts(lat, lon)
            
            # Check again if we've been asked to stop before delivering results
            if self._stop_event.is_set():
                logger.debug("Alerts fetch completed but cancelled")
                return
                
            # Call success callback if provided
            if on_success and not self._stop_event.is_set():
                # Call callback on main thread
                safe_call_after(on_success, alerts_data)
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Failed to retrieve alerts: {str(e)}")
                if on_error:
                    # Call error callback on main thread
                    error_msg = f"Unable to retrieve alerts data: {str(e)}"
                    safe_call_after(on_error, error_msg)


class DiscussionFetcher:
    """Handles asynchronous fetching of weather discussion data"""
    
    def __init__(self, api_client):
        """Initialize discussion fetcher
        
        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        self._stop_event = threading.Event()
        
    def fetch(self, lat, lon, on_success=None, on_error=None,
              additional_data=None):
        """Fetch discussion data asynchronously
        
        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
            additional_data: Additional data to pass to callbacks
        """
        # Cancel any existing fetch
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Cancelling in-progress discussion fetch")
            self._stop_event.set()
            # Join with a short timeout to avoid blocking UI indefinitely
            self.thread.join(0.5)
        
        # Reset stop event for new fetch
        self._stop_event.clear()
            
        # Create and start new thread
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
            # Check if we've been asked to stop
            if self._stop_event.is_set():
                logger.debug("Discussion fetch cancelled before API call")
                return
                
            # Get discussion text from API
            discussion_text = self.api_client.get_discussion(lat, lon)
            
            # Check again if we've been asked to stop before delivering results
            if self._stop_event.is_set():
                logger.debug("Discussion fetch completed but cancelled")
                return
                
            # Call success callback if provided
            if on_success and not self._stop_event.is_set():
                # Call callback on main thread
                if additional_data is not None:
                    safe_call_after(
                        on_success, discussion_text, *additional_data
                    )
                else:
                    safe_call_after(on_success, discussion_text)
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Failed to retrieve discussion: {str(e)}")
                if on_error:
                    # Call error callback on main thread
                    error_msg = (
                        f"Unable to retrieve forecast discussion: {str(e)}"
                    )
                    if additional_data is not None:
                        safe_call_after(on_error, error_msg, *additional_data)
                    else:
                        safe_call_after(on_error, error_msg)
