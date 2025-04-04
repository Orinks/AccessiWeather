"""Mock wxPython module for headless testing in CI environments."""


class App:
    """Mock wx.App."""

    def __init__(self, *args, **kwargs):
        """Initialize mock App."""
        pass

    def MainLoop(self):
        """Mock MainLoop."""
        pass

    def SetExitOnFrameDelete(self, *args):
        """Mock SetExitOnFrameDelete."""
        pass


class Frame:
    """Mock wx.Frame."""

    def __init__(self, *args, **kwargs):
        """Initialize mock Frame."""
        pass

    def Show(self, *args):
        """Mock Show."""
        pass

    def Close(self, *args):
        """Mock Close."""
        pass


class Panel:
    """Mock wx.Panel."""

    def __init__(self, *args, **kwargs):
        """Initialize mock Panel."""
        pass


class BoxSizer:
    """Mock wx.BoxSizer."""

    def __init__(self, *args):
        """Initialize mock BoxSizer."""
        pass

    def Add(self, *args, **kwargs):
        """Mock Add."""
        return self

    def AddSpacer(self, *args):
        """Mock AddSpacer."""
        return self


class StaticText:
    """Mock wx.StaticText."""

    def __init__(self, *args, **kwargs):
        """Initialize mock StaticText."""
        pass

    def SetLabel(self, *args):
        """Mock SetLabel."""
        pass


class Button:
    """Mock wx.Button."""

    def __init__(self, *args, **kwargs):
        """Initialize mock Button."""
        pass

    def Bind(self, *args, **kwargs):
        """Mock Bind."""
        pass


class ComboBox:
    """Mock wx.ComboBox."""

    def __init__(self, *args, **kwargs):
        """Initialize mock ComboBox."""
        pass

    def Bind(self, *args, **kwargs):
        """Mock Bind."""
        pass

    def SetItems(self, items):
        """Mock SetItems."""
        pass

    def SetValue(self, value):
        """Mock SetValue."""
        pass

    def GetValue(self):
        """Mock GetValue."""
        return ""


# Constants
VERTICAL = 0
HORIZONTAL = 1
ID_ANY = -1
EXPAND = 2
ALL = 15
