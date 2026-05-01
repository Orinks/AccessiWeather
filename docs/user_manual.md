# AccessiWeather User Manual

## 1. Introduction

AccessiWeather is an accessible desktop weather application for Windows, macOS, and Linux. It is designed to work well with screen readers, keyboard navigation, desktop notifications, and clear text layouts.

Instead of mixing everything into one long report, AccessiWeather separates weather into practical sections:

- Location selector
- Current Conditions
- Hourly Forecast / near-term
- Daily Forecast
- Weather Alerts
- Event Center

The app can also provide forecast discussions, air quality details, UV details, aviation weather, NOAA Weather Radio access, AI weather explanations, Weather Assistant chat, and optional notification sounds.

This manual explains how to install the app, add locations, read the weather, choose weather sources, manage alerts and notifications, and adjust settings.

## 2. Installing and starting AccessiWeather

### Downloading a build

Prebuilt downloads are available from the [AccessiWeather page](https://orinks.net/accessiweather) and the [GitHub releases page](https://github.com/Orinks/AccessiWeather/releases).

Typical download options are:

- Windows: setup installer or portable ZIP
- macOS: DMG

## 3. First-time setup

When you start AccessiWeather for the first time, it shows a short onboarding wizard.

The wizard walks you through these steps:

1. Add your first location, or skip it for now.
2. Enter an OpenRouter API key if you want AI features.
3. Enter a Pirate Weather API key if you want that provider.

At the end, AccessiWeather shows a readiness summary.

You can safely skip any optional key step. The app works without paid services, and you can add keys later in Settings. When a provider needs a key, AccessiWeather includes a button that takes you to the place to get one.

### Recommended first setup

For the smoothest first experience, do the following:

1. Add at least one location.
2. Leave the weather source set to Automatic unless you have a reason to force one provider.
3. Refresh weather if the app has not already done so.
4. Open Settings only after you have seen the basic forecast once.

## 4. Everyday tasks

### Add your first location

To add a location:

1. Open Location > Add Location, or press Ctrl+L.
2. Enter a friendly name in Location Name.
3. Search by city name or ZIP or postal code.
4. Select one result from the results list.
5. Save the location.

Important things to know:

- The name must be unique in your saved list.
- You cannot save the location until you choose a search result.
- Double-clicking a search result also saves it.

### Switch locations

Use the location selector near the top of the main window to switch between saved places.

When you switch locations, AccessiWeather may show cached weather first and then refresh in the background.

### Refresh weather now

To refresh the selected location immediately:

- press F5
- press Ctrl+R
- choose View > Refresh
- use the Refresh button in the main window

### Remove a location

To remove the current location:

- choose Location > Remove Location
- or press Ctrl+D
- or use the Remove button

AccessiWeather will not let you remove your last remaining location.

### Open the forecast discussion

To open a forecast discussion:

- use the Discussion button
- or choose View > Forecast Discussion

For normal US locations, this opens the local NWS Area Forecast Discussion, often called the AFD.

An AFD is a text product written by National Weather Service forecasters. It explains what they think will happen, why they think it, and how confident they are. This is different from the regular forecast, which mainly tells you the expected result.

Use this when:

- you want to know why the forecast might change later
- storm timing looks uncertain and you want the forecaster's reasoning
- snow, sleet, freezing rain, or rain could change over from one to another
- severe weather may develop and you want more detail than a short alert headline gives
- you trust hearing a local forecaster explain the setup in plain text

This is helpful if the regular forecast feels too short. The AFD often explains whether rain is likely to arrive before or after your commute, why temperatures may be tricky near freezing, whether thunderstorm coverage is uncertain, and how confident forecasters are in the next update.

If Nationwide is selected, AccessiWeather opens national discussion products instead.

Leave this alone if you only want a quick answer such as the current temperature, today's high, or whether an alert is active. The regular forecast sections are faster for that.

If your current source or location does not support forecast discussions, the discussion may be unavailable.

### View alert details

To read the full text of an alert:

1. Move to the Weather Alerts section.
2. Select the alert you want.
3. Choose View Alert Details, or press Enter or Space on the selected alert.

### Open Settings

To open Settings:

- press Ctrl+S
- choose File > Settings
- use the Settings button

## 5. Understanding the main window

The main window is designed for quick keyboard and screen-reader use.

### Quick-action buttons

The button row provides common actions without requiring the menu bar:

- Add Location
- Remove Location
- Refresh Weather
- Explain Weather
- Forecast Discussion
- Settings
- View Alert Details

### Top-level navigation

AccessiWeather supports two top-level navigation patterns in the main window:

- F6 cycles through the visible top-level sections in order
- Ctrl+1 through Ctrl+5 jump directly to the main forecast sections

The current top-level order is:

1. Location selector
2. Current Conditions
3. Hourly Forecast / near-term
4. Daily Forecast
5. Weather Alerts
6. Event Center

The direct-jump shortcuts map like this:

- Ctrl+1: Current Conditions
- Ctrl+2: Hourly Forecast / near-term
- Ctrl+3: Daily Forecast
- Ctrl+4: Weather Alerts
- Ctrl+5: Event Center

If the Event Center is hidden from the View menu, F6 skips it and Ctrl+5 does nothing until you show it again.

### Location selector

The location selector chooses which saved place is currently shown.

### Current Conditions

This section shows what the weather is doing right now, or as close to right now as the source can provide.

This matters separately from the forecast because the forecast tells you what is expected, while Current Conditions tells you what is already happening. That difference matters when you need to make an immediate decision.

Use this when:

- you are deciding what to wear before leaving the house right now
- you want to know whether the wind is already strong enough to affect walking, transit, or mobility aids
- you need to know whether visibility is poor before going out
- you are checking whether the temperature already dropped below freezing even if the forecast only said it might happen later
- you want to know whether rain has started yet instead of whether it is expected later today

This section can help answer practical questions such as:

- Do I need a heavier coat right now?
- Is it already windy enough that I should expect a harder walk or wait for a ride?
- Is the air quality poor enough that I should limit time outside?
- Is the UV level high enough that I should prepare before going out?

- temperature
- feels-like temperature
- wind
- humidity
- dew point
- visibility
- UV index
- pressure trend
- air quality
- pollen or impact summaries when available

If Pirate Weather minutely precipitation data is available, this section can also mention near-term precipitation start or stop timing.

This is helpful if you need a quick answer before stepping outside and do not want to read several forecast periods first.

Leave this alone if you are planning for tomorrow or the weekend. In that case, the forecast sections are usually more useful.

### Hourly Forecast / near-term

This section shows the short-range hourly forecast. You can choose how many hours appear in Settings > Display.

When AccessiWeather has enough useful near-term data, this section can begin with a one-sentence mobility briefing for roughly the next 90 minutes. The mobility briefing does not replace the hourly outlook summary. It appears above the hourly outlook when available.

Use this when:

- you need timing, not just a general day summary
- you are deciding when to leave, when to return home, or when to fit in a trip outside
- you want to know whether the coldest, windiest, wettest, or iciest part of the day lines up with your plans

Hourly Forecast is usually the better choice for questions like "Will the rain start before my bus trip?" "Will the temperature still be above freezing at 7 PM?" or "Does the wind ease later tonight?"

This is helpful if one part of the day is much different from another. It gives the timing that Daily Forecast intentionally smooths out.

Leave this alone if you only need the big picture for the next several days. In that case, Daily Forecast is faster to read.

### Daily Forecast

This section shows the multi-day forecast. The number of days depends on your Display settings and on what the source can provide.

Use this when:

- you are planning the next few days instead of the next few hours
- you want to compare one day with another before scheduling errands, travel, work, or outdoor time
- you care more about the overall shape of the week than exact hour-by-hour timing

Daily Forecast is usually the better choice for questions like "Which day looks driest?" "Will the weekend be colder than today?" or "Is there a better day for a medical appointment, grocery trip, or outdoor event?"

This is helpful if you do not want to read 24 or more hourly entries. It summarizes the larger pattern.

Leave this alone if the exact timing matters, such as whether rain begins before 3 PM or whether winds ease after sunset. For those questions, use Hourly Forecast / near-term.

### Event Center

The Event Center is a reviewable text history of user-facing weather events and summaries.

On the current release, it is intended for:

- spoken or surfaced briefings
- reviewable notification/event text

Entries are appended as plain timestamped lines. Examples include:

- brief mobility summaries
- discussion-update summaries
- other user-facing event text that AccessiWeather surfaces for review

The Event Center is part of the main window, not a separate dialog. It is visible by default and can be shown or hidden from View > Event Center.

When it is visible:

- F6 includes it in top-level cycling
- Ctrl+5 jumps to it

When it is hidden:

- F6 skips it
- Ctrl+5 does nothing
- re-enable it from View > Event Center when you want it back

### Weather Alerts

This section lists active alerts for the selected location.

Think of this section as your current hazard list. It tells you what warnings, watches, advisories, or similar urgent products are active right now for that place.

Use this when:

- you want to confirm whether an alert is active right now, even if you dismissed the earlier notification
- you need the full alert title and can open the details for instructions, timing, and affected areas
- you are checking whether a situation became more serious, was extended, or was cancelled

This section is different from notifications. Notifications are the popups or sounds AccessiWeather sends when something changes. The Weather Alerts section is the place where you can review the alerts themselves after the popup is gone.

This is helpful if you want to double-check what kind of hazard is active before heading out or telling someone else about it.

When alerts change between refreshes, you may hear or read labels such as:

- New
- Updated
- Escalated
- Extended

Cancelled alerts may still trigger notifications even after they leave the active list.

Leave this alone if there are no active alerts and you only want routine forecast information. The forecast sections remain the main place for everyday planning.

## 6. Weather sources and Automatic mode

AccessiWeather can use multiple weather providers. You can force a single provider, but most users will get the best results from Automatic mode.

### Weather providers at a glance

#### National Weather Service (NWS)

Best for:

- US forecasts
- US alerts
- US forecast discussions
- NOAA Weather Radio features

Important limits:

- US only
- not available for international locations

#### Open-Meteo

Best for:

- global forecast coverage
- no-key setup
- strong baseline forecast coverage

Important limits:

- no weather alerts in AccessiWeather
- no forecast discussion support

#### Pirate Weather

Best for:

- global forecast coverage with an API key
- worldwide alert coverage in many regions
- minutely precipitation guidance
- Dark Sky-style summary text

Important limits:

- requires an API key
- alerts may be broader than local US NWS targeting
- minutely precipitation is only available where Pirate Weather provides it

### What Automatic mode means now

Automatic mode is the default weather-source choice.

Its default behavior is fusion-first using the Max coverage budget. In plain language, that means AccessiWeather tries every enabled source it can use for your region, then merges the results so one provider can fill gaps left by another.

Automatic mode is not limited to one built-in fetch order. It follows the source order you save in the Automatic mode configuration.

Automatic mode also keeps separate source lists for:

- US locations
- international locations

This lets you choose a different preferred order for domestic and international use.

### Automatic mode budgets

AccessiWeather provides three Automatic mode API budget choices.

#### Max coverage

This is the default.

Use this when:

- you want the richest merged result
- you want Automatic mode to behave in its full fusion-first form
- you want the best chance of filling forecast gaps from multiple sources

What it does:

- fans out to every enabled source that is available for the current location
- merges current conditions, daily forecast, and hourly forecast from those results
- uses your saved source order when deciding how to merge overlapping data

#### Economy

This is an opt-in reduced-call mode.

Use this when:

- you want to minimize API usage
- you are trying to stay within optional-provider quotas
- you prefer a simpler, lower-call Automatic mode

What it does:

- starts with your first enabled source for the region
- only adds limited fallback behavior when needed
- keeps call volume lower than Max coverage

#### Balanced

This is also an opt-in reduced-call mode.

Use this when:

- you want fewer API calls than Max coverage
- but you still want one useful fallback in more situations than Economy

What it does:

- starts with your first enabled source for the region
- allows one additional fallback source when Automatic mode needs it
- offers a middle ground between Economy and Max coverage

### Separate US and international source lists

Automatic mode uses separate saved source lists for US and international locations.

Default order:

- US: NWS, Open-Meteo, Pirate Weather
- International: Open-Meteo, Pirate Weather

You can change these lists in Settings > Data Sources > Configure automatic mode budget and sources.

The staged fetch order follows the source order you save.

### Alerts in Automatic mode

Automatic mode does not treat every alert source equally.

#### US locations

For US locations, NWS alerts are authoritative when NWS is available.

That means:

- AccessiWeather uses NWS alerts as the official alert feed in Automatic mode
- Pirate Weather alerts are not used as an equal co-authority for US alerts
- the Alert Area setting applies to NWS-style US alert targeting

#### International locations

For international locations:

- NWS alerts do not apply
- Pirate Weather alerts are preferred when available

### Forecast discussion behavior in Automatic mode

Forecast discussions in AccessiWeather come from NWS.

That means:

- US users can open discussions when NWS is part of the active path
- Nationwide can open national discussion products
- if Automatic mode does not use NWS for the current weather path, forecast discussion may be unavailable
- Open-Meteo and Pirate Weather do not provide forecast discussions in AccessiWeather

Use this when you want the forecaster's reasoning rather than only the final forecast numbers. This is especially useful when thunderstorm timing is uncertain, when a snow or ice changeover is possible, or when you want to know how confident the local office is.

Leave this alone if you mainly want a quick yes-or-no answer such as whether rain is in today's forecast. The regular forecast sections are faster.

### Minutely precipitation

Minutely precipitation guidance depends on Pirate Weather.

When Pirate Weather minutely data is available, AccessiWeather can:

- include near-term precipitation timing in current conditions
- notify you when precipitation is expected to start soon
- notify you when precipitation is expected to stop soon

Use this when the next 5 to 60 minutes matters more than the rest of the day, such as deciding whether to leave now, wait a few minutes, or finish a short trip before rain starts.

This is helpful if you do not need a long forecast and only want to know whether precipitation is about to begin or end.

If Pirate Weather is not configured, or if minutely data is unavailable for the location, those features will not appear.

## 7. Alerts and notifications

Alerts and notifications are related, but they are not the same thing.

- Alerts are the weather hazards AccessiWeather receives from a source.
- Notifications are the desktop popups and optional sounds AccessiWeather sends when something changes.

### Standard alert monitoring

This is the basic alert system. You can choose whether AccessiWeather should:

- monitor alerts at all
- send alert notifications
- open alert details immediately while the app is running

Use this when you want AccessiWeather to act as an ongoing safety tool instead of only a forecast reader.

This is helpful if you may not be checking the app constantly. Notifications let the app bring urgent changes to you.

Leave this alone if the defaults already give you the right level of interruption. Most users do not need to change all three options.

### Alert area

For NWS-based US alerts, the Alert Area setting controls how broad the targeting should be.

Choices are:

- County: recommended for most users
- Point: exact coordinate, but may miss nearby alerts
- Zone: somewhat broader than county
- State: broadest and noisiest

Use smaller areas when you want fewer notifications. Use broader areas when you do not want to miss alerts that affect a wider region.

Use County if you want a practical balance and do not want to fine-tune anything. That is the best starting point for most users.

Use Point when you live near a county line and prefer highly local alerts, but understand that you may miss something that affects nearby travel.

Use Zone or State when your plans regularly take you across a larger area, or when you would rather hear some extra alerts than risk missing one that matters.

Leave this alone if you are not sure. County is usually the safest default choice.

### Severity filters

You can choose which alert severities are allowed to notify you:

- Extreme
- Severe
- Moderate
- Minor
- Uncategorized

A severity being turned off means the alert can still exist in the weather data, but AccessiWeather will not notify you for that level.

Use this when you want to hear about the most serious hazards but not every lower-level headline.

This is helpful if your area gets frequent advisories that are useful to read when you open the app, but not important enough to interrupt you with a popup or sound.

Leave this alone if you are new to the app and want the broadest awareness first. You can narrow it later after you learn how noisy your local alerts are.

### Extra weather event notifications

In addition to standard alerts, AccessiWeather can notify you about:

- Area Forecast Discussion updates for NWS US locations
- minutely precipitation start soon from Pirate Weather
- minutely precipitation stop soon from Pirate Weather

These are optional and should be turned on only if you want those extra updates.

Use discussion update notifications when you follow developing weather closely and want to know when local forecaster reasoning changes.

Use minutely precipitation notifications when short outdoor trips matter and a few minutes of notice would help.

Leave these alone if you want the app to notify you only for formal alerts. That simpler setup is usually enough for everyday use.

### Cooldowns and notification limits

Cooldown settings help prevent repeated notifications from becoming overwhelming.

In user terms:

- global cooldown is the minimum time between any alert notifications
- per-alert cooldown is how long AccessiWeather waits before repeating the same alert
- freshness window limits notifications to recently issued alerts
- maximum notifications per hour puts an upper cap on how noisy the app can be

Use these controls when you want fewer repeat notifications without turning alerts off completely.

This is helpful if you rely on screen reader speech or audio cues and do not want several related notifications interrupting other work.

Leave this alone if the default notification pace already feels reasonable.

## 8. Settings reference

The Settings dialog is organized in this order:

1. General
2. Display
3. Alerts
4. Audio
5. Data Sources
6. AI
7. Updates
8. Advanced

Start with the defaults if you are new to AccessiWeather. The default setup is designed to work without any API keys:

- Automatic weather source is usually the best starting point
- Open-Meteo gives no-key global forecast coverage
- NWS adds US alerts, discussions, and NOAA features when you are in the US
- you only need optional keys if you want extra provider features or AI tools

The most useful way to think about Settings is this:

- change something only when you have a reason
- leave it alone when the app is already giving you the information you need
- add optional services gradually instead of all at once

The usual progression is:

1. Start with the no-key default experience.
2. Add Pirate Weather if you want worldwide alerts in many regions or minutely precipitation timing.
3. Add OpenRouter if you want AI explanations and Weather Assistant.
4. Add an AVWX key only if you use Aviation Weather and want better international aviation decoding.

### General

Use the General tab for everyday app behavior.

Most users will visit this tab first. It controls how often the app refreshes and a few convenience features. The defaults are usually fine if you simply want AccessiWeather to stay up to date in the background.

#### Refresh weather every (minutes)

Controls how often AccessiWeather refreshes weather automatically.

Use a shorter interval when you want faster background updates. This is helpful if you follow changing conditions during the day.

Use a longer interval when you prefer less network activity or when you mostly refresh by hand.

Leave this alone if the app already feels current enough. Many users never need to adjust it.

#### Show the Nationwide location when a supported data source is selected

Shows or hides the built-in Nationwide location.

Nationwide is available when your weather source is set to Automatic or NWS.

Use this when you want quick access to national discussion products or broad national awareness during major weather setups.

This is helpful if you track hurricanes, winter storms, or other widespread events that matter beyond one city.

Leave this alone if you only care about your saved local locations.

#### Tray icon text options

The General tab also includes tray text controls:

- Show weather text on the tray icon
- Update tray text as conditions change
- Current tray text format
- Edit tray text format

Use these options when you want the notification-area icon to show a short live weather summary instead of a plain app name.

This is helpful if you keep AccessiWeather running all day and want a quick status check without opening the full window.

Leave this alone if you do not use the tray area or if extra text there would be distracting.

### Display

Use the Display tab to control units, detail level, and forecast layout.

This tab matters most if the weather is readable but not yet comfortable for you. It is where you decide how much detail AccessiWeather speaks or shows at once.

#### Temperature units

Choices are:

- Auto based on location
- Imperial (Fahrenheit)
- Metric (Celsius)
- Both

You can also choose to show values as whole numbers when possible.

Use Auto if you want the app to follow the location's usual unit system.

Use Both if you move between unit systems often, compare forecasts from different regions, or simply want extra certainty.

Use whole numbers if decimal values feel noisy and do not help your decisions.

Leave this alone if the temperature already makes sense to you quickly.

#### Forecast range

The Display tab lets you choose:

- Daily forecast range: 3, 5, 7, 10, 14, or 15 days
- Hourly forecast range: 1 to 168 hours

Use a shorter range if you want faster, lighter reading with less clutter.

Use a longer range if you routinely plan travel, work shifts, or appointments several days ahead.

Leave this alone if the current amount of forecast detail already fits how you use the app.

#### Extra weather details

You can turn these details on or off:

- dew point
- visibility
- UV index
- pressure trend
- impact summaries for outdoor, driving, and allergy conditions

Use these options when a detail changes real decisions for you.

Examples:

- keep visibility on if fog, smoke, or heavy rain affects travel confidence
- keep UV on if sun exposure matters to your routine
- keep pressure trend on if you follow fast-changing weather closely
- keep impact summaries on if you want a more practical readout instead of raw numbers alone

Leave details off if they add noise and you rarely act on them.

#### Time display

Time controls include:

- whether forecast times follow the location timezone or your own local timezone
- whether times are shown as local only, UTC only, or both
- 12-hour time format
- timezone abbreviations

Use location timezone when you care about the weather where the place actually is, such as for travel or family in another region.

Use your own local timezone when you want all times translated into the way you think about your day.

Leave this alone if you mainly check nearby locations in the same timezone.

#### Reading priority

You can choose:

- Minimal verbosity
- Standard verbosity
- Detailed verbosity
- Automatically prioritize severe weather details

Use these controls to make the forecast shorter or more detailed.

Minimal verbosity is helpful if you want the fastest possible readout.

Detailed verbosity is helpful if you do not want to open extra windows just to get a fuller picture.

Automatically prioritize severe weather details is helpful if you want hazardous conditions moved closer to the front when they matter.

Leave this alone if Standard verbosity already feels balanced.

### Alerts

Use the Alerts tab to control alert handling, event notifications, and rate limiting.

This tab matters most for users who want AccessiWeather to actively interrupt them when conditions change. If you mostly open the app manually and check alerts yourself, the defaults are often enough.

#### Alert delivery

Controls include:

- Monitor weather alerts
- Send alert notifications
- Open alert details immediately while AccessiWeather is running

Change these if you want more or less interruption.

Opening alert details immediately can be helpful if you want the full instructions as soon as something urgent appears.

Leave this alone if simple popup notifications already work well for you.

#### Coverage and severity

Controls include:

- Alert Area
- Extreme severity alerts
- Severe severity alerts
- Moderate severity alerts
- Minor severity alerts
- Uncategorized alerts

Change these if your area is too noisy or too quiet.

Most users should start with the defaults, live with them for a few days, and only then decide whether to narrow or widen coverage.

#### Extra weather event notifications

Controls include:

- discussion update notifications
- severe risk change notifications
- minutely precipitation start notifications
- minutely precipitation stop notifications

Change these if formal alerts are not enough for your needs.

Leave them off if you want a simpler alert experience.

#### Rate limiting and advanced timing

Controls include:

- Maximum notifications per hour
- Advanced timing dialog for global cooldown, per-alert cooldown, and freshness window

Use these controls when you want to keep notifications useful without letting them repeat too often.

This is especially helpful if you use speech output and repeated interruptions are frustrating.

Leave this alone unless you have already noticed too many repeat notifications.

### Audio

Use the Audio tab to control sounds.

Use this tab if audio cues help you notice weather changes without reading the screen. If you prefer silence and rely on screen-reader speech or visual notifications, the defaults may already be right.

#### Playback

Controls include:

- Play notification sounds
- Sound pack
- Play sample sound
- Manage sound packs

Turn sounds on if you want an audible cue for important weather events.

Manage sound packs if the default sounds are hard to distinguish or simply not comfortable for you.

Leave sounds off if you work in a quiet setting or already get enough feedback from speech and popups.

#### When sounds play

Audio also includes event-sound controls so you can decide which event types are allowed to make noise.

Use this when:

- you want sounds for major alerts but not for routine updates
- you want to keep audio on without making every event noisy

Leave this alone if the default event sounds already match how urgent you want the app to feel.

### Data Sources

Use the Data Sources tab to choose the weather provider and configure Automatic mode.

For most users, this tab is best approached in stages. First, leave the source on Automatic and use the app with no keys. Only come back here when you know what is missing for you.

#### Weather source

Choices are:

- Automatic
- National Weather Service
- Open-Meteo
- Pirate Weather

Choose Automatic when you want merged results and source fallbacks. This is the best default for most people.

Choose a single source when you want predictable provider-specific behavior, such as testing one provider or preferring one provider's style.

Leave this alone if the app is already giving you reliable weather. Automatic is usually the right answer.

#### Automatic mode summary and configuration

The Data Sources tab shows a plain-language summary of your current Automatic mode settings, including:

- Automatic mode budget
- US automatic sources
- International automatic sources
- NWS station strategy

Use Configure automatic mode budget and sources to change:

- Max coverage, Economy, or Balanced
- separate US automatic source order
- separate international automatic source order
- the station strategy used when NWS chooses a current-conditions station

Change Automatic mode only if you have a clear reason, such as reducing API use, preferring one provider's data first, or keeping different priorities for US and international travel.

Leave this alone if you do not have optional API keys yet. The default configuration is designed to work well without them.

#### NWS station strategy

The available strategies are:

- Hybrid default
- Nearest station
- Major airport preferred
- Freshest observation

Use this when you want to influence which NWS observation station is preferred for current conditions.

This is helpful if the default station does not match the kind of location you care about. For example, an airport may read differently from a hilltop, coastal area, or smaller local station.

Leave this alone if current conditions already sound reasonable for your area.

#### Provider API keys

Start here with no keys unless you already know you need more. AccessiWeather works without provider keys.

The Data Sources tab includes API key fields and validation actions for:

- Pirate Weather

Each provider includes:

- an API key field
- a button to get a key
- a button to validate the key

Pirate Weather is the optional weather-provider key worth adding. Use it when you want worldwide alert coverage in many regions, minutely precipitation timing, moon phase, or Dark Sky-style summary text. This can be worth it if short-term rain timing matters to you or if you need alerts outside the US.

Leave the field blank if the default no-key setup already covers your needs. Many users never need a provider key.

Stored keys remain in secure storage unless you explicitly export them.

### AI

Use the AI tab if you want Explain Weather or Weather Assistant.

This tab is completely optional. If you do not want AI features, you can ignore it and still use the rest of AccessiWeather normally.

#### OpenRouter access

Controls include:

- OpenRouter API key
- a button to get a key
- Validate OpenRouter key

OpenRouter is worth adding only if you want AI help with understanding the weather.

Use it when you want a plain-language explanation, practical advice, or the ability to ask follow-up questions about the current conditions and forecast.

Leave it blank if the built-in forecast text already gives you what you need.

#### Model and explanation style

Controls include:

- model preference
- Browse OpenRouter models
- explanation style: brief, standard, or detailed

Use brief if you want fast summaries.

Use detailed if you want more explanation, more context, and more reasoning.

Leave the model choice alone unless you notice quality, speed, or availability issues.

#### Custom prompts

Optional fields include:

- custom system prompt
- custom instructions
- Reset prompt to default

Leave these blank unless you want to change the AI's tone or focus.

Most users should never need to edit prompts.

### Updates

Use the Updates tab to control release checks.

Most users should stay on Stable and leave automatic checking on.

Controls include:

- Check for updates automatically
- Release channel: Stable or Development
- Check every (hours)
- Check for updates now

Use Stable for everyday use. Use Development only if you want newer changes sooner and are comfortable with more risk.

Leave this alone if you simply want the app to keep itself reasonably current.

### Advanced

Use the Advanced tab for startup behavior, backup tools, file locations, and reset actions.

This tab is mainly for users who want tighter control, are moving to another machine, or are troubleshooting. If the app is working well, you may rarely need it.

#### Startup and window behavior

Controls include:

- Minimize to the notification area when closing
- Start minimized to the notification area
- Launch automatically at startup
- Enable weather history comparisons

Change these if you want AccessiWeather to behave more like a background utility and less like a window you open manually.

Leave these alone if you prefer starting the app only when you need it.

#### Backup and transfer

Tools include:

- Export settings
- Import settings
- Export API keys (encrypted)
- Import API keys (encrypted)

This is the place to move settings between machines and to transfer API keys securely.

Use this when setting up a second computer or when you want to move your settings securely.

#### Folders and files

Tools include:

- Open current config folder
- Open sound packs folder

Use these tools when you need to inspect or back up AccessiWeather files.

Leave this alone unless you are troubleshooting or intentionally managing files yourself.

#### Reset and maintenance

Tools include:

- Reset settings to defaults
- Reset all app data (settings, locations, caches)

Reset settings to defaults is useful when you want to keep your saved locations but undo a lot of option changes.

Reset all app data is a major cleanup action. Use it only when normal troubleshooting has not solved the problem.

If you use Aviation Weather often, the optional AVWX key is only worth adding if you want better decoded international aviation weather. AccessiWeather includes a button that takes you to the place to get that key.

## 9. Keyboard shortcuts

These shortcuts are available in the current app:

- F5 or Ctrl+R: Refresh weather
- Ctrl+L: Add location
- Ctrl+D: Remove location
- Ctrl+S: Open Settings
- Ctrl+H: Open Weather History
- Ctrl+E: Explain Weather
- Ctrl+T: Open Weather Assistant
- Ctrl+Shift+R: Open NOAA Weather Radio
- Ctrl+Q: Quit

## 10. Troubleshooting

### Problem: No weather data appears

What it usually means:

- the selected source failed
- your network connection is unavailable
- the location has not refreshed yet
- an API-key-based source is selected without a working key

What to try:

1. Press F5 to refresh.
2. Switch the weather source to Automatic.
3. Confirm the location is valid and still selected.
4. If using Pirate Weather directly, validate the API key in Settings > Data Sources.
5. Try another saved location to see whether the issue is location-specific.

### Problem: Alerts are missing or seem different between sources

What it usually means:

- different providers do not offer the same alert coverage
- US alerts and international alerts follow different authority rules
- your Alert Area or severity filters are too narrow

What to try:

1. Check whether the location is in the US or outside it.
2. For US locations, remember that NWS is the authoritative alert source in Automatic mode.
3. For international locations, add a Pirate Weather key if you want broader alert coverage.
4. Review Alert Area and severity settings in Settings > Alerts.
5. Make sure alert monitoring and alert notifications are enabled.

### Problem: Forecast discussion is unavailable

What it usually means:

- the current location is outside NWS coverage
- the current provider does not support discussions
- Automatic mode did not use NWS for the current path

What to try:

1. Switch to a US location.
2. Use Automatic or NWS as the weather source.
3. If you need national products, enable and select Nationwide.
4. Refresh and try again.

### Problem: AI features are unavailable

What it usually means:

- no OpenRouter key is configured
- the key is invalid
- the selected model is unavailable or rate limited

What to try:

1. Open Settings > AI.
2. Enter or validate your OpenRouter API key.
3. Try a free model first.
4. If responses are empty, switch models and try again.

### Problem: API key validation fails

What it usually means:

- the key was entered incorrectly
- the provider account is not active yet
- the provider site is temporarily unavailable

What to try:

1. Paste the key again carefully.
2. Make sure there are no extra spaces before or after it.
3. Confirm you copied the correct provider's key.
4. Wait a few minutes and validate again if the key was just created.

### Problem: Update checks are not happening when expected

What it usually means:

- automatic update checks are disabled
- the check interval is longer than you expected
- you are on a different update channel than you intended

What to try:

1. Open Settings > Updates.
2. Confirm automatic checking is enabled.
3. Review the release channel.
4. Use Check for updates now to test immediately.

### Problem: Automatic mode did not use the source I expected

What it usually means:

- your saved US or international source order is different from what you remember
- the provider you expected is not currently available
- you selected Economy or Balanced instead of Max coverage

What to try:

1. Open Settings > Data Sources.
2. Review the Automatic mode summary.
3. Open Configure automatic mode budget and sources.
4. Check whether you are looking at the US list or the international list.
5. If you want full fusion-first behavior, choose Max coverage.
6. Confirm any required API key is present and valid.

## 11. Additional features

### Weather History

Use View > Weather History to compare current conditions with recent history when that data is available.

This feature can be turned on or off in Settings > Advanced.

### Air Quality and UV details

Use the View menu to open dedicated air quality and UV windows.

These windows can show current values, categories, forecasts, and guidance when the underlying weather data includes them.

### Aviation Weather

Use View > Aviation Weather to fetch decoded aviation weather by four-letter ICAO airport code, such as KJFK.

This is useful when you want raw and decoded TAF information and related advisories.

Use this when:

- you fly, dispatch, spot aircraft, or monitor airport conditions
- someone you care about is traveling and you want to understand airport weather more clearly
- you need a more aviation-focused view than the normal city forecast provides

This is helpful if you want screen-reader-friendly decoded aviation text instead of trying to interpret compact raw aviation codes on your own.

An optional AVWX key can improve international aviation support. Leave it alone if you only check US aviation weather occasionally. It is mainly worth adding if international airport weather is important to you, and AccessiWeather includes a button that takes you to the place to get that key.

### NOAA Weather Radio

Use View > NOAA Weather Radio to open the radio player for the current location.

This feature is most useful in NOAA coverage areas and depends on online station streams being available.

### Explain Weather

Explain Weather gives you a one-shot AI explanation of the current weather.

Use it when you want a quick plain-language summary.

### Weather Assistant

Weather Assistant is the chat-style AI tool.

Use it when you want follow-up questions, practical advice, or a longer conversation about the current weather and forecast.

## 12. Where to get help

If you need help, updates, or downloads, use these resources:

- Project website: [AccessiWeather on orinks.net](https://orinks.net/accessiweather)
- Report a bug: [Orinks/AccessiWeather issues](https://github.com/Orinks/AccessiWeather/issues)
- Download releases directly: [Orinks/AccessiWeather releases](https://github.com/Orinks/AccessiWeather/releases)
