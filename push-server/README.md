# AccessiWeather push server

Cloudflare Worker that sends NWS alert notifications to the iOS app over APNs, so alerts arrive while the app is closed.

- `POST /v1/devices` stores a device's APNs token, alert severities and US saved locations (resolved to NWS UGC zones via `/points`). `enabled: false` or no locations removes the device. `DELETE /v1/devices/{token}` removes it too.
- A cron trigger runs every minute. It fetches `/alerts/active?zone=...` for the registered zones only (25 zones per request, which keeps it inside the free plan's 10 ms CPU limit), and pushes new, updated or escalated alerts. Updates are keyed by the original alert they reference. Each alert reaches a device once.
- Pirate Weather, with each user's own key (stored AES-GCM encrypted with `KEY_ENCRYPTION_KEY`), every 15 minutes per location: alerts outside NWS coverage, and rain starting or stopping.
- Forecast discussion, Hazardous Weather Outlook and Special Weather Statement updates, per forecast office every 5 minutes, with the app's wording, baselines and 30-minute rate limits.
- Per-run budgets keep each cron run under the free plan's 50 subrequests.
- The first check of a new location only records the alerts already active there. The app's own local check covers those.
- Dead tokens (410, BadDeviceToken) are deleted. Sent records are kept for 7 days.

## Setup

```sh
npm install
npx wrangler d1 create accessiweather-push   # put the id in wrangler.toml
npx wrangler d1 execute accessiweather-push --remote --file schema.sql
npx wrangler secret put APNS_KEY_P8          # full .p8 text
npx wrangler secret put APNS_KEY_ID
openssl rand -base64 32 | npx wrangler secret put KEY_ENCRYPTION_KEY
npx wrangler deploy
```

Then set `AWPushServerURL` in `ios/AccessiWeather/project.yml` to the deployed URL.

## Checks

`npm test` (offline unit tests) and `npm run typecheck`.
