# Nationwide Forecast Integration

This document outlines the implementation plan for integrating national forecast data from NOAA/NWS centers into the AccessiWeather application.

## Overview

The Nationwide view will display national forecast data and discussions from various NOAA/NWS centers including:
- Weather Prediction Center (WPC)
- Storm Prediction Center (SPC)
- National Hurricane Center (NHC)
- Climate Prediction Center (CPC)

## Accessibility Considerations

Many national forecast products are presented as charts or graphical elements on the NWS website, which poses challenges for screen reader accessibility. To make the Nationwide view accessible, we will:

1. **Focus on Text Products**: We'll use text-based forecast discussions rather than trying to describe graphical products. These text products contain the same information as the charts but in a format that is inherently accessible to screen readers.

2. **Structured Presentation**: We'll organize the text in a structured way with clear headings and sections to make it easier for screen readers to navigate.

3. **Descriptive Summaries**: For each national center's products, we'll extract or create concise summaries that highlight the most important information.

4. **Semantic HTML**: When displaying the information in the UI, we'll use proper semantic HTML elements with appropriate ARIA attributes to enhance screen reader navigation.

5. **Keyboard Navigation**: We'll ensure that all elements in the Nationwide view are keyboard navigable for users who can't use a mouse.

The forecast discussions from national centers are particularly valuable for screen reader users because they provide detailed explanations in plain text format, including:
- Meteorological reasoning behind the forecast
- Expected timing and intensity of weather events
- Confidence levels and alternative scenarios
- Geographic descriptions of affected areas

## API Endpoints

The following API endpoints will be used to fetch national forecast data:

### Weather Prediction Center (WPC)
- Short Range Forecast Discussion (FXUS01 KWNH): `https://api.weather.gov/products/types/FXUS01/locations/KWNH`
- Medium Range Forecast Discussion (FXUS06 KWNH): `https://api.weather.gov/products/types/FXUS06/locations/KWNH`
- Extended Forecast Discussion (FXUS07 KWNH): `https://api.weather.gov/products/types/FXUS07/locations/KWNH`
- Quantitative Precipitation Forecast (QPF) Discussion (FXUS02 KWNH): `https://api.weather.gov/products/types/FXUS02/locations/KWNH`

### Storm Prediction Center (SPC)
- Day 1 Convective Outlook Discussion (ACUS01 KWNS): `https://api.weather.gov/products/types/ACUS01/locations/KWNS`
- Day 2 Convective Outlook Discussion (ACUS02 KWNS): `https://api.weather.gov/products/types/ACUS02/locations/KWNS`
- Day 3 Convective Outlook Discussion (ACUS03 KWNS): `https://api.weather.gov/products/types/ACUS03/locations/KWNS`

### National Hurricane Center (NHC)
- Tropical Weather Outlook (TWO): `https://api.weather.gov/products/types/MIATWOAT/locations/KNHC` (Atlantic)
- Tropical Weather Outlook (TWO): `https://api.weather.gov/products/types/MIATWOEP/locations/KNHC` (East Pacific)

### Climate Prediction Center (CPC)
- 6-10 Day Outlook Discussion (FXUS05 KWNC): `https://api.weather.gov/products/types/FXUS05/locations/KWNC`
- 8-14 Day Outlook Discussion (FXUS07 KWNC): `https://api.weather.gov/products/types/FXUS07/locations/KWNC`

## Implementation Plan

### 1. API Client Updates

Add methods to the `NoaaApiClient` class to fetch national forecast data:

