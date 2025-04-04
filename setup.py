"""Setup script for AccessiWeather package."""

from setuptools import find_packages, setup

setup(
    name="accessiweather",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "requests",
        "pytest",
        "pytest-mock",
        "plyer",  # For cross-platform notifications
        "geopy",  # For geocoding addresses and zip codes
        "python-dateutil",  # For parsing ISO timestamps
    ],
    extras_require={
        # GUI dependencies, optional for headless environments
        "gui": ["wxPython"],
    },
    description=(
        "AccessiWeather: An accessible weather application using NOAA data "
        "with focus on screen reader compatibility"
    ),
    author="User",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "accessiweather=accessiweather.cli:main",
        ],
    },
)
