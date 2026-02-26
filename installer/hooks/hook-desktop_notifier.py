"""PyInstaller hook for desktop_notifier WinRT support on Windows."""

from PyInstaller.utils.hooks import collect_dynamic_libs

hiddenimports = [
    # desktop-notifier Windows backend is imported dynamically.
    "desktop_notifier.backends.winrt",
    # WinRT modules used by desktop-notifier's backend.
    "winrt.system",
    "winrt.windows.applicationmodel.core",
    "winrt.windows.data.xml.dom",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
    "winrt.windows.ui.notifications",
]

binaries = (
    collect_dynamic_libs("winrt.system")
    + collect_dynamic_libs("winrt.windows.applicationmodel.core")
    + collect_dynamic_libs("winrt.windows.data.xml.dom")
    + collect_dynamic_libs("winrt.windows.foundation")
    + collect_dynamic_libs("winrt.windows.foundation.collections")
    + collect_dynamic_libs("winrt.windows.ui.notifications")
)