```python
def get_national_product(self, product_type: str, location: str, force_refresh: bool = False) -> Optional[str]:
    """Get a national product from a specific center

    Args:
        product_type: Product type code (e.g., "FXUS01")
        location: Location code (e.g., "KWNH")
        force_refresh: Whether to force a refresh of the data

    Returns:
        Text of the product or None if not available
    """
    try:
        endpoint = f"products/types/{product_type}/locations/{location}"
        products = self._make_request(endpoint, force_refresh=force_refresh)

        if "@graph" not in products or not products["@graph"]:
            return None

        # Get the latest product
        latest_product = products["@graph"][0]
        latest_product_id = latest_product["id"]

        # Get the product text
        product_endpoint = f"products/{latest_product_id}"
        product = self._make_request(product_endpoint, force_refresh=force_refresh)

        return product.get("productText")
    except Exception as e:
        logger.error(f"Error getting national product {product_type} from {location}: {str(e)}")
        return None

def get_national_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
    """Get national forecast data from various centers

    Returns:
        Dictionary containing national forecast data
    """
    result = {
        "wpc": {
            "short_range": self.get_national_product("FXUS01", "KWNH", force_refresh),
            "medium_range": self.get_national_product("FXUS06", "KWNH", force_refresh),
            "extended": self.get_national_product("FXUS07", "KWNH", force_refresh),
            "qpf": self.get_national_product("FXUS02", "KWNH", force_refresh)
        },
        "spc": {
            "day1": self.get_national_product("ACUS01", "KWNS", force_refresh),
            "day2": self.get_national_product("ACUS02", "KWNS", force_refresh),
            "day3": self.get_national_product("ACUS03", "KWNS", force_refresh)
        },
        "nhc": {
            "atlantic": self.get_national_product("MIATWOAT", "KNHC", force_refresh),
            "east_pacific": self.get_national_product("MIATWOEP", "KNHC", force_refresh)
        },
        "cpc": {
            "6_10_day": self.get_national_product("FXUS05", "KWNC", force_refresh),
            "8_14_day": self.get_national_product("FXUS07", "KWNC", force_refresh)
        }
    }

    return result
```

### 2. Weather Service Updates

Add methods to the `WeatherService` class to handle national forecast data:

```python
def get_national_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
    """Get national forecast data

    Args:
        force_refresh: Whether to force a refresh of the data

    Returns:
        Dictionary containing national forecast data
    """
    try:
        return self.api_client.get_national_forecast_data(force_refresh=force_refresh)
    except Exception as e:
        logger.error(f"Error getting national forecast data: {str(e)}")
        raise ApiClientError(f"Unable to retrieve national forecast data: {str(e)}")
```

### 3. Async Fetcher Updates

Add a new fetcher class for national forecast data:

```python
class NationalForecastFetcher(BaseFetcher):
    """Fetcher for national forecast data"""

    def fetch(self, on_success=None, on_error=None, additional_data=None):
        """Fetch national forecast data asynchronously

        Args:
            on_success: Callback for successful fetch
            on_error: Callback for error handling
            additional_data: Additional data to pass to callbacks
        """
        # Cancel any existing fetch
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Cancelling in-progress national forecast fetch")
            self._stop_event.set()
            self.thread.join(0.5)

        # Reset stop event for new fetch
        self._stop_event.clear()

        # Create and start new thread
        self.thread = threading.Thread(
            target=self._fetch_thread,
            args=(on_success, on_error, additional_data)
        )
        self.thread.daemon = True
        self.thread.start()

    def _fetch_thread(self, on_success, on_error, additional_data):
        """Thread function to fetch the national forecast data

        Args:
            on_success: Success callback
            on_error: Error callback
            additional_data: Additional data to pass to callbacks
        """
        try:
            # Check if we've been asked to stop
            if self._stop_event.is_set():
                logger.debug("National forecast fetch cancelled before API call")
                return

            # Get national forecast data from API
            national_data = self.api_client.get_national_forecast_data()

            # Check again if we've been asked to stop before delivering results
            if self._stop_event.is_set():
                logger.debug("National forecast fetch completed but cancelled")
                return

            # Call success callback on main thread
            if on_success:
                if additional_data is not None:
                    safe_call_after(on_success, national_data, *additional_data)
                else:
                    safe_call_after(on_success, national_data)
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Failed to retrieve national forecast data: {str(e)}")
                if on_error:
                    error_msg = f"Unable to retrieve national forecast data: {str(e)}"
                    if additional_data is not None:
                        safe_call_after(on_error, error_msg, *additional_data)
                    else:
                        safe_call_after(on_error, error_msg)
```

### 4. Weather App Updates

Update the `_FetchWeatherData` method in both `WeatherApp` and `WeatherAppRefactored` classes to handle the Nationwide location:

