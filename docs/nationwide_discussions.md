# Nationwide Discussions Feature

This document outlines the implementation plan for the nationwide discussions feature in the AccessiWeather application.

## Overview

The nationwide discussions feature will allow users to view forecast discussions from various NOAA/NWS centers when the Nationwide location is selected. This will provide a comprehensive view of the national weather situation.

## Implementation Plan

### 1. Update the OnViewDiscussion Handler

Update the `OnViewDiscussion` method in both `WeatherAppHandlers` and `WeatherAppHandlersRefactored` classes to handle the Nationwide location:

```python
def OnViewDiscussion(self, event):  # event is required by wx
    """Handle view discussion button click

    Args:
        event: Button event
    """
    # Get current location from the location service
    location = self.location_service.get_current_location()
    if location is None:
        wx.MessageBox(
            "Please select a location first", "No Location Selected", wx.OK | wx.ICON_ERROR
        )
        return

    name, lat, lon = location

    # Check if this is the Nationwide location
    if self.location_service.is_nationwide_location(name):
        self._handle_nationwide_discussion()
        return

    # Regular location discussion handling
    self.SetStatusText(f"Loading forecast discussion for {name}...")

    # Create a progress dialog
    loading_dialog = wx.ProgressDialog(
        "Fetching Discussion",
        f"Fetching forecast discussion for {name}...",
        maximum=100,
        parent=self,
        style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
    )

    # Store the loading dialog as an instance variable so we can access it later
    self._discussion_loading_dialog = loading_dialog

    # Start a timer to pulse the dialog and check for cancel
    self._discussion_timer = wx.Timer(self)
    self.Bind(wx.EVT_TIMER, self._on_discussion_timer, self._discussion_timer)
    self._discussion_timer.Start(100)  # Check every 100ms

    # Fetch discussion data
    self.discussion_fetcher.fetch(
        lat,
        lon,
        on_success=functools.partial(
            self._on_discussion_fetched, name=name, loading_dialog=loading_dialog
        ),
        on_error=functools.partial(
            self._on_discussion_error, name=name, loading_dialog=loading_dialog
        ),
    )
```

### 2. Add Nationwide Discussion Handler

Add a method to handle nationwide discussions:

```python
def _handle_nationwide_discussion(self):
    """Handle nationwide discussion view"""
    self.SetStatusText("Loading nationwide discussions...")

    # Create a progress dialog
    loading_dialog = wx.ProgressDialog(
        "Fetching Discussions",
        "Fetching nationwide discussions...",
        maximum=100,
        parent=self,
        style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
    )

    # Store the loading dialog as an instance variable so we can access it later
    self._discussion_loading_dialog = loading_dialog

    # Start a timer to pulse the dialog and check for cancel
    self._discussion_timer = wx.Timer(self)
    self.Bind(wx.EVT_TIMER, self._on_discussion_timer, self._discussion_timer)
    self._discussion_timer.Start(100)  # Check every 100ms

    # Fetch national forecast data
    self.national_forecast_fetcher.fetch(
        on_success=functools.partial(
            self._on_nationwide_discussion_fetched, loading_dialog=loading_dialog
        ),
        on_error=functools.partial(
            self._on_nationwide_discussion_error, loading_dialog=loading_dialog
        ),
    )
```

### 3. Add Nationwide Discussion Callback Handlers

Add callback handlers for nationwide discussions:

```python
def _on_nationwide_discussion_fetched(self, national_data, loading_dialog=None):
    """Handle the fetched nationwide discussions in the main thread

    Args:
        national_data: Dictionary with national forecast data
        loading_dialog: Progress dialog instance (optional)
    """
    logger.debug("Nationwide discussions fetched successfully, handling in main thread")

    # Make sure we clean up properly before showing the discussion dialog
    self._cleanup_discussion_loading(loading_dialog)

    # Show nationwide discussion dialog
    logger.debug("Creating and showing nationwide discussion dialog")
    dialog = NationalDiscussionDialog(self, national_data)
    dialog.ShowModal()
    dialog.Destroy()
    logger.debug("Nationwide discussion dialog closed")

    # Re-enable button if it exists
    if hasattr(self, "discussion_btn") and self.discussion_btn:
        self.discussion_btn.Enable()

def _on_nationwide_discussion_error(self, error, loading_dialog=None):
    """Handle nationwide discussion fetch error

    Args:
        error: Error message
        loading_dialog: Progress dialog instance (optional)
    """
    logger.debug("Nationwide discussion fetch error, handling in main thread")

    # Make sure we clean up properly before showing the error message
    self._cleanup_discussion_loading(loading_dialog)

    logger.error(f"Nationwide discussion fetch error: {error}")

    wx.MessageBox(
        f"Error fetching nationwide discussions: {error}",
        "Fetch Error",
        wx.OK | wx.ICON_ERROR,
    )

    # Re-enable button if it exists
    if hasattr(self, "discussion_btn") and self.discussion_btn:
        self.discussion_btn.Enable()
```

### 4. Create National Discussion Dialog

