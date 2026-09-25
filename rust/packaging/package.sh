#!/usr/bin/env bash
# Bundle the release binary for the current platform into rust/dist/<name>.
# macOS output is an unsigned .app; Gatekeeper users need to right-click > Open.
set -euo pipefail

cd "$(dirname "$0")/.."
name="${1:?artifact file name required}"
version="$(grep -m1 '^version' crates/aw-app/Cargo.toml | sed 's/.*"\(.*\)"/\1/')"
rm -rf dist stage && mkdir -p dist stage

case "$(uname -s)" in
  Darwin)
    app="stage/AccessiWeather.app"
    mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
    cp target/release/accessiweather "$app/Contents/MacOS/AccessiWeather"
    sed "s/@VERSION@/$version/g" packaging/macos/Info.plist > "$app/Contents/Info.plist"
    cp crates/aw-app/ui/icon.png "$app/Contents/Resources/icon.png"
    codesign --force --deep --sign - "$app" || echo "ad-hoc codesign unavailable; shipping unsigned"
    (cd stage && zip -qry "../dist/$name" AccessiWeather.app)
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    cp target/release/accessiweather.exe stage/AccessiWeather.exe
    cp packaging/README-portable.txt stage/README.txt
    (cd stage && 7z a -tzip "../dist/$name" ./* > /dev/null)
    ;;
  *)
    mkdir -p stage/accessiweather
    cp target/release/accessiweather stage/accessiweather/
    cp packaging/linux/accessiweather.desktop stage/accessiweather/
    cp crates/aw-app/ui/icon.png stage/accessiweather/accessiweather.png
    cp packaging/README-portable.txt stage/accessiweather/README.txt
    tar -C stage -czf "dist/$name" accessiweather
    ;;
esac

(cd dist && shasum -a 256 "$name" > "$name.sha256")
ls -la dist
