# WordPress Release Page Sync

AccessiWeather now updates the existing WordPress download page directly from the
latest public GitHub release. The WordPress page is the primary public release
page. GitHub Pages remains a mirror for nightly/build information.

## How It Works

`update-wordpress.yml` runs when a GitHub release is published, or when run
manually. It calls `.github/scripts/push_releases.py`, which:

- fetches the latest public stable release from `Orinks/AccessiWeather`
- selects the primary public download asset
- computes GitHub release asset download counts
- fetches the existing WordPress page via `/wp-json/wp/v2/pages/<id>`
- replaces only the managed section between:
  - `<!-- accessiweather-release:start -->`
  - `<!-- accessiweather-release:end -->`
- appends the managed section if those markers are not present yet

## GitHub Configuration

Required GitHub Actions secrets:

- `WP_SITE_URL`: Base site URL, for example `https://accessiweather.orinks.net`
- `WP_USERNAME`: WordPress user allowed to edit the page via REST API
- `WP_APPLICATION_PASSWORD`: Application Password for that WordPress user

Required GitHub Actions variable:

- `WP_PAGE_ID`: Numeric page ID for the existing AccessiWeather download page

## WordPress Requirements

- WordPress REST API must be available at `/wp-json/wp/v2/pages/<id>`
- The configured user must be allowed to edit that page
- For best placement control, add the start/end markers where the generated
  release block should live

If the markers are missing, the workflow appends the generated release block to
the end of the page content instead of replacing the whole page.
