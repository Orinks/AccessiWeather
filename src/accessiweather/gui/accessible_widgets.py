"""Accessible UI components for AccessiWeather

This module provides accessible UI widgets that enhance screen reader support.
"""

import logging

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
            evt = wx.CommandEvent(
                wx.wxEVT_COMMAND_BUTTON_CLICKED, self.GetId()
            )
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

    This provides a dropdown combobox that allows typing and selecting from
    options, with full screen reader support for accessibility.
    """

    def __init__(
        self, parent, id=wx.ID_ANY, value="", choices=None, label="", **kwargs
    ):
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
        """Set the value of the combo box and update selection if it matches
        an item

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