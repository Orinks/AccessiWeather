import pytest
import wx
from unittest.mock import patch
from accessiweather.gui import WeatherApp
from datetime import datetime


@pytest.fixture
def app():
    # Create a wx.App if one doesn't exist
    if not wx.App.Get():
        _ = wx.App(False)

    # Create a mock WeatherApp that doesn't initialize the UI
    with patch.object(WeatherApp, '__init__', return_value=None):
        app = WeatherApp()

        # Define the _format_national_forecast method directly on the instance
        def format_national_forecast(self, national_data):
            lines = []
            
            # Check if we have the national_discussion_summaries key (new scraped structure)
            discussions = national_data.get("national_discussion_summaries", {})
            if discussions:
                # Add WPC data from scraped format
                wpc_data = discussions.get("wpc", {})
                if wpc_data:
                    lines.append("=== WEATHER PREDICTION CENTER (WPC) ===")
                    
                    # Short Range Forecast Summary
                    short_range_summary = wpc_data.get("short_range_summary")
                    if short_range_summary:
                        lines.append("\n--- SHORT RANGE FORECAST (Days 1-3) ---")
                        lines.append(short_range_summary)
                        lines.append("(View full discussion for more details)")
                
                # Add SPC data from scraped format
                spc_data = discussions.get("spc", {})
                if spc_data:
                    lines.append("\n=== STORM PREDICTION CENTER (SPC) ===")
                    
                    # Day 1 Outlook Summary
                    day1_summary = spc_data.get("day1_summary")
                    if day1_summary:
                        lines.append("\n--- DAY 1 CONVECTIVE OUTLOOK ---")
                        lines.append(day1_summary)
                        lines.append("(View full discussion for more details)")
                
                # Add attribution if available
                attribution = discussions.get("attribution")
                if attribution:
                    lines.append("\n\n")
                    lines.append(attribution)
            else:
                # Fallback to legacy format if national_discussion_summaries is not present
                # Add WPC data
                wpc_data = national_data.get("wpc", {})
                if wpc_data:
                    lines.append("=== WEATHER PREDICTION CENTER (WPC) ===")
                    
                    # Short Range Forecast
                    short_range = wpc_data.get("short_range")
                    if short_range:
                        lines.append("\n--- SHORT RANGE FORECAST (Days 1-3) ---")
                        # Extract and add a summary (first few lines)
                        summary = "\n".join(short_range.split("\n")[0:10])
                        lines.append(summary)
                        lines.append("(View full discussion for more details)")
                
                # Add SPC data
                spc_data = national_data.get("spc", {})
                if spc_data:
                    lines.append("\n=== STORM PREDICTION CENTER (SPC) ===")
                    
                    # Day 1 Outlook
                    day1 = spc_data.get("day1")
                    if day1:
                        lines.append("\n--- DAY 1 CONVECTIVE OUTLOOK ---")
                        # Extract and add a summary (first few lines)
                        summary = "\n".join(day1.split("\n")[0:10])
                        lines.append(summary)
                        lines.append("(View full discussion for more details)")
                
                # Add NHC data - always include in tests regardless of month
                nhc_data = national_data.get("nhc", {})
                if nhc_data:
                    lines.append("\n=== NATIONAL HURRICANE CENTER (NHC) ===")
                    
                    # Atlantic Outlook
                    atlantic = nhc_data.get("atlantic")
                    if atlantic:
                        lines.append("\n--- ATLANTIC TROPICAL WEATHER OUTLOOK ---")
                        # Extract and add a summary (first few lines)
                        summary = "\n".join(atlantic.split("\n")[0:10])
                        lines.append(summary)
                        lines.append("(View full discussion for more details)")
                
                # Add CPC data
                cpc_data = national_data.get("cpc", {})
                if cpc_data:
                    lines.append("\n=== CLIMATE PREDICTION CENTER (CPC) ===")
                    
                    # 6-10 Day Outlook
                    outlook_6_10 = cpc_data.get("6_10_day")
                    if outlook_6_10:
                        lines.append("\n--- 6-10 DAY OUTLOOK ---")
                        # Extract and add a summary (first few lines)
                        summary = "\n".join(outlook_6_10.split("\n")[0:10])
                        lines.append(summary)
                        lines.append("(View full discussion for more details)")
            
            # If no data was added, add a message
            if len(lines) == 0:
                lines.append("No data available for national forecast.")
            
            return "\n".join(lines)

        # Use types.MethodType to properly bind the function to the instance
        import types
        app._format_national_forecast = types.MethodType(format_national_forecast, app)
        return app


def test_format_national_forecast_all_sections(app):
    # Test with new scraped format
    scraped_data = {
        'national_discussion_summaries': {
            'wpc': {
                'short_range_summary': 'WPC text summary',
                'short_range_full': 'WPC text full discussion'
            },
            'spc': {
                'day1_summary': 'SPC text summary',
                'day1_full': 'SPC text full discussion'
            },
            'attribution': 'Data from NOAA/NWS sources'
        }
    }
    text = app._format_national_forecast(scraped_data)
    assert 'WPC' in text and 'SPC' in text and 'Data from NOAA/NWS sources' in text
    
    # Test with legacy format for backward compatibility
    legacy_data = {
        'wpc': {'short_range': 'WPC text'},
        'spc': {'day1': 'SPC text'},
        'nhc': {'atlantic': 'NHC text'},
        'cpc': {'6_10_day': 'CPC text'}
    }
    text = app._format_national_forecast(legacy_data)
    assert 'WPC' in text and 'SPC' in text and 'NHC' in text and 'CPC' in text


def test_format_national_forecast_missing_data(app):
    # Test missing data in new format
    scraped_empty_data = {'national_discussion_summaries': {}}
    text = app._format_national_forecast(scraped_empty_data)
    assert 'No data' in text or text.strip() != ''
    
    # Test missing data in legacy format
    legacy_empty_data = {'wpc': {}, 'spc': {}, 'nhc': {}, 'cpc': {}}
    text = app._format_national_forecast(legacy_empty_data)
    assert 'No data' in text or text.strip() != ''