Create a dialog to display nationwide discussions:

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

    def _create_spc_panel(self, parent):
        """Create the SPC panel

        Args:
            parent: Parent notebook

        Returns:
            Panel with SPC discussions
        """
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        spc_notebook = wx.Notebook(panel)

        # Add Day 1 page
        day1_panel = wx.Panel(spc_notebook)
        day1_sizer = wx.BoxSizer(wx.VERTICAL)
        day1_text = wx.TextCtrl(
            day1_panel,
            value=self.national_data.get("spc", {}).get("day1", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        day1_sizer.Add(day1_text, 1, wx.EXPAND)
        day1_panel.SetSizer(day1_sizer)
        spc_notebook.AddPage(day1_panel, "Day 1 Outlook")

        # Add Day 2 page
        day2_panel = wx.Panel(spc_notebook)
        day2_sizer = wx.BoxSizer(wx.VERTICAL)
        day2_text = wx.TextCtrl(
            day2_panel,
            value=self.national_data.get("spc", {}).get("day2", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        day2_sizer.Add(day2_text, 1, wx.EXPAND)
        day2_panel.SetSizer(day2_sizer)
        spc_notebook.AddPage(day2_panel, "Day 2 Outlook")

        # Add Day 3 page
        day3_panel = wx.Panel(spc_notebook)
        day3_sizer = wx.BoxSizer(wx.VERTICAL)
        day3_text = wx.TextCtrl(
            day3_panel,
            value=self.national_data.get("spc", {}).get("day3", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        day3_sizer.Add(day3_text, 1, wx.EXPAND)
        day3_panel.SetSizer(day3_sizer)
        spc_notebook.AddPage(day3_panel, "Day 3 Outlook")

        sizer.Add(spc_notebook, 1, wx.EXPAND)
        panel.SetSizer(sizer)

        return panel

    def _create_nhc_panel(self, parent):
        """Create the NHC panel

        Args:
            parent: Parent notebook

        Returns:
            Panel with NHC discussions
        """
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        nhc_notebook = wx.Notebook(panel)

        # Add Atlantic page
        atlantic_panel = wx.Panel(nhc_notebook)
        atlantic_sizer = wx.BoxSizer(wx.VERTICAL)
        atlantic_text = wx.TextCtrl(
            atlantic_panel,
            value=self.national_data.get("nhc", {}).get("atlantic", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        atlantic_sizer.Add(atlantic_text, 1, wx.EXPAND)
        atlantic_panel.SetSizer(atlantic_sizer)
        nhc_notebook.AddPage(atlantic_panel, "Atlantic Outlook")

        # Add East Pacific page
        east_pacific_panel = wx.Panel(nhc_notebook)
        east_pacific_sizer = wx.BoxSizer(wx.VERTICAL)
        east_pacific_text = wx.TextCtrl(
            east_pacific_panel,
            value=self.national_data.get("nhc", {}).get("east_pacific", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        east_pacific_sizer.Add(east_pacific_text, 1, wx.EXPAND)
        east_pacific_panel.SetSizer(east_pacific_sizer)
        nhc_notebook.AddPage(east_pacific_panel, "East Pacific Outlook")

        sizer.Add(nhc_notebook, 1, wx.EXPAND)
        panel.SetSizer(sizer)

        return panel

    def _create_cpc_panel(self, parent):
        """Create the CPC panel

        Args:
            parent: Parent notebook

        Returns:
            Panel with CPC discussions
        """
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        cpc_notebook = wx.Notebook(panel)

        # Add 6-10 Day page
        outlook_6_10_panel = wx.Panel(cpc_notebook)
        outlook_6_10_sizer = wx.BoxSizer(wx.VERTICAL)
        outlook_6_10_text = wx.TextCtrl(
            outlook_6_10_panel,
            value=self.national_data.get("cpc", {}).get("6_10_day", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        outlook_6_10_sizer.Add(outlook_6_10_text, 1, wx.EXPAND)
        outlook_6_10_panel.SetSizer(outlook_6_10_sizer)
        cpc_notebook.AddPage(outlook_6_10_panel, "6-10 Day Outlook")

        # Add 8-14 Day page
        outlook_8_14_panel = wx.Panel(cpc_notebook)
        outlook_8_14_sizer = wx.BoxSizer(wx.VERTICAL)
        outlook_8_14_text = wx.TextCtrl(
            outlook_8_14_panel,
            value=self.national_data.get("cpc", {}).get("8_14_day", "No data available"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        outlook_8_14_sizer.Add(outlook_8_14_text, 1, wx.EXPAND)
        outlook_8_14_panel.SetSizer(outlook_8_14_sizer)
        cpc_notebook.AddPage(outlook_8_14_panel, "8-14 Day Outlook")

        sizer.Add(cpc_notebook, 1, wx.EXPAND)
        panel.SetSizer(sizer)

        return panel

    def OnClose(self, event):
        """Handle close button click

        Args:
            event: Button event
        """
        self.EndModal(wx.ID_CLOSE)
```

## Next Steps

After implementing the nationwide discussions feature, the next step will be to add settings to hide/show the Nationwide view.
