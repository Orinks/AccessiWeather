"""List-related accessible UI components for AccessiWeather

This module provides list-related accessible UI widgets that enhance screen reader support.
"""

import logging

import wx
import wx.lib.mixins.listctrl as listmix

logger = logging.getLogger(__name__)


class AccessibleListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """List control with enhanced accessibility support and auto-width columns"""

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

        # Track column headers for accessibility
        self.column_headers = []

    def set_label(self, label):
        """Set the accessible label

        Args:
            label: New accessible label

        """
        self.SetName(label)

    def InsertColumn(self, col, heading, format=wx.LIST_FORMAT_LEFT, width=-1):
        """Insert a column and track its header for accessibility

        Args:
            col: Column index
            heading: Column heading
            format: Column format
            width: Column width

        Returns:
            Index of the new column

        """
        # Track column header
        if col >= len(self.column_headers):
            self.column_headers.extend([""] * (col - len(self.column_headers) + 1))
        self.column_headers[col] = heading

        return super().InsertColumn(col, heading, format, width)

    def GetItemText(self, item, col=0):
        """Get item text with better accessibility support

        Args:
            item: Item index
            col: Column index

        Returns:
            Item text

        """
        # For column 0, use the built-in method
        if col == 0:
            return super().GetItemText(item)

        # For other columns, use GetItem
        info = wx.ListItem()
        info.SetId(item)
        info.SetColumn(col)
        info.SetMask(wx.LIST_MASK_TEXT)
        self.GetItem(info)
        return info.GetText()
