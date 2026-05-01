"""ScrolledPanel compatibility shim for the sound pack wizard."""

from __future__ import annotations

import wx

try:
    import wx.lib.scrolledpanel as scrolled
except ModuleNotFoundError:
    _SCROLLED_BASE = wx.Panel if hasattr(wx, "Panel") else object

    class _FallbackScrolledPanel(_SCROLLED_BASE):
        """Fallback when wx.lib.scrolledpanel is unavailable."""

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)

        def SetupScrolling(self) -> None:  # noqa: N802
            if hasattr(self, "SetScrollRate"):
                self.SetScrollRate(10, 10)

    class _FallbackScrolledModule:
        ScrolledPanel = _FallbackScrolledPanel

    scrolled = _FallbackScrolledModule()
