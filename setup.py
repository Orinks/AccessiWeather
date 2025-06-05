from setuptools import find_packages, setup

setup(
    name="accessiweather",
    version="0.9.3",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "wxPython",
        "requests",
        "plyer",  # For cross-platform notifications
        "geopy",  # For geocoding addresses and zip codes
        "python-dateutil",  # For parsing ISO timestamps
        "beautifulsoup4",  # For parsing HTML in the scraper
        "httpx>=0.20.0",  # For HTTP requests in API clients
        "attrs>=22.2.0",  # For data classes in generated API client
    ],
    extras_require={"dev": ["pytest", "pytest-mock", "requests-mock"]},
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
