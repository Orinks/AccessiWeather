"""Debug log window for AccessiWeather

This module provides a window for viewing and filtering the application log.
"""

import logging
import os
import re
import threading
import time

import wx

logger = logging.getLogger(__name__)


class LogWatcher(threading.Thread):
    """Thread that watches a log file for changes and updates a text control."""

    def __init__(self, log_file: str, callback, interval: float = 1.0):
        """Initialize the log watcher.

        Args:
            log_file: Path to the log file to watch
            callback: Function to call when the log file changes
            interval: Interval in seconds to check for changes
        """
        super().__init__()
        self.daemon = True  # Thread will exit when main thread exits
        self.log_file = log_file
        self.callback = callback
        self.interval = interval
        self.last_position = 0
        self.running = True
        self.last_modified = 0.0  # Use float for timestamp

    def run(self):
        """Run the log watcher thread."""
        while self.running:
            try:
                if os.path.exists(self.log_file):
                    # Check if the file has been modified
                    modified_time = os.path.getmtime(self.log_file)
                    if modified_time > self.last_modified:
                        self.last_modified = float(modified_time)

                        # Read the new content
                        with open(self.log_file, "r") as f:
                            f.seek(self.last_position)
                            new_content = f.read()
                            self.last_position = f.tell()

                        # Call the callback with the new content
                        if new_content:
                            wx.CallAfter(self.callback, new_content)
            except Exception as e:
                logger.error(f"Error in log watcher: {e}")

            # Sleep for the specified interval
            time.sleep(self.interval)

    def stop(self):
        """Stop the log watcher thread."""
        self.running = False


