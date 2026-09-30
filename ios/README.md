# AccessiWeather for iOS

A native SwiftUI port of AccessiWeather. VoiceOver is the primary interface: every
forecast row is a single element with expanded units, section headers work with the
rotor, and refresh completion is announced.

- iOS 17+, Swift 5.9, SwiftUI, Swift Concurrency. No third-party dependencies.
- Project lives in `ios/AccessiWeather/`. The Xcode project is generated with
  [XcodeGen](https://github.com/yonaskolb/XcodeGen) from `project.yml`; the generated
  `AccessiWeather.xcodeproj` is committed so XcodeGen is not required to build.

## Build

```bash
cd ios/AccessiWeather
xcodebuild -scheme AccessiWeather -destination 'platform=iOS Simulator,name=iPhone 16' build
```

Use whichever simulator you have installed; for example this machine only had an
iPhone 17 (iOS 26.5) simulator, so the verified command was:

```bash
xcodebuild -scheme AccessiWeather -destination 'platform=iOS Simulator,name=iPhone 17,OS=26.5' build
```

To run the accessibility UI tests (they walk every tab and assert that rows expose
sensible VoiceOver labels; add a saved location first for the live-data test):

```bash
xcodebuild -scheme AccessiWeather -destination 'platform=iOS Simulator,name=iPhone 17,OS=26.5' test
```

After editing `project.yml`, regenerate with `xcodegen generate` and commit both files.

## Layout

| Folder | Purpose |
|--------|---------|
| `App/` | `AccessiWeatherApp` entry point, `ContentView` tab bar, `AppModel` (selected location, current report, refresh, notifications) |
| `Models/` | `SavedLocation`, `WeatherReport`, `CurrentConditions`, `HourlyPeriod`, `DailyPeriod`, `WeatherAlert`, `AirQuality` |
| `Networking/` | `HTTPClient` (User-Agent `AccessiWeather-iOS (github.com/Orinks/AccessiWeather)`), `NWSClient`, `OpenMeteoClient`, `GeocodingClient` (Nominatim), `WeatherService` (source selection + 5-minute cache) |
| `Storage/` | `SettingsStore` (UserDefaults), `LocationStore` (JSON in Application Support), `KeychainStore` (API keys) |
| `Formatting/` | `WeatherFormatter`: compact visible strings plus spoken strings with expanded units |
| `Views/` | Weather, Alerts, Locations (+ Add Location sheet), Settings, shared views |
| `../AccessiWeatherUITests/` | XCUITest accessibility audit |

Data sources: NWS (`api.weather.gov`) for US coordinates, Open-Meteo elsewhere, with
Open-Meteo filling in UV, sunrise/sunset and air quality for US locations. Pirate
Weather can be selected and its key stored, but fetching from it is not implemented yet.

## Desktop features deliberately dropped or replaced

| Desktop feature | iOS decision |
|-----------------|--------------|
| System tray / taskbar icon text, minimize to tray | Dropped. iOS has no tray; the app is a normal foreground app. |
| Start on login | Dropped. Not a concept on iOS. |
| Global hotkeys | Dropped. iOS has no global hotkeys; VoiceOver gestures and the rotor cover navigation. |
| Portable mode | Dropped. iOS sandboxes app data automatically. |
| Import / export backup | Dropped for now. iCloud backup covers the app container; a share-sheet export could be added later. |
| Auto-update channel and update checks | Replaced by the App Store / TestFlight. |
| Sound packs and Soundpack Manager | Replaced by system notification sounds via `UNUserNotificationCenter`. |
| GitHub backend / pack submission | Dropped along with sound packs. |
| Debug menu | Dropped. Use Xcode and Console.app. |
| Single-instance logic | Dropped. iOS runs one instance. |
| NOAA Weather Radio streaming | Future work. |
| Weather Assistant chat and AI Explain Conditions | Explain Conditions shows only when an OpenRouter key is saved and is a placeholder; chat is future work. |
| Aviation weather, Weather History, Precipitation Timeline, Event Center | Not in the first version. |

## Known gaps

- Pirate Weather fetching, AirNow and AVWX are not wired up; keys can be stored in the Keychain.
- Alert notifications are scheduled locally when a refresh finds new alerts; there is no background refresh yet.
- No widgets or Live Activities yet.
