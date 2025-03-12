"""Accessible widgets for NOAA Weather App

This module provides wxPython widgets enhanced with accessibility features.
"""

import wx
import wx.lib.mixins.listctrl as listmix
import logging
from typing import Callable, Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class AccessibleTextCtrl(wx.TextCtrl):
    """An accessible text control with screen reader support"""
    
    def __init__(self, parent, id=wx.ID_ANY, value="", pos=wx.DefaultPosition,
                size=wx.DefaultSize, style=0, validator=wx.DefaultValidator,
                name=wx.TextCtrlNameStr, label=""):
        """Initialize the accessible text control
        
        Args:
            parent: Parent window
            id: Window identifier
            value: Default text value
            pos: Window position
            size: Window size
            style: Window style
            validator: Window validator
            name: Window name
            label: Accessible label for screen readers
        """
        super().__init__(parent, id, value, pos, size, style, validator, name)
        
        self.accessible_label = label
        self.SetName(label)  # Set name for accessibility
        
        # Get accessible object
        self.accessible = self.GetAccessible()
        if self.accessible:
            self.accessible.SetName(label)            
            self.accessible.SetRole(wx.ACC_ROLE_TEXT)
        
        # Set keyboard event handlers for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        
    def OnKeyDown(self, event):
        """Handle key down event
        
        Args:
            event: Key event
        """
        # Implement custom keyboard handling for accessibility
        # For now, just pass the event to the default handler
        event.Skip()


class AccessibleButton(wx.Button):
    """An accessible button with screen reader support"""
    
    def __init__(self, parent, id=wx.ID_ANY, label="", pos=wx.DefaultPosition,
                size=wx.DefaultSize, style=0, validator=wx.DefaultValidator,
                name=wx.ButtonNameStr):
        """Initialize the accessible button
        
        Args:
            parent: Parent window
            id: Window identifier
            label: Button label text
            pos: Window position
            size: Window size
            style: Window style
            validator: Window validator
            name: Window name
        """
        super().__init__(parent, id, label, pos, size, style, validator, name)
        
        # Set accessible name and description
        self.SetName(label)  # Set name for accessibility
        
        # Get accessible object
        self.accessible = self.GetAccessible()
        if self.accessible:
            self.accessible.SetName(label)
            self.accessible.SetRole(wx.ACC_ROLE_BUTTON)
        
        # Set keyboard event handlers for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
    
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
    """An accessible list control with screen reader support"""
    
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition,
                size=wx.DefaultSize, style=wx.LC_REPORT, label=""):
        """Initialize the accessible list control
        
        Args:
            parent: Parent window
            id: Window identifier
            pos: Window position
            size: Window size
            style: Window style
            label: Accessible label for screen readers
        """
        wx.ListCtrl.__init__(self, parent, id, pos, size, style)
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        
        self.accessible_label = label
        self.SetName(label)  # Set name for accessibility
        
        # Get accessible object
        self.accessible = self.GetAccessible()
        if self.accessible:
            self.accessible.SetName(label)
            self.accessible.SetRole(wx.ACC_ROLE_LIST)
        
        # Set keyboard event handlers for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
    
    def OnKeyDown(self, event):
        """Handle key down event for accessibility navigation
        
        Args:
            event: Key event
        """
        key_code = event.GetKeyCode()
        
        # Add more accessible keyboard navigation here
        event.Skip()


class AccessibleStaticText(wx.StaticText):
    """An accessible static text control with screen reader support"""
    
    def __init__(self, parent, id=wx.ID_ANY, label="", pos=wx.DefaultPosition,
                size=wx.DefaultSize, style=0, name=wx.StaticTextNameStr):
        """Initialize the accessible static text
        
        Args:
            parent: Parent window
            id: Window identifier
            label: Text label
            pos: Window position
            size: Window size
            style: Window style
            name: Window name
        """
        super().__init__(parent, id, label, pos, size, style, name)
        
        # Set accessible name and description
        self.SetName(label)  # Set name for accessibility
        
        # Get accessible object
        self.accessible = self.GetAccessible()
        if self.accessible:
            self.accessible.SetName(label)
            self.accessible.SetRole(wx.ACC_ROLE_STATICTEXT)
            

class AccessibleChoice(wx.Choice):
    """An accessible choice/dropdown control with screen reader support"""
    
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition,
                size=wx.DefaultSize, choices=None, style=0,
                validator=wx.DefaultValidator, name=wx.ChoiceNameStr, label=""):
        """Initialize the accessible choice control
        
        Args:
            parent: Parent window
            id: Window identifier
            pos: Window position
            size: Window size
            choices: List of choices to display
            style: Window style
            validator: Window validator
            name: Window name
            label: Accessible label for screen readers
        """
        choices = choices or []
        super().__init__(parent, id, pos, size, choices, style, validator, name)
        
        self.accessible_label = label
        self.SetName(label)  # Set name for accessibility
        
        # Get accessible object
        self.accessible = self.GetAccessible()
        if self.accessible:
            self.accessible.SetName(label)
            self.accessible.SetRole(wx.ACC_ROLE_COMBOBOX)
        
        # Set keyboard event handlers for better accessibility
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
    
    def OnKeyDown(self, event):
        """Handle key down event
        
        Args:
            event: Key event
        """
        # Add accessible keyboard navigation here
        event.Skip()