class DebugLogWindow(wx.Frame):
    """Window for viewing and filtering the application log."""

    def __init__(self, parent=None):
        """Initialize the debug log window.

        Args:
            parent: Parent window
        """
        super().__init__(
            parent,
            title="AccessiWeather Debug Log",
            size=(800, 600),
            style=wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER,
        )

        # Set up the UI
        self._create_ui()

        # Set up the log watcher
        self.log_watcher = None
        self._start_log_watcher()

        # Bind the close event
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Load the initial log content
        self._load_log()

    def _create_ui(self):
        """Create the UI components."""
        # Create the main panel
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create the filter controls
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Log level filter
        level_label = wx.StaticText(panel, label="Log Level:")
        filter_sizer.Add(level_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.level_choice = wx.Choice(
            panel, choices=["All", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
        self.level_choice.SetSelection(0)  # Default to "All"
        filter_sizer.Add(self.level_choice, 0, wx.ALL, 5)

        # Text filter
        filter_label = wx.StaticText(panel, label="Filter:")
        filter_sizer.Add(filter_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.filter_text = wx.TextCtrl(panel)
        filter_sizer.Add(self.filter_text, 1, wx.ALL | wx.EXPAND, 5)

        # Apply filter button
        self.apply_btn = wx.Button(panel, label="Apply Filter")
        filter_sizer.Add(self.apply_btn, 0, wx.ALL, 5)

        # Clear filter button
        self.clear_btn = wx.Button(panel, label="Clear Filter")
        filter_sizer.Add(self.clear_btn, 0, wx.ALL, 5)

        main_sizer.Add(filter_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Create the log text control
        self.log_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.TE_RICH
        )
        main_sizer.Add(self.log_text, 1, wx.ALL | wx.EXPAND, 5)

        # Create the button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Clear log button
        self.clear_log_btn = wx.Button(panel, label="Clear Log")
        button_sizer.Add(self.clear_log_btn, 0, wx.ALL, 5)

        # Reload log button
        self.reload_btn = wx.Button(panel, label="Reload Log")
        button_sizer.Add(self.reload_btn, 0, wx.ALL, 5)

        # Auto-scroll checkbox
        self.auto_scroll = wx.CheckBox(panel, label="Auto-scroll")
        self.auto_scroll.SetValue(True)
        button_sizer.Add(self.auto_scroll, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # Add button sizer to main sizer
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        # Set the sizer for the panel
        panel.SetSizer(main_sizer)

        # Bind events
        self.apply_btn.Bind(wx.EVT_BUTTON, self.OnApplyFilter)
        self.clear_btn.Bind(wx.EVT_BUTTON, self.OnClearFilter)
        self.clear_log_btn.Bind(wx.EVT_BUTTON, self.OnClearLog)
        self.reload_btn.Bind(wx.EVT_BUTTON, self.OnReloadLog)
        self.level_choice.Bind(wx.EVT_CHOICE, self.OnApplyFilter)
        self.filter_text.Bind(wx.EVT_TEXT_ENTER, self.OnApplyFilter)

    def _start_log_watcher(self):
        """Start the log watcher thread."""
        log_file = self._get_log_file_path()
        if os.path.exists(log_file):
            self.log_watcher = LogWatcher(log_file, self._on_log_update)
            self.log_watcher.start()
        else:
            logger.error(f"Log file not found: {log_file}")
            self.log_text.SetValue(f"Log file not found: {log_file}")

    def _get_log_file_path(self) -> str:
        """Get the path to the log file.

        Returns:
            Path to the log file
        """
        log_dir = os.path.expanduser("~/AccessiWeather_logs")
        return os.path.join(log_dir, "accessiweather.log")

    def _load_log(self):
        """Load the log file content."""
        log_file = self._get_log_file_path()
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                    content = f.read()
                    self._apply_filter(content, replace=True)

                    # Update the last position for the log watcher
                    if self.log_watcher:
                        self.log_watcher.last_position = len(content)
            except Exception as e:
                logger.error(f"Error loading log file: {e}")
                self.log_text.SetValue(f"Error loading log file: {str(e)}")
        else:
            logger.error(f"Log file not found: {log_file}")
            self.log_text.SetValue(f"Log file not found: {log_file}")

    def _on_log_update(self, new_content: str):
        """Handle log file updates.

        Args:
            new_content: New content from the log file
        """
        self._apply_filter(new_content, replace=False)

    def _apply_filter(self, content: str, replace: bool = True):
        """Apply the current filter to the log content.

        Args:
            content: Log content to filter
            replace: Whether to replace the current content or append
        """
        # Get the current filter settings
        level = self.level_choice.GetStringSelection()
        filter_text = self.filter_text.GetValue().strip()

        # Filter by log level
        if level != "All":
            # Create a regex pattern to match the selected log level
            pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - " + level
            level_regex = re.compile(pattern, re.IGNORECASE)

            # Filter the content
            filtered_lines = []
            for line in content.splitlines():
                if level_regex.search(line):
                    filtered_lines.append(line)

            content = "\n".join(filtered_lines)

        # Filter by text
        if filter_text:
            # Filter the content
            filtered_lines = []
            for line in content.splitlines():
                if filter_text.lower() in line.lower():
                    filtered_lines.append(line)

            content = "\n".join(filtered_lines)

        # Update the log text
        if replace:
            self.log_text.SetValue(content)
        else:
            self.log_text.AppendText(content)

        # Auto-scroll to the end if enabled
        if self.auto_scroll.GetValue():
            self.log_text.ShowPosition(self.log_text.GetLastPosition())

    def OnApplyFilter(self, event):  # event is required by wx
        """Handle apply filter button click.

        Args:
            event: Button event
        """
        # Reload the log with the new filter
        self._load_log()

    def OnClearFilter(self, event):  # event is required by wx
        """Handle clear filter button click.

        Args:
            event: Button event
        """
        # Clear the filter controls
        self.level_choice.SetSelection(0)  # "All"
        self.filter_text.SetValue("")

        # Reload the log
        self._load_log()

    def OnClearLog(self, event):  # event is required by wx
        """Handle clear log button click.

        Args:
            event: Button event
        """
        # Clear the log text
        self.log_text.Clear()

    def OnReloadLog(self, event):  # event is required by wx
        """Handle reload log button click.

        Args:
            event: Button event
        """
        # Reload the log
        self._load_log()

    def OnClose(self, event):  # event is required by wx
        """Handle window close event.

        Args:
            event: Close event
        """
        # Stop the log watcher
        if self.log_watcher:
            self.log_watcher.stop()

        # Hide the window instead of destroying it
        self.Hide()