```python
def _FetchWeatherData(self, location):
    """Fetch weather data using the weather service

    Args:
        location: Tuple of (name, lat, lon)
    """
    name, lat, lon = location
    self.SetStatusText(f"Updating weather data for {name}...")

    # --- Start Loading State ---
    self.refresh_btn.Disable()  # Disable refresh button
    # Show loading message
    self.forecast_text.SetValue("Loading forecast...")
    self.alerts_list.DeleteAllItems()  # Clear previous alerts
    # --- End Loading State ---

    # Reset completion flags for this fetch cycle
    self._forecast_complete = False
    self._alerts_complete = False

    # Check if this is the Nationwide location
    if self.location_service.is_nationwide_location(name):
        # Fetch national forecast data
        self.national_forecast_fetcher.fetch(
            on_success=self._on_national_forecast_fetched,
            on_error=self._on_national_forecast_error
        )

        # No alerts for Nationwide view
        self._alerts_complete = True
    else:
        # Start forecast fetching thread
        self.forecast_fetcher.fetch(
            lat, lon, on_success=self._on_forecast_fetched, on_error=self._on_forecast_error
        )

        # Get precise location setting from config
        precise_location = self.config.get("settings", {}).get(PRECISE_LOCATION_ALERTS_KEY, True)
        alert_radius = self.config.get("settings", {}).get(ALERT_RADIUS_KEY, 25)

        # Start alerts fetching thread with precise location setting
        self.alerts_fetcher.fetch(
            lat,
            lon,
            on_success=self._on_alerts_fetched,
            on_error=self._on_alerts_error,
            precise_location=precise_location,
            radius=alert_radius,
        )
```

Add handler methods for national forecast data:

```python
def _on_national_forecast_fetched(self, national_data):
    """Handle the fetched national forecast data in the main thread

    Args:
        national_data: Dictionary with national forecast data
    """
    # Save forecast data
    self.current_forecast = national_data

    # Format the national forecast data for display
    formatted_text = self._format_national_forecast(national_data)

    # Update display
    self.forecast_text.SetValue(formatted_text)

    # Update timestamp
    self.last_update = time.time()

    # Mark forecast as complete and check overall completion
    self._forecast_complete = True
    self._check_update_complete()

def _on_national_forecast_error(self, error):
    """Handle national forecast fetch error

    Args:
        error: Error message
    """
    logger.error(f"National forecast fetch error: {error}")
    self.forecast_text.SetValue(f"Error fetching national forecast: {error}")

    # Mark forecast as complete and check overall completion
    self._forecast_complete = True
    self._check_update_complete()

def _format_national_forecast(self, national_data):
    """Format national forecast data for display

    Args:
        national_data: Dictionary with national forecast data

    Returns:
        Formatted text for display
    """
    lines = []

    # Add WPC data
    wpc_data = national_data.get("wpc", {})
    if wpc_data:
        lines.append("=== WEATHER PREDICTION CENTER (WPC) ===")

        # Short Range Forecast
        short_range = wpc_data.get("short_range")
        if short_range:
            lines.append("\n--- SHORT RANGE FORECAST (Days 1-3) ---")
            # Extract and add a summary (first few lines)
            summary = "\n".join(short_range.split("\n")[0:10])
            lines.append(summary)
            lines.append("(View full discussion for more details)")

        # Medium Range Forecast
        medium_range = wpc_data.get("medium_range")
        if medium_range:
            lines.append("\n--- MEDIUM RANGE FORECAST (Days 3-7) ---")
            # Extract and add a summary (first few lines)
            summary = "\n".join(medium_range.split("\n")[0:10])
            lines.append(summary)
            lines.append("(View full discussion for more details)")

    # Add SPC data
    spc_data = national_data.get("spc", {})
    if spc_data:
        lines.append("\n=== STORM PREDICTION CENTER (SPC) ===")

        # Day 1 Outlook
        day1 = spc_data.get("day1")
        if day1:
            lines.append("\n--- DAY 1 CONVECTIVE OUTLOOK ---")
            # Extract and add a summary (first few lines)
            summary = "\n".join(day1.split("\n")[0:10])
            lines.append(summary)
            lines.append("(View full discussion for more details)")

    # Add NHC data during hurricane season (June 1 - November 30)
    current_month = datetime.now().month
    if 6 <= current_month <= 11:  # Hurricane season
        nhc_data = national_data.get("nhc", {})
        if nhc_data:
            lines.append("\n=== NATIONAL HURRICANE CENTER (NHC) ===")

            # Atlantic Outlook
            atlantic = nhc_data.get("atlantic")
            if atlantic:
                lines.append("\n--- ATLANTIC TROPICAL WEATHER OUTLOOK ---")
                # Extract and add a summary (first few lines)
                summary = "\n".join(atlantic.split("\n")[0:10])
                lines.append(summary)
                lines.append("(View full discussion for more details)")

    # Add CPC data
    cpc_data = national_data.get("cpc", {})
    if cpc_data:
        lines.append("\n=== CLIMATE PREDICTION CENTER (CPC) ===")

        # 6-10 Day Outlook
        outlook_6_10 = cpc_data.get("6_10_day")
        if outlook_6_10:
            lines.append("\n--- 6-10 DAY OUTLOOK ---")
            # Extract and add a summary (first few lines)
            summary = "\n".join(outlook_6_10.split("\n")[0:10])
            lines.append(summary)
            lines.append("(View full discussion for more details)")

    return "\n".join(lines)
```

