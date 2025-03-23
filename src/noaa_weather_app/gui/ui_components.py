"""Accessible UI components for NOAA Weather App

This module provides accessible UI widgets that enhance screen reader support.
"""

import wx
import logging

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
        
        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
            accessible.SetRole(wx.ACC_ROLE_TEXT)
            
    def SetLabel(self, label):
        """Set accessible label
        
        Args:
            label: Accessible label
        """
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)


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
            accessible.SetRole(wx.ACC_ROLE_CHOICE)
            
    def SetLabel(self, label):
        """Set accessible label
        
        Args:
            label: Accessible label
        """
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)


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


class AccessibleListCtrl(wx.ListCtrl):
    """List control with enhanced accessibility support"""
    
    def __init__(self, parent, id=wx.ID_ANY, label="", **kwargs):
        """Initialize accessible list control
        
        Args:
            parent: Parent window
            id: Control ID
            label: Accessible label
            **kwargs: Additional arguments for wx.ListCtrl
        """
        super().__init__(parent, id, **kwargs)
        
        # Set accessible name
        self.SetName(label)
        
        # Get accessible object
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
            accessible.SetRole(wx.ACC_ROLE_LIST)
            
    def SetLabel(self, label):
        """Set accessible label
        
        Args:
            label: Accessible label
        """
        self.SetName(label)
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName(label)
