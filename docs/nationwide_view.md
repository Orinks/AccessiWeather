# Nationwide View Feature

The Nationwide view is a special feature in AccessiWeather that provides a comprehensive overview of the national weather situation in the United States. This document explains how to use the feature, what data it provides, and how to troubleshoot common issues.

## Overview

The Nationwide view is implemented as a special location named "Nationwide" that appears in your locations dropdown. Unlike regular locations, the Nationwide location:

- Cannot be removed (the remove button is disabled when it's selected)
- Can be hidden/shown via settings
- Provides national forecast data and discussions from various NOAA/NWS centers
- Is automatically added during application initialization

## Data Sources

The Nationwide view retrieves data from several NOAA/NWS centers:

1. **Weather Prediction Center (WPC)**
   - Short-range forecasts (1-2 days)
   - Medium-range forecasts (3-7 days)
   - Extended forecasts (8-14 days)
   - Quantitative Precipitation Forecasts (QPF)

2. **Storm Prediction Center (SPC)**
   - Day 1 Convective Outlook
   - Day 2 Convective Outlook

3. **National Hurricane Center (NHC)** (during hurricane season, June-November)
   - Atlantic basin tropical weather outlook
   - Eastern Pacific basin tropical weather outlook

4. **Climate Prediction Center (CPC)**
   - 6-10 day outlook
   - 8-14 day outlook

## Using the Nationwide View

### Accessing the Nationwide View

1. Open the AccessiWeather application
2. Select "Nationwide" from the locations dropdown
3. The main display will update to show national forecast information

### Viewing National Discussions

1. Select "Nationwide" from the locations dropdown
2. Click the "View Forecast Discussion" button
3. A tabbed dialog will appear with discussions from different centers:
   - WPC tab: Weather Prediction Center discussions
   - SPC tab: Storm Prediction Center discussions
   - NHC tab: National Hurricane Center discussions (during hurricane season)

### Hiding/Showing the Nationwide Location

If you don't use the Nationwide view, you can hide it from the locations dropdown:

1. Click the "Settings" button
2. Uncheck the "Show Nationwide location" checkbox
3. Click "Save"

To show it again, follow the same steps but check the box.

## Accessibility Features

The Nationwide view is fully accessible with screen readers:

- All discussions are presented as plain text that can be read by screen readers
- The tabbed interface in the discussion dialog is keyboard navigable
- Each tab has proper focus management and screen reader announcements
- Discussion text is formatted for readability with proper headings and paragraphs

## Troubleshooting

### Common Issues

1. **National discussions unavailable**
   - The NOAA websites may be undergoing maintenance
   - Your internet connection may be interrupted
   - Try again later or check the NOAA website status

2. **Nationwide location not appearing in dropdown**
   - Check your settings to ensure "Show Nationwide location" is enabled
   - If it's still missing, try restarting the application

3. **Empty or incomplete discussions**
   - The discussion format on the NOAA websites may have changed
   - Report this issue on our GitHub repository

4. **Slow loading of national discussions**
   - National discussions require fetching data from multiple sources
   - A loading dialog will appear during this process
   - The application implements rate limiting to avoid overloading NOAA servers

## Technical Details

The Nationwide view is implemented using several components:

- `location.py`: Defines the Nationwide location constants and special handling
- `national_forecast_fetcher.py`: Fetches national forecast data asynchronously
- `services/national_discussion_scraper.py`: Scrapes national discussions from NOAA websites
- `gui/dialogs.py`: Contains the `NationalDiscussionDialog` for displaying discussions
- `gui/handlers/discussion_handlers.py`: Handles viewing nationwide discussions

The feature uses web scraping to retrieve discussion text from NOAA websites, as this information is not available through the standard NOAA API. The application implements rate limiting to avoid overloading NOAA servers.

## Data Attribution

All national forecast data and discussions are provided by the National Oceanic and Atmospheric Administration (NOAA) and the National Weather Service (NWS). The data is sourced from:

- Weather Prediction Center: https://www.wpc.ncep.noaa.gov/
- Storm Prediction Center: https://www.spc.noaa.gov/
- National Hurricane Center: https://www.nhc.noaa.gov/
- Climate Prediction Center: https://www.cpc.ncep.noaa.gov/

Please refer to the NOAA and NWS websites for the most up-to-date and comprehensive information.
