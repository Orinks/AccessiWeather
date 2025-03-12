from setuptools import setup, find_packages

setup(
    name="noaa_weather_app",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"":"src"},
    install_requires=[
        "wxPython",
        "requests",
        "pytest",
        "pytest-mock",
        "win10toast",  # For Windows notifications
        "geopy",      # For geocoding addresses and zip codes
    ],
    description="Desktop application to check NOAA weather with accessibility features",
    author="User",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    entry_points={
        'console_scripts': [
            'noaa-weather=noaa_weather_app.cli:main',
        ],
    },
)
