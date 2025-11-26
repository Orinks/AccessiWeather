# Accessibility Testing Checklist - Forecast Navigation

This checklist covers manual testing for the heading-based forecast navigation feature.

## Prerequisites
- AccessiWeather installed and running
- At least one location added with weather data loaded
- Screen reader installed and active

---

## NVDA Testing (Windows)

### Heading Navigation
- [ ] Press `H` to navigate to next heading in forecast
- [ ] Press `Shift+H` to navigate to previous heading
- [ ] Verify each forecast day is announced as a heading (e.g., "heading level 2, Today")
- [ ] Verify day names are announced clearly (Today, Tonight, Monday, etc.)
- [ ] Verify you can navigate through all forecast days using H key

### Content Access
- [ ] After landing on a heading, press `Down Arrow` to read forecast content
- [ ] Verify temperature, conditions, and wind are readable after each heading
- [ ] Verify hourly forecast section has its own heading ("Next 6 Hours")

### Elements List
- [ ] Press `Insert+F7` to open Elements List
- [ ] Select "Headings" tab
- [ ] Verify all forecast days appear in the headings list
- [ ] Select a heading and press Enter to navigate to it

---

## JAWS Testing (Windows)

### Heading Navigation
- [ ] Press `H` to move to next heading
- [ ] Press `Shift+H` to move to previous heading
- [ ] Verify JAWS announces heading level (should be level 2)
- [ ] Verify day names are announced

### Quick Keys
- [ ] Press `Insert+F6` to open Headings List
- [ ] Verify forecast day headings appear in the list
- [ ] Navigate to a heading from the list

---

## Windows Narrator Testing

### Scan Mode Navigation
- [ ] Enable Scan Mode (Caps Lock + Space)
- [ ] Press `H` to navigate between headings
- [ ] Verify Narrator announces "heading level 2" for each forecast day
- [ ] Verify day names are spoken clearly

### Landmarks
- [ ] Press `D` to navigate by landmark/region
- [ ] Verify forecast section is identified as a region

---

## General Accessibility Checks

### Focus Management
- [ ] Tab navigation moves logically through the interface
- [ ] Focus is visible when navigating with keyboard
- [ ] No focus traps in the forecast area

### Content Updates
- [ ] After refreshing weather data, headings remain navigable
- [ ] Screen reader announces when weather data updates (if applicable)

### Empty States
- [ ] When no forecast data is available, a clear message is announced
- [ ] No broken headings or empty regions

---

## Test Results

| Screen Reader | Version | Pass/Fail | Notes |
|--------------|---------|-----------|-------|
| NVDA         |         |           |       |
| JAWS         |         |           |       |
| Narrator     |         |           |       |

**Tester:** _______________
**Date:** _______________
**App Version:** _______________
