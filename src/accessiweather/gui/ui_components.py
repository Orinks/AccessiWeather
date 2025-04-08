"""Accessible UI components for AccessiWeather

This module provides accessible UI widgets that enhance screen reader support.
"""

import logging
import threading

import wx
import wx.lib.mixins.listctrl as listmix

logger = logging.getLogger(__name__)


class AccessibleStaticText(wx.StaticText):
    """Static text with enhanced accessibility support"""

    def __init__(self, parent, id=wx.ID_ANY, label="", **kwargs):
        """Initialize accessible static text

        Args:
            parent: Parent window
            id: Control ID
            label: Text label
            **kwargs: Additional arguments for wx.StaticText
        """
        super().__init__(parent, id, label, **kwargs)

        # Set accessible name
        self.SetName(label)

        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
            accessible.SetRole(wx.ACC_ROLE_STATICTEXT)

    def SetLabel(self, label):
        """Set text label with accessibility support

        Args:
            label: Text label
        """
        super().SetLabel(label)
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)


class AccessibleTextCtrl(wx.TextCtrl):

    def __init__(self, parent, id=wx.ID_ANY, value="", label="", **kwargs):
        """Initialize accessible text control

        Args:
            parent: Parent window
            id: Control ID
            value: Initial text value
            label: Accessible label
            **kwargs: Additional arguments for wx.TextCtrl
        """
        super().__init__(parent, id, value, **kwargs)

        # Set accessible name
        self.SetName(label)

        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
            accessible.SetRole(wx.ACC_ROLE_TEXT)

        # Set keyboard event handlers for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    def SetLabel(self, label):
        """Set accessible label

        Args:
            label: Accessible label
        """
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)

    def OnKeyDown(self, event):
        """Handle key down event

        Args:
            event: Key event
        """
        # Implement custom keyboard handling for accessibility
        # For now, just pass the event to the default handler
        event.Skip()


class AccessibleChoice(wx.Choice):
    """Choice control with enhanced accessibility support"""

    def __init__(self, parent, id=wx.ID_ANY, choices=None, label="", **kwargs):
        """Initialize accessible choice control

        Args:
            parent: Parent window
            id: Control ID
            choices: List of choices
            label: Accessible label
            **kwargs: Additional arguments for wx.Choice
        """
        if choices is None:
            choices = []
        super().__init__(parent, id, choices=choices, **kwargs)

        # Set accessible name
        self.SetName(label)

        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
            accessible.SetRole(wx.ACC_ROLE_COMBOBOX)

        # Set keyboard event handlers for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    def SetLabel(self, label):
        """Set accessible label

        Args:
            label: Accessible label
        """
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)

    def OnKeyDown(self, event):
        """Handle key down event

        Args:
            event: Key event
        """
        # Add accessible keyboard navigation here
        event.Skip()


class AccessibleButton(wx.Button):
    """Button with enhanced accessibility support"""

    def __init__(self, parent, id=wx.ID_ANY, label="", **kwargs):
        """Initialize accessible button

        Args:
            parent: Parent window
            id: Control ID
            label: Button label
            **kwargs: Additional arguments for wx.Button
        """
        super().__init__(parent, id, label, **kwargs)

        # Set accessible name
        self.SetName(label)

        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
            accessible.SetRole(wx.ACC_ROLE_BUTTON)

        # Set keyboard event handlers for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    def SetLabel(self, label):
        """Set button label with accessibility support

        Args:
            label: Button label
        """
        super().SetLabel(label)
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)

    def OnKeyDown(self, event):
        """Handle key down event

        Args:
            event: Key event
        """
        key_code = event.GetKeyCode()

        # Handle Enter or Space to activate button (standard for accessibility)
        if key_code in (wx.WXK_RETURN, wx.WXK_SPACE):
            evt = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.GetId())
            evt.SetEventObject(self)
            self.GetEventHandler().ProcessEvent(evt)
        else:
            event.Skip()


class AccessibleListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """List control with enhanced accessibility support"""

    def __init__(self, parent, id=wx.ID_ANY, label="", **kwargs):
        """Initialize accessible list control

        Args:
            parent: Parent window
            id: Control ID
            label: Accessible label
            **kwargs: Additional arguments for wx.ListCtrl
        """
        wx.ListCtrl.__init__(self, parent, id, **kwargs)
        listmix.ListCtrlAutoWidthMixin.__init__(self)

        # Set accessible name
        self.SetName(label)

        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
            accessible.SetRole(wx.ACC_ROLE_LIST)

        # Set keyboard event handlers for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    def SetLabel(self, label):
        """Set accessible label

        Args:
            label: Accessible label
        """
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)

    def OnKeyDown(self, event):
        """Handle key down event for accessibility navigation

        Args:
            event: Key event
        """
        # Add more accessible keyboard navigation here if needed
        event.Skip()


class AccessibleComboBox(wx.ComboBox):
    """Combo box with enhanced accessibility support

    This provides a dropdown combobox that allows typing and selecting from options,
    with full screen reader support for accessibility.
    """

    def __init__(self, parent, id=wx.ID_ANY, value="", choices=None, label="", **kwargs):
        """Initialize accessible combo box

        Args:
            parent: Parent window
            id: Control ID
            value: Initial text value
            choices: List of choices
            label: Accessible label
            **kwargs: Additional arguments for wx.ComboBox
        """
        if choices is None:
            choices = []

        # Use default style if none provided to ensure it's editable
        if "style" not in kwargs:
            kwargs["style"] = wx.CB_DROPDOWN

        super().__init__(parent, id, value, choices=choices, **kwargs)

        # Set accessible name
        self.SetName(label)

        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
            accessible.SetRole(wx.ACC_ROLE_COMBOBOX)

    def SetLabel(self, label):
        """Set accessible label

        Args:
            label: Accessible label
        """
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)

    def SetValue(self, value):
        """Set the value of the combo box and update selection if it matches an item

        Args:
            value: Text value to set
        """
        # Call parent method to set text value
        super().SetValue(value)

        # Try to find the text in the list of choices and update selection
        for i in range(self.GetCount()):
            if self.GetString(i) == value:
                self.SetSelection(i)
                break

    def Append(self, items):
        """Add items to the combo box

        Args:
            items: String or list of strings to add

        Returns:
            Index of the last item added
        """
        # Handle both single string and list of strings
        if isinstance(items, str):
            return super().Append(items)
        else:
            # Add items one by one
            last_index = -1
            for item in items:
                last_index = super().Append(item)
            return last_index


class WeatherTextCompleter(wx.TextCompleterSimple):
    """Concrete implementation of TextCompleterSimple for location autocompletion

    This implements the abstract methods required by TextCompleterSimple.
    """

    def __init__(self):
        """Initialize the text completer"""
        super().__init__()
        self.completions = []

    def GetCompletions(self, prefix):
        """Get completions that match the given prefix

        Args:
            prefix: Text prefix to match

        Returns:
            List of matching completions
        """
        if not prefix:
            return []

        # Case-insensitive prefix matching
        prefix_lower = prefix.lower()
        return [comp for comp in self.completions if comp.lower().startswith(prefix_lower)]

    def SetCompletions(self, completions):
        """Set the available completions

        Args:
            completions: List of completion strings
        """
        self.completions = completions.copy() if completions else []


