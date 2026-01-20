"""PyInstaller hook for AccessiWeather.

This hook ensures all necessary modules and data files are included.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all submodules
hiddenimports = collect_submodules("accessiweather")

# Add additional hidden imports
hiddenimports += [
    "accessiweather.api",
    "accessiweather.config",
    "accessiweather.dialogs",
    "accessiweather.display",
    "accessiweather.models",
    "accessiweather.notifications",
    "accessiweather.services",
    "accessiweather.ui",
    "accessiweather.utils",
]

# Collect data files (resources, soundpacks)
datas = collect_data_files("accessiweather", include_py_files=False)
