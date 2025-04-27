from setuptools import find_packages, setup

setup(
    name="accessiweather",
    version="0.9.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "wxPython",
        "requests",
        "plyer",  # For cross-platform notifications
        "geopy",  # For geocoding addresses and zip codes
        "python-dateutil",  # For parsing ISO timestamps
        "beautifulsoup4",  # For parsing HTML in the scraper
    ],
    extras_require={"dev": ["pytest", "pytest-mock"]},
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