class WeatherLocationAutocomplete(AccessibleComboBox):
    """Weather location search with autocomplete support

    This component extends the AccessibleComboBox to provide location
    search autocomplete functionality with wxPython's TextCompleterSimple.

    It asynchronously fetches location suggestions as the user types and
    provides accessible autocompletion for screen readers.
    """

    def __init__(
        self, parent, id=wx.ID_ANY, value="", choices=None, label="", min_chars=2, **kwargs
    ):
        """Initialize the autocomplete location search control

        Args:
            parent: Parent window
            id: Control ID
            value: Initial text value
            choices: List of initial choices
            label: Accessible label
            min_chars: Minimum characters before triggering suggestions
            **kwargs: Additional arguments for wx.ComboBox
        """
        # Initialize with default choices if none provided
        if choices is None:
            choices = []

        super().__init__(parent, id, value, choices=choices, label=label, **kwargs)

        # Create text completer for autocomplete
        self.completer = WeatherTextCompleter()
        self.AutoComplete(self.completer)

        # Store configuration
        self.min_chars = min_chars
        self.geocoding_service = None
        self.choices = choices.copy() if choices else []
        self.lock = threading.RLock()
        self.suppress_events = False

        # Create debounce timer for typing
        self.debounce_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_debounce_timer, self.debounce_timer)
        self.debounce_delay = 300  # milliseconds

        # Thread control
        self.fetch_thread = None
        self.stop_event = threading.Event()

        # Bind events
        self.Bind(wx.EVT_TEXT, self.on_text_changed)

    def set_geocoding_service(self, service):
        """Set the geocoding service for location suggestions

        Args:
            service: GeocodingService instance
        """
        self.geocoding_service = service

    def SetValue(self, value):
        """Set the value of the combo box while preventing duplicate events

        Args:
            value: Text value to set
        """
        # Temporarily suppress events to prevent duplicate calls
        self.suppress_events = True
        super().SetValue(value)
        self.suppress_events = False

    def on_text_changed(self, event):
        """Handle text change event to trigger autocomplete

        Args:
            event: Text event
        """
        # Skip if events are suppressed
        if self.suppress_events:
            if event:
                event.Skip()
            return

        # Get current text
        current_text = self.GetValue()

        # Check if we have enough characters to trigger suggestions
        if current_text and len(current_text) >= self.min_chars and self.geocoding_service:
            # Restart the debounce timer
            self.debounce_timer.Stop()
            self.debounce_timer.Start(self.debounce_delay, wx.TIMER_ONE_SHOT)

            # In test mode, fetch immediately
            if hasattr(wx, "testing") and wx.testing:
                suggestions = self.geocoding_service.suggest_locations(current_text)
                self._update_completions(suggestions)

        # Allow event to continue
        if event:
            event.Skip()

    def on_debounce_timer(self, event):
        """Handle debounce timer event to fetch suggestions after typing stops

        Args:
            event: Timer event
        """
        current_text = self.GetValue()
        if current_text and len(current_text) >= self.min_chars and self.geocoding_service:
            self._fetch_suggestions(current_text)

    def _fetch_suggestions(self, text):
        """Fetch location suggestions in the background

        Args:
            text: Text to get suggestions for
        """
        # Cancel any existing fetch
        if self.fetch_thread is not None and self.fetch_thread.is_alive():
            logger.debug("Cancelling in-progress location suggestions fetch")
            self.stop_event.set()
            # Don't join here as it may block the UI

        # Reset stop event for new fetch
        self.stop_event.clear()

        # Start a new thread to fetch suggestions
        self.fetch_thread = threading.Thread(target=self._fetch_thread_func, args=(text,))
        self.fetch_thread.daemon = True
        self.fetch_thread.start()

    def _fetch_thread_func(self, text):
        """Thread function to fetch location suggestions

        Args:
            text: Text to get suggestions for
        """
        try:
            # Check if we've been asked to stop
            if self.stop_event.is_set():
                logger.debug("Location suggestions fetch cancelled")
                return

            # Get suggestions from geocoding service
            suggestions = self.geocoding_service.suggest_locations(text)

            # Check again if we've been asked to stop before delivering results
            if self.stop_event.is_set():
                logger.debug("Suggestions fetch completed but results discarded")
                return

            # Update the completer on the main thread
            wx.CallAfter(self._update_completions, suggestions)
        except Exception as e:
            if not self.stop_event.is_set():
                logger.error(f"Error fetching location suggestions: {e}")

    def _update_completions(self, suggestions):
        """Update the completions in the text completer

        Args:
            suggestions: List of location suggestions
        """
        if suggestions:
            with self.lock:
                # Update completions in the text completer
                self.completer.SetCompletions(suggestions)

                # Trigger autocomplete with current text
                self.AutoComplete(self.completer)

    def update_choices(self, choices):
        """Update autocomplete choices

        This is a convenience method primarily used for testing.

        Args:
            choices: List of location strings
        """
        if not choices:
            return

        with self.lock:
            # Update the completer with new choices
            self.completer.SetCompletions(choices)

            # Also update dropdown items if needed
            self.Clear()
            self.Append(choices)

    def get_completer(self):
        """Get the text completer for testing

        Returns:
            TextCompleterSimple instance
        """
        return self.completer
