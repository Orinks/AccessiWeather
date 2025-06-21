"""Basic accessible UI components for AccessiWeather

This module provides basic accessible UI widgets that enhance screen reader support.
"""

import logging

import wx

logger = logging.getLogger(__name__)


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

        # Get accessible object and set properties for screen readers
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
            accessible.SetRole(wx.ACC_ROLE_COMBOBOX)

        # Bind keyboard events for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

        # Bind character hook for screen reader character navigation
        self.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)

    def SetLabel(self, label):
        """Set accessible label

        Args:
            label: Accessible label

        """
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)

    def set_label(self, label):
        """Set the accessible label (alias for SetLabel for consistency)

        Args:
            label: New accessible label

        """
        self.SetLabel(label)

    def SetItems(self, items):
        """Set the items in the combo box

        Args:
            items: List of items

        """
        self.Clear()
        for item in items:
            self.Append(item)

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
        # Add items one by one
        last_index = -1
        for item in items:
            last_index = super().Append(item)
        return last_index

    def OnKeyDown(self, event):
        """Handle key down event for accessibility navigation

        Args:
            event: Key event

        """
        key_code = event.GetKeyCode()

        # Handle Alt+Down to open dropdown (standard accessibility pattern)
        if key_code == wx.WXK_DOWN and event.AltDown():
            # Simulate dropdown open
            self.Popup()
        else:
            # Allow default handling for other keys
            event.Skip()

    def OnCharHook(self, event):
        """Handle character hook events for screen reader accessibility

        This method intercepts character navigation events and announces
        the current character to screen readers when navigating with arrow keys.

        Args:
            event: Character hook event

        """
        key_code = event.GetKeyCode()

        # Get current text and insertion point
        text = self.GetValue()
        insertion_point = self.GetInsertionPoint()

        # Handle left/right arrow keys for character navigation
        if key_code == wx.WXK_LEFT:
            # If not at the beginning of the text
            if insertion_point > 0:
                # Get the character to the left of the cursor
                char_to_announce = text[insertion_point - 1 : insertion_point]
                # Announce the character to screen readers
                self._announce_character(char_to_announce)
        elif key_code == wx.WXK_RIGHT:
            # If not at the end of the text
            if insertion_point < len(text):
                # Get the character to the right of the cursor
                char_to_announce = text[insertion_point : insertion_point + 1]
                # Announce the character to screen readers
                self._announce_character(char_to_announce)
        elif key_code == wx.WXK_HOME:
            # Announce moving to the beginning of the text
            if insertion_point > 0:
                self._announce_navigation("Beginning of text")
        elif key_code == wx.WXK_END:
            # Announce moving to the end of the text
            if insertion_point < len(text):
                self._announce_navigation("End of text")

        # Allow the event to be processed normally
        event.Skip()

    def _announce_character(self, char):
        """Announce a character to screen readers

        Args:
            char: Character to announce

        """
        if not char:
            return

        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            # Special handling for whitespace and special characters
            if char == " ":
                accessible.SetDescription("space")
            elif char == "\n":
                accessible.SetDescription("new line")
            elif char == "\t":
                accessible.SetDescription("tab")
            else:
                accessible.SetDescription(char)

    def _announce_navigation(self, message):
        """Announce a navigation message to screen readers

        Args:
            message: Message to announce

        """
        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetDescription(message)


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

    def SetLabel(self, label):
        """Set the label and update accessibility name

        Args:
            label: New label text

        """
        super().SetLabel(label)
        self.SetName(label)


class AccessibleTextCtrl(wx.TextCtrl):
    """Text control with enhanced accessibility support"""

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

    def set_label(self, label):
        """Set the accessible label

        Args:
            label: New accessible label

        """
        self.SetName(label)


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

    def set_label(self, label):
        """Set the accessible label

        Args:
            label: New accessible label

        """
        self.SetName(label)

    def SetItems(self, items):
        """Set the items in the choice control

        Args:
            items: List of items

        """
        self.Clear()
        for item in items:
            self.Append(item)


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

    def SetLabel(self, label):
        """Set the label and update accessibility name

        Args:
            label: New label text

        """
        super().SetLabel(label)
        self.SetName(label)
