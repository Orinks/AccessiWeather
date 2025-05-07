"""Debug console for AccessiWeather

This module provides a console for executing Python code in the context of the application.
"""

import logging
import sys
import traceback
from io import StringIO
from typing import Any, Dict, Optional, TextIO, cast

import wx

logger = logging.getLogger(__name__)


class RedirectText:
    """Redirect stdout/stderr to a text control."""

    def __init__(self, text_ctrl):
        """Initialize the redirect.

        Args:
            text_ctrl: Text control to redirect to
        """
        self.text_ctrl = text_ctrl
        self.buffer = StringIO()
        self.encoding = "utf-8"
        self.errors = None
        self.mode = "w"
        self.name = "<RedirectText>"
        self.newlines = None

    def write(self, string):
        """Write to the text control.

        Args:
            string: String to write
        """
        self.buffer.write(string)

        # If the string ends with a newline, flush the buffer
        if string.endswith("\n"):
            self.flush()

    def flush(self):
        """Flush the buffer to the text control."""
        wx.CallAfter(self._write_to_text_ctrl)

    def _write_to_text_ctrl(self):
        """Write the buffer to the text control."""
        text = self.buffer.getvalue()
        if text:
            self.text_ctrl.AppendText(text)
            self.buffer = StringIO()

    # Additional methods to better match TextIO interface
    def close(self):
        """Close the stream."""
        self.flush()

    def isatty(self):
        """Return False (not a tty)."""
        return False

    def readable(self):
        """Return False (not readable)."""
        return False

    def writable(self):
        """Return True (writable)."""
        return True

    def seekable(self):
        """Return False (not seekable)."""
        return False


class DebugConsole(wx.Frame):
    """Console for executing Python code in the context of the application."""

    def __init__(self, parent=None, context: Optional[Dict[str, Any]] = None):
        """Initialize the debug console.

        Args:
            parent: Parent window
            context: Dictionary of variables to make available in the console
        """
        super().__init__(
            parent,
            title="AccessiWeather Debug Console",
            size=(800, 600),
            style=wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER,
        )

        # Store the context
        self.context = context or {}

        # Set up the UI
        self._create_ui()

        # Bind the close event
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Add some help text
        self._add_help_text()

    def _create_ui(self):
        """Create the UI components."""
        # Create the main panel
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create the output text control
        output_label = wx.StaticText(panel, label="Output:")
        main_sizer.Add(output_label, 0, wx.ALL, 5)

        self.output_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        main_sizer.Add(self.output_text, 1, wx.ALL | wx.EXPAND, 5)

        # Create the input text control
        input_label = wx.StaticText(panel, label="Input:")
        main_sizer.Add(input_label, 0, wx.ALL, 5)

        self.input_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER | wx.HSCROLL
        )
        main_sizer.Add(self.input_text, 0, wx.ALL | wx.EXPAND, 5)

        # Create the button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.execute_btn = wx.Button(panel, label="Execute")
        self.clear_output_btn = wx.Button(panel, label="Clear Output")
        self.clear_input_btn = wx.Button(panel, label="Clear Input")

        button_sizer.Add(self.execute_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.clear_output_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.clear_input_btn, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        # Set the sizer for the panel
        panel.SetSizer(main_sizer)

        # Bind events
        self.execute_btn.Bind(wx.EVT_BUTTON, self.OnExecute)
        self.clear_output_btn.Bind(wx.EVT_BUTTON, self.OnClearOutput)
        self.clear_input_btn.Bind(wx.EVT_BUTTON, self.OnClearInput)
        self.input_text.Bind(wx.EVT_TEXT_ENTER, self.OnExecute)

        # Set up stdout/stderr redirection
        self.stdout_redirect = RedirectText(self.output_text)
        self.stderr_redirect = RedirectText(self.output_text)

        # Set focus to the input text control
        self.input_text.SetFocus()

    def _add_help_text(self):
        """Add help text to the output text control."""
        help_text = """AccessiWeather Debug Console

This console allows you to execute Python code in the context of the application.
The following variables are available:

- app: The WeatherApp instance
- wx: The wxPython module

Example commands:
- app.config  # View the application configuration
- app.location_service.get_all_locations()  # Get all locations
- app.weather_service.get_forecast(lat, lon)  # Get forecast for coordinates

Press Enter or click Execute to run the code.
"""
        self.output_text.SetValue(help_text)

    def OnExecute(self, event):  # event is required by wx
        """Handle execute button click.

        Args:
            event: Button event
        """
        # Get the code to execute
        code = self.input_text.GetValue()
        if not code.strip():
            return

        # Add the code to the output
        self.output_text.AppendText(f"\n>>> {code}\n")

        # Redirect stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = cast(TextIO, self.stdout_redirect)
        sys.stderr = cast(TextIO, self.stderr_redirect)

        try:
            # Execute the code
            result = eval(code, self.context, self.context)

            # Print the result if it's not None
            if result is not None:
                print(repr(result))
        except SyntaxError:
            # If eval fails, try exec
            try:
                exec(code, self.context, self.context)
            except Exception:
                traceback.print_exc()
        except Exception:
            traceback.print_exc()
        finally:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        # Clear the input
        self.input_text.Clear()

    def OnClearOutput(self, event):  # event is required by wx
        """Handle clear output button click.

        Args:
            event: Button event
        """
        self.output_text.Clear()

    def OnClearInput(self, event):  # event is required by wx
        """Handle clear input button click.

        Args:
            event: Button event
        """
        self.input_text.Clear()

    def OnClose(self, event):  # event is required by wx
        """Handle window close event.

        Args:
            event: Close event
        """
        # Hide the window instead of destroying it
        self.Hide()
