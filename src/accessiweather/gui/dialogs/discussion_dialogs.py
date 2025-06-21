"""Discussion dialog components for AccessiWeather

This module provides dialog windows for displaying weather discussion content,
including local weather discussions and national forecast discussions.

Extracted from the original dialogs.py file for better maintainability
and separation of concerns.
"""

import logging

import wx

from ..ui_components import AccessibleButton

logger = logging.getLogger(__name__)


class WeatherDiscussionDialog(wx.Dialog):
    """Dialog for displaying weather discussion text"""

    def __init__(self, parent, title="Weather Discussion", text=""):
        """Initialize the weather discussion dialog

        Args:
            parent: Parent window
            title: Dialog title
            text: Discussion text

        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        # Log the discussion text for debugging
        logger.debug(
            f"Creating discussion dialog with text type: {type(text)}, length: {len(text)}"
        )
        if not text:
            logger.warning("Empty discussion text provided to dialog")
            text = "No discussion available"
        else:
            # Log a preview of the text
            preview = text[:100].replace("\n", "\\n")
            logger.debug(f"Text preview: {preview}...")

        try:
            logger.debug("Creating panel for discussion dialog")
            panel = wx.Panel(self)
            sizer = wx.BoxSizer(wx.VERTICAL)

            # Create a text control for the discussion
            logger.debug("Creating text control for discussion dialog")
            self.text_ctrl = wx.TextCtrl(
                panel,
                style=wx.TE_MULTILINE | wx.TE_READONLY,  # Removed wx.TE_RICH2
            )

            # Set a monospace font for better readability of formatted text
            logger.debug("Setting font for text control")
            font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            self.text_ctrl.SetFont(font)

            # Normalize line endings for consistent screen reader behavior
            if isinstance(text, str):
                text = text.replace("\r\n", "\n").replace("\r", "\n")

            # Set the text after setting the font
            logger.debug(f"Setting text value (length: {len(text)})")
            self.text_ctrl.SetValue(text)
            logger.debug("Text value set successfully")
        except Exception as e:
            logger.error(f"Error creating discussion dialog components: {e}")
            raise

        try:
            # Set accessible name and description
            logger.debug("Setting accessible name for text control")
            self.text_ctrl.SetName("Weather Discussion Text")

            # Get accessible object
            logger.debug("Getting accessible object for text control")
            accessible = self.text_ctrl.GetAccessible()
            if accessible:
                logger.debug("Setting accessible properties")
                accessible.SetName("Weather Discussion Text")
                accessible.SetRole(wx.ACC_ROLE_TEXT)

            # Add to sizer with expansion
            logger.debug("Adding text control to sizer")
            sizer.Add(self.text_ctrl, 1, wx.ALL | wx.EXPAND, 10)

            # Close button
            logger.debug("Creating close button")
            close_button = AccessibleButton(panel, wx.ID_CLOSE, "Close")
            sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

            logger.debug("Setting panel sizer")
            panel.SetSizer(sizer)

            logger.debug("Setting dialog size")
            self.SetSize((800, 600))
            logger.debug("Dialog size set successfully")
        except Exception as e:
            logger.error(f"Error finalizing discussion dialog setup: {e}")
            raise

        try:
            # Center on parent
            logger.debug("Centering dialog on parent")
            self.CenterOnParent()

            # Bind events
            logger.debug("Binding close button event")
            self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CLOSE)

            # Set initial focus for accessibility
            logger.debug("Setting initial focus to text control")
            self.text_ctrl.SetFocus()
            logger.debug("WeatherDiscussionDialog initialization complete")
        except Exception as e:
            logger.error(f"Error in final dialog setup: {e}")

    def OnClose(self, event):  # event is required by wx
        """Handle close button event

        Args:
            event: Button event

        """
        logger.debug("Close button clicked, ending modal dialog")
        try:
            self.EndModal(wx.ID_CLOSE)
            logger.debug("Dialog closed successfully")
        except Exception as e:
            logger.error(f"Error closing dialog: {e}")


class NationalDiscussionDialog(wx.Dialog):
    """Dialog for displaying national forecast discussions with a tabbed interface for accessibility."""

    def __init__(self, parent, national_data):
        """Initialize the dialog.

        Args:
            parent: Parent window
            national_data: Dictionary with national forecast data containing WPC and SPC discussions

        """
        super().__init__(
            parent,
            title="National Weather Discussions",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(800, 600),
        )

        self.national_data = national_data
        self._init_ui()
        self.Center()

    def _init_ui(self):
        """Initialize the dialog UI with a tabbed interface for accessibility."""
        logger.debug("Initializing NationalDiscussionDialog UI")

        try:
            # Create main panel and sizer
            panel = wx.Panel(self)
            main_sizer = wx.BoxSizer(wx.VERTICAL)

            # Get the discussion data
            summaries = self.national_data.get("national_discussion_summaries", {})

            # Store the discussion texts for both sources
            self.wpc_text = summaries.get("wpc", {}).get(
                "short_range_full", "WPC discussion unavailable"
            )
            self.spc_text = summaries.get("spc", {}).get("day1_full", "SPC discussion unavailable")

            # Normalize line endings for both texts
            if isinstance(self.wpc_text, str):
                self.wpc_text = self.wpc_text.replace("\r\n", "\n").replace("\r", "\n")
            if isinstance(self.spc_text, str):
                self.spc_text = self.spc_text.replace("\r\n", "\n").replace("\r", "\n")

            # Create notebook (tabbed interface)
            self.notebook = wx.Notebook(panel)
            self.notebook.SetName("National Discussion Tabs")

            # Create WPC tab
            wpc_panel = wx.Panel(self.notebook)
            wpc_sizer = wx.BoxSizer(wx.VERTICAL)

            # Create text control for WPC discussion
            self.wpc_text_ctrl = wx.TextCtrl(
                wpc_panel,
                style=wx.TE_MULTILINE | wx.TE_READONLY,
                size=(-1, 450),
            )

            # Set accessible name and role
            self.wpc_text_ctrl.SetName("WPC Discussion Text")
            accessible = self.wpc_text_ctrl.GetAccessible()
            if accessible:
                accessible.SetName("Weather Prediction Center Discussion Text")
                accessible.SetRole(wx.ACC_ROLE_TEXT)

            # Set monospace font for better readability
            font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            self.wpc_text_ctrl.SetFont(font)

            # Set the WPC discussion text
            self.wpc_text_ctrl.SetValue(self.wpc_text)

            # Add text control to WPC panel sizer
            wpc_sizer.Add(self.wpc_text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
            wpc_panel.SetSizer(wpc_sizer)

            # Create SPC tab
            spc_panel = wx.Panel(self.notebook)
            spc_sizer = wx.BoxSizer(wx.VERTICAL)

            # Create text control for SPC discussion
            self.spc_text_ctrl = wx.TextCtrl(
                spc_panel,
                style=wx.TE_MULTILINE | wx.TE_READONLY,
                size=(-1, 450),
            )

            # Set accessible name and role
            self.spc_text_ctrl.SetName("SPC Discussion Text")
            accessible = self.spc_text_ctrl.GetAccessible()
            if accessible:
                accessible.SetName("Storm Prediction Center Discussion Text")
                accessible.SetRole(wx.ACC_ROLE_TEXT)

            # Set monospace font for better readability
            self.spc_text_ctrl.SetFont(font)

            # Set the SPC discussion text
            self.spc_text_ctrl.SetValue(self.spc_text)

            # Add text control to SPC panel sizer
            spc_sizer.Add(self.spc_text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
            spc_panel.SetSizer(spc_sizer)

            # Add tabs to notebook
            self.notebook.AddPage(wpc_panel, "Weather Prediction Center")
            self.notebook.AddPage(spc_panel, "Storm Prediction Center")

            # Add notebook to main sizer
            main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

            # Add close button
            close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
            close_btn.SetName("Close Button")
            main_sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)

            # Set the sizer for the panel
            panel.SetSizer(main_sizer)

            # Bind events
            self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)
            close_btn.Bind(wx.EVT_BUTTON, self.on_close)

            # Set initial focus to the notebook for accessibility
            # This allows users to tab to the text control
            self.notebook.SetFocus()

            # Store references for easier access
            self.close_btn = close_btn

            logger.debug("NationalDiscussionDialog UI initialization complete")
        except Exception as e:
            logger.error(f"Error initializing NationalDiscussionDialog UI: {e}")
            wx.MessageBox(
                f"Error creating national discussion dialog: {e}",
                "Dialog Error",
                wx.OK | wx.ICON_ERROR,
            )
            raise

    def on_tab_changed(self, event):
        """Handle tab selection change.

        Args:
            event: Notebook page changed event

        """
        # Simply allow the event to propagate
        # This lets the user tab to the text control instead of automatically setting focus to it
        event.Skip()

    def on_close(self, event):  # event is required by wx
        """Handle close button event.

        Args:
            event: Button event

        """
        logger.debug("Close button clicked, ending modal dialog")
        try:
            self.EndModal(wx.ID_CLOSE)
            logger.debug("Dialog closed successfully")
        except Exception as e:
            logger.error(f"Error closing dialog: {e}")
