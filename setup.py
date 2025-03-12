from setuptools import setup, find_packages

setup(
    name="accessiweather",
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
    description="AccessiWeather: An accessible weather application using NOAA data with focus on screen reader compatibility",
    author="User",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    entry_points={
        'console_scripts': [
            'accessiweather=noaa_weather_app.cli:main',
        ],
    },
)