### 5. Discussion Dialog Updates

Update the discussion dialog to handle national forecast discussions:

```python
class NationalDiscussionDialog(wx.Dialog):
    """Dialog for displaying national forecast discussions"""

    def __init__(self, parent, national_data):
        """Initialize the dialog

        Args:
            parent: Parent window
            national_data: Dictionary with national forecast data
        """
        super().__init__(
            parent,
            title="National Forecast Discussions",
            size=(800, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )

        self.national_data = national_data
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create notebook for different centers
        self.notebook = wx.Notebook(panel)

        # Add WPC page
        wpc_panel = self._create_wpc_panel(self.notebook)
        self.notebook.AddPage(wpc_panel, "WPC")

        # Add SPC page
        spc_panel = self._create_spc_panel(self.notebook)
        self.notebook.AddPage(spc_panel, "SPC")

        # Add NHC page during hurricane season
        current_month = datetime.now().month
        if 6 <= current_month <= 11:  # Hurricane season
            nhc_panel = self._create_nhc_panel(self.notebook)
            self.notebook.AddPage(nhc_panel, "NHC")

        # Add CPC page
        cpc_panel = self._create_cpc_panel(self.notebook)
        self.notebook.AddPage(cpc_panel, "CPC")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Add close button
        button_sizer = wx.StdDialogButtonSizer()
        close_button = wx.Button(panel, wx.ID_CLOSE)
        close_button.Bind(wx.EVT_BUTTON, self.OnClose)
        button_sizer.AddButton(close_button)
        button_sizer.Realize()

        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        self.Layout()

    def _create_wpc_panel(self, parent):
        """Create the WPC panel

        Args:
            parent: Parent notebook

        Returns:
            Panel with WPC discussions
        """
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        wpc_notebook = wx.Notebook(panel)

        # Add Short Range page
        short_range_panel = wx.Panel(wpc_notebook)
        short_range_sizer = wx.BoxSizer(wx.VERTICAL)
        short_range_text = wx.TextCtrl(
            short_range_panel,
            value=self.national_data.get("wpc", {}).get("short_range", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        short_range_sizer.Add(short_range_text, 1, wx.EXPAND)
        short_range_panel.SetSizer(short_range_sizer)
        wpc_notebook.AddPage(short_range_panel, "Short Range (Days 1-3)")

        # Add Medium Range page
        medium_range_panel = wx.Panel(wpc_notebook)
        medium_range_sizer = wx.BoxSizer(wx.VERTICAL)
        medium_range_text = wx.TextCtrl(
            medium_range_panel,
            value=self.national_data.get("wpc", {}).get("medium_range", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        medium_range_sizer.Add(medium_range_text, 1, wx.EXPAND)
        medium_range_panel.SetSizer(medium_range_sizer)
        wpc_notebook.AddPage(medium_range_panel, "Medium Range (Days 3-7)")

        # Add Extended Range page
        extended_panel = wx.Panel(wpc_notebook)
        extended_sizer = wx.BoxSizer(wx.VERTICAL)
        extended_text = wx.TextCtrl(
            extended_panel,
            value=self.national_data.get("wpc", {}).get("extended", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        extended_sizer.Add(extended_text, 1, wx.EXPAND)
        extended_panel.SetSizer(extended_sizer)
        wpc_notebook.AddPage(extended_panel, "Extended (Days 8-10)")

        # Add QPF page
        qpf_panel = wx.Panel(wpc_notebook)
        qpf_sizer = wx.BoxSizer(wx.VERTICAL)
        qpf_text = wx.TextCtrl(
            qpf_panel,
            value=self.national_data.get("wpc", {}).get("qpf", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        qpf_sizer.Add(qpf_text, 1, wx.EXPAND)
        qpf_panel.SetSizer(qpf_sizer)
        wpc_notebook.AddPage(qpf_panel, "QPF Discussion")

        sizer.Add(wpc_notebook, 1, wx.EXPAND)
        panel.SetSizer(sizer)

        return panel

    # Similar methods for _create_spc_panel, _create_nhc_panel, and _create_cpc_panel

    def OnClose(self, event):
        """Handle close button click

        Args:
            event: Button event
        """
        self.EndModal(wx.ID_CLOSE)
```

## Next Steps

After implementing the nationwide forecast integration, the next steps will be:

1. Implement the nationwide discussions feature
2. Add settings to hide/show the Nationwide view
