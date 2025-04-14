"""Autocomplete-related accessible UI components for AccessiWeather

This module provides the AccessibleComboBox component for enhanced accessibility.
"""

import logging
import threading
from typing import List

import wx

from .basic_components import AccessibleComboBox

logger = logging.getLogger(__name__)


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
        """Initialize weather location autocomplete

        Args:
            parent: Parent window
            id: Control ID
            value: Initial text value
            choices: List of choices
            label: Accessible label
            min_chars: Minimum characters before triggering suggestions
            **kwargs: Additional arguments for wx.ComboBox
        """
        if choices is None:
            choices = []
        super().__init__(parent, id, value, choices=choices, label=label, **kwargs)

        # Create text completer for autocomplete
        self.completer = wx.TextCompleterSimple()
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

        # Override key down handler for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        # Override character hook handler for character-by-character navigation
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

        # Bind dropdown events for accessibility announcements
        self.Bind(wx.EVT_COMBOBOX_DROPDOWN, self.on_dropdown_shown)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, self.on_dropdown_hidden)

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

    def on_debounce_timer(self, event):  # event is required by wx
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

    def _fetch_thread_func(self, text: str) -> None:
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
            if self.geocoding_service is not None:
                suggestions = self.geocoding_service.suggest_locations(text)
            else:
                suggestions = []

            # Check again if we've been asked to stop before delivering results
            if self.stop_event.is_set():
                logger.debug("Suggestions fetch completed but results discarded")
                return

            # Update the completer on the main thread
            wx.CallAfter(self._update_completions, suggestions)
        except Exception as e:
            if not self.stop_event.is_set():
                logger.error(f"Error fetching location suggestions: {e}")

    def _update_completions(self, suggestions: List[str]) -> None:
        """Update the completions in the text completer

        Args:
            suggestions: List of location suggestions
        """
        with self.lock:
            # Update the completer with new suggestions
            self.completer.SetCompletions(suggestions)

            # Also update the dropdown choices
            self.update_choices(suggestions)

            # Announce to screen readers that suggestions are available
            if suggestions:
                # Get accessible object
                accessible = self.GetAccessible()
                if accessible:
                    # Update accessible properties to indicate suggestions are available
                    count = len(suggestions)
                    # Set a description that screen readers can announce
                    msg = f"{count} location suggestions available. Use arrow keys to navigate."
                    accessible.SetDescription(msg)

    def update_choices(self, choices):
        """Update the dropdown choices

        Args:
            choices: List of choices
        """
        with self.lock:
            # Store choices
            self.choices = choices.copy() if choices else []

            # Update dropdown
            self.SetItems(self.choices)

    def get_completer(self):
        """Get the text completer

        Returns:
            WeatherTextCompleter instance
        """
        return self.completer

    def on_key_down(self, event):
        """Handle key down event for enhanced accessibility

        This method improves keyboard navigation for screen readers by providing
        additional keyboard shortcuts and announcing the state of the control.

        Args:
            event: Key event
        """
        key_code = event.GetKeyCode()

        # Handle Alt+Down to open dropdown (standard accessibility pattern)
        if key_code == wx.WXK_DOWN and event.AltDown():
            # Get accessible object
            accessible = self.GetAccessible()
            if accessible and self.GetCount() > 0:
                # Announce dropdown state to screen readers
                accessible.SetDescription("Dropdown list opened")

            # Let parent class handle the dropdown display
            event.Skip()

        # Handle Escape key to close dropdown and announce to screen readers
        elif key_code == wx.WXK_ESCAPE and self.IsPopupShown():
            # Close dropdown
            self.Dismiss()

            # Announce to screen readers
            accessible = self.GetAccessible()
            if accessible:
                accessible.SetDescription("Dropdown list closed")

        # Handle Enter key with special announcement for screen readers
        elif key_code == wx.WXK_RETURN:
            # Get current selection
            selection = self.GetSelection()
            if selection != wx.NOT_FOUND:
                # Get the selected text
                selected_text = self.GetString(selection)

                # Announce selection to screen readers
                accessible = self.GetAccessible()
                if accessible:
                    accessible.SetDescription(f"Selected: {selected_text}")

            # Let default handler process the event
            event.Skip()

        else:
            # For all other keys, let the parent class handle them
            event.Skip()

    def on_dropdown_shown(self, event):
        """Handle dropdown shown event for accessibility announcements

        Args:
            event: Dropdown event
        """
        # Announce to screen readers that the dropdown is shown
        accessible = self.GetAccessible()
        if accessible and self.GetCount() > 0:
            count = self.GetCount()
            msg = f"Dropdown opened with {count} items. Use arrow keys to navigate."
            accessible.SetDescription(msg)

        # Allow event to continue
        event.Skip()

    def on_dropdown_hidden(self, event):
        """Handle dropdown hidden event for accessibility announcements

        Args:
            event: Dropdown event
        """
        # Announce to screen readers that the dropdown is hidden
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetDescription("Dropdown closed")

        # Allow event to continue
        event.Skip()

    def on_char_hook(self, event):
        """Handle character hook events for screen reader accessibility

        This method extends the base class implementation to provide additional
        autocomplete-specific announcements for screen readers.

        Args:
            event: Character hook event
        """
        key_code = event.GetKeyCode()

        # We don't need text and insertion point here, but the parent class will use them

        # Handle up/down arrow keys for dropdown navigation
        if key_code == wx.WXK_UP or key_code == wx.WXK_DOWN:
            if self.IsPopupShown():
                # Let the event process normally first
                event.Skip()

                # Then announce the selected item
                wx.CallAfter(self._announce_selected_item)
                return

        # For all other keys, call the parent class implementation
        # which will handle left/right arrow keys
        super().OnCharHook(event)

    def _announce_selected_item(self):
        """Announce the currently selected item in the dropdown"""
        selection = self.GetSelection()
        if selection != wx.NOT_FOUND:
            # Get the selected text
            selected_text = self.GetString(selection)

            # Announce selection to screen readers
            accessible = self.GetAccessible()
            if accessible:
                accessible.SetDescription(f"Selected: {selected_text}")
