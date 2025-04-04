"""Mock wxPython module for headless testing in CI environments."""


class App:

    def __init__(self, *args, **kwargs):
        pass

    def MainLoop(self):
        pass

    def SetExitOnFrameDelete(self, *args):
        pass


class Frame:

    def __init__(self, *args, **kwargs):
        pass

    def Show(self, *args):
        pass

    def Close(self, *args):
        pass


class Panel:

    def __init__(self, *args, **kwargs):
        pass


class BoxSizer:

    def __init__(self, *args):
        pass

    def Add(self, *args, **kwargs):
        return self

    def AddSpacer(self, *args):
        return self


class StaticText:

    def __init__(self, *args, **kwargs):
        pass

    def SetLabel(self, *args):
        pass


class Button:

    def __init__(self, *args, **kwargs):
        pass

    def Bind(self, *args, **kwargs):
        pass


class ComboBox:

    def __init__(self, *args, **kwargs):
        pass

    def Bind(self, *args, **kwargs):
        pass

    def SetItems(self, items):
        pass

    def SetValue(self, value):
        pass

    def GetValue(self):
        return ""


# Constants
VERTICAL = 0
HORIZONTAL = 1
ID_ANY = -1
EXPAND = 2
ALL = 15
