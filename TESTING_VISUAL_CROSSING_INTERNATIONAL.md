# Testing Visual Crossing International Alerts

## Overview

Visual Crossing provides **global weather alert coverage**, making it essential for AccessiWeather users outside the United States. Unlike the National Weather Service (NWS) which only covers US locations, Visual Crossing can provide weather alerts for any location worldwide.

## Test Scripts Available

### 1. `debug_visual_crossing_alerts.py` - Comprehensive Debug Tool
**Enhanced with international locations**

This is the main debugging script that now tests both US and international locations:

**US Locations Tested:**
- Miami, FL (hurricanes, thunderstorms)
- Oklahoma City, OK (tornadoes, severe weather)
- Denver, CO (winter weather, high winds)
- Phoenix, AZ (heat warnings, dust storms)

**International Locations Tested:**
- London, UK (European weather systems)
- Tokyo, Japan (typhoons, earthquakes)
- Sydney, Australia (bushfires, storms)
- Mumbai, India (monsoons, cyclones)
- Toronto, Canada (winter storms)
- Mexico City, Mexico (air quality, storms)

**Usage:**
```bash
export VISUAL_CROSSING_API_KEY="your_api_key_here"
python debug_visual_crossing_alerts.py
```

**Menu Options:**
1. Test Visual Crossing alerts end-to-end (US + International)
2. Compare alert sources (NWS vs Visual Crossing)
3. Run international alerts test (dedicated script)
4. Run simple test (basic functionality)

### 2. `test_international_alerts.py` - Dedicated International Test
**New comprehensive international testing script**

This script specifically focuses on international locations to demonstrate Visual Crossing's global advantage:

**Features:**
- Tests 12+ international locations across all continents
- Compares NWS vs Visual Crossing coverage
- Shows detailed alert information when found
- Provides coverage statistics

**International Locations:**
- **Europe:** London, Amsterdam, Berlin
- **Asia-Pacific:** Tokyo, Sydney, Mumbai, Bangkok
- **Americas (non-US):** Toronto, Mexico City, São Paulo
- **Other:** Cairo, Cape Town

**Usage:**
```bash
export VISUAL_CROSSING_API_KEY="your_api_key_here"
python test_international_alerts.py
```

**Menu Options:**
1. Test international locations only
2. Compare US vs International coverage

### 3. `test_visual_crossing_alerts_simple.py` - Quick Test
**Updated with international locations**

Simple test that quickly checks 3 locations:
- Miami, FL (US)
- London, UK (International)
- Tokyo, Japan (International)

**Usage:**
```bash
export VISUAL_CROSSING_API_KEY="your_api_key_here"
python test_visual_crossing_alerts_simple.py
```

## Key Benefits of International Testing

### 1. **Global Coverage Verification**
- Confirms Visual Crossing works worldwide
- Tests locations where NWS cannot provide data
- Validates alert parsing for different regions

### 2. **Real-World Use Cases**
- European users get weather alerts for their locations
- Asian users receive typhoon and monsoon warnings
- Australian users get bushfire and storm alerts
- Canadian users receive winter weather warnings

### 3. **Accessibility Impact**
- Screen reader users worldwide can receive weather alerts
- No need to rely on local weather services that may not be accessible
- Consistent alert format regardless of location

## Expected Test Results

### For US Locations:
- **NWS:** ✅ Should work (when alerts are active)
- **Visual Crossing:** ✅ Should work (alternative source)
- **Comparison:** Both sources may have different alerts

### For International Locations:
- **NWS:** ❌ Expected to fail (US-only coverage)
- **Visual Crossing:** ✅ Should work (global coverage)
- **Result:** Visual Crossing is the only option

## Sample Test Output

```
[1/12] Testing: London, UK
Coordinates: 51.5074, -0.1278
------------------------------------------------------------
✓ API Response: Current=True, Forecast=True, Alerts=True
🚨 ALERTS FOUND: 2 active alert(s)
  Alert 1:
    Event: Wind Warning
    Severity: Moderate
    Headline: Strong winds expected across southern England
    Areas: Greater London, Surrey
    Expires: 2024-01-15 18:00

🔍 Comparison: Testing NWS for this location...
✓ Expected: NWS failed for international location (ApiClientError)
```

## Troubleshooting International Alerts

### Common Issues:

1. **No Alerts Found**
   - **Normal:** Many locations may not have active alerts
   - **Solution:** Test during active weather events or try multiple locations

2. **API Rate Limits**
   - **Cause:** Visual Crossing has usage limits
   - **Solution:** Space out requests, check your API quota

3. **Different Alert Formats**
   - **Cause:** International alerts may have different structures
   - **Solution:** Enhanced parsing handles multiple formats

4. **Time Zone Issues**
   - **Cause:** Alert times may be in different time zones
   - **Solution:** Times are parsed and displayed in local format

### Debugging Steps:

1. **Check API Key:** Ensure your Visual Crossing API key is valid
2. **Test Multiple Locations:** Some areas have more frequent alerts
3. **Check Logs:** Enable debug logging to see detailed information
4. **Compare with Local Sources:** Verify alerts match local weather services

## API Key Setup

Get your free Visual Crossing API key:
1. Visit: https://www.visualcrossing.com/weather-query-builder/
2. Sign up for a free account
3. Copy your API key
4. Set environment variable: `export VISUAL_CROSSING_API_KEY="your_key"`

Free accounts include 1000 weather records per day.

## Integration with AccessiWeather

The international alert testing validates that:

1. **Global Users Can Receive Alerts:** Users anywhere in the world can get weather notifications
2. **Consistent Experience:** Same notification system works for all locations
3. **Accessibility Maintained:** Screen reader compatibility preserved globally
4. **Fallback Strategy:** Visual Crossing provides coverage where NWS cannot

## Conclusion

The enhanced testing suite now comprehensively validates Visual Crossing's international weather alert capabilities, ensuring AccessiWeather can serve users worldwide with the same high-quality, accessible weather alert notifications that US users receive from the National Weather Service.

This global coverage is essential for AccessiWeather's mission to provide accessible weather information to all users, regardless of their location.
