"""Basic accessible UI components for AccessiWeather

This module provides basic accessible UI widgets that enhance screen reader support.
"""

import logging

import wx

logger = logging.getLogger(__name__)


class AccessibleComboBox(wx.ComboBox):
    """Combo box with enhanced accessibility support"""

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
        super().__init__(parent, id, value, choices=choices, **kwargs)

        # Set accessible name
        self.SetName(label)

    def set_label(self, label):
        """Set the accessible label

        Args:
            label: New accessible label
        """
        self.SetName(label)

    def SetItems(self, items):
        """Set the items in the combo box

        Args:
            items: List of items
        """
        self.Clear()
        for item in items:
            self.Append(item)


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
