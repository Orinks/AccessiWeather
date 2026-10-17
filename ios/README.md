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
| `Audio/` | `SoundPack` (reads the desktop `pack.json` format), `SoundManager` (AVAudioPlayer cues, notification sound install) |
| `Radio/` | `WeatherIndexClient` (`api.wxindex.org/v1/stations/all`), `RadioStationDirectory` (live list with disk cache and bundled fallback), `RadioStation` + `RadioStationDatabase` (nearest-station search), `RadioPlayer` (AVPlayer streaming, lock screen, interruptions) |
| `Resources/` | `SoundPacks/<pack>/pack.json` plus clips (folder reference), `noaa_radio_stations.json` |
| `Views/` | Weather, Alerts, Locations (+ Add Location sheet), Settings (+ Sound Events), Radio, shared views |
| `../AccessiWeatherUITests/` | XCUITest accessibility audit |

Data sources: NWS (`api.weather.gov`) for US coordinates, Open-Meteo elsewhere, with
Open-Meteo filling in UV, sunrise/sunset and air quality for US locations. Pirate
Weather can be selected and its key stored, but fetching from it is not implemented yet.

## Sound packs

Packs live in `AccessiWeather/Resources/SoundPacks/<pack>/` and use the same `pack.json` as
the desktop app (`name`, `author`, `description`, `version`, `sounds` map of event name to
file). AVAudioPlayer cannot decode Ogg Vorbis, so the desktop `default` pack's `.ogg` clips
are committed here as `.caf` copies made with
`ffmpeg -i in.ogg -c:a pcm_s16le out.caf`. The desktop `nature` pack is not bundled because
its `.wav` files in the repo are empty placeholders.

In-app cues use the ambient audio session category with mixing enabled, so they play under
VoiceOver speech and respect the silent switch. Events mirror the desktop
`muted_sound_events` setting: `data_updated` (muted by default, like the desktop),
`fetch_error`, `discussion_update`, `alert_updated`, and the alert severities `extreme`,
`severe`, `moderate`, `minor`, `unknown`. Settings > Sounds has the on/off toggle, one row
per pack with a Preview button, and a Sound Events screen with a toggle per event.

Alert notifications use `UNNotificationSound(named:)`. On launch `SoundManager` copies each
pack's alert clips into `Library/Sounds`, which is where iOS looks for custom notification
sounds. iOS only plays custom notification clips shorter than 30 seconds; longer clips are
skipped and the system default sound is used instead. Pack submission and the GitHub
soundpack backend are not ported.

## NOAA Weather Radio

The station list and stream URLs come from the WeatherIndex directory
(`https://api.wxindex.org/v1/stations/all`), the same source the desktop app uses, so new
and retired transmitters and changed relay URLs show up without an app update. Stations
WeatherIndex marks `OUT OF SERVICE` are hidden. The directory is refreshed when the Radio
screen opens (at most every 30 minutes, retrying 5 minutes after a failure) or via the Refresh
Stations button / pull-to-refresh, and the last download is cached in `Caches/AccessiWeather/
noaa_radio_stations.json`. If WeatherIndex is unreachable and there is no cache, the bundled
`Resources/noaa_radio_stations.json` snapshot is used and the footer says so. Every station
still falls back to `broadcastify.cdnstream1.com/noaa/<call sign>`. The Radio screen opens from the
Weather tab toolbar or the "NOAA Weather Radio" row and lists the eight stations nearest the
selected location with call sign, frequency and distance. Tapping a station streams it with
`AVPlayer` (playback category, `audio` background mode, so it keeps playing when the screen
locks) and tries each stream URL in turn before reporting "Stream unavailable". Lock Screen
and headphone controls work through `MPRemoteCommandCenter`; `MPNowPlayingInfoCenter` shows
the station name. Interruptions pause and resume, and unplugging headphones stops playback.
Play, stop, resume and error states are announced to VoiceOver. The desktop auto-tune-on-alert
feature is not ported. Known gap: in the iOS Simulator the KIH28 relays reached "Stream
unavailable" even though `curl` returned `200 audio/mpeg` (the WeatherUSA relay fails the TLS
handshake with `NSURLErrorDomain -1200`); playback on a physical device has not been verified.

## Desktop features deliberately dropped or replaced

| Desktop feature | iOS decision |
|-----------------|--------------|
| System tray / taskbar icon text, minimize to tray | Dropped. iOS has no tray; the app is a normal foreground app. |
| Start on login | Dropped. Not a concept on iOS. |
| Global hotkeys | Dropped. iOS has no global hotkeys; VoiceOver gestures and the rotor cover navigation. |
| Portable mode | Dropped. iOS sandboxes app data automatically. |
| Import / export backup | Dropped for now. iCloud backup covers the app container; a share-sheet export could be added later. |
| Auto-update channel and update checks | Replaced by the App Store / TestFlight. |
| Soundpack Manager (install/create packs) | Only bundled packs are available; see Sound packs above. |
| GitHub backend / pack submission | Dropped. |
| Debug menu | Dropped. Use Xcode and Console.app. |
| Single-instance logic | Dropped. iOS runs one instance. |
| NOAA Weather Radio auto-tune on alert | Not ported; streaming itself is available from the Weather tab. |
| Weather Assistant chat and AI Explain Conditions | Explain Conditions shows only when an OpenRouter key is saved and is a placeholder; chat is future work. |
| Aviation weather, Weather History, Precipitation Timeline, Event Center | Not in the first version. |

## Known gaps

- Pirate Weather fetching, AirNow and AVWX are not wired up; keys can be stored in the Keychain.
- Alert notifications are scheduled locally when a refresh finds new alerts; there is no background refresh yet.
- No widgets or Live Activities yet.
- Radio streams come from volunteer relays and some stations are offline; the app tries every known URL before giving up.
