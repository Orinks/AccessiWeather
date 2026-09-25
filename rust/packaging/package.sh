#!/usr/bin/env bash
# Bundle the release binary for the current platform into rust/dist/<name>.
# macOS output is an unsigned .app; Gatekeeper users need to right-click > Open.
set -euo pipefail

cd "$(dirname "$0")/.."
name="${1:?artifact file name required}"
version="$(grep -m1 '^version = ' Cargo.toml | sed 's/.*"\(.*\)"/\1/')"
rm -rf dist stage && mkdir -p dist stage

# Linux/macOS link prism as a shared library found beside the executable.
copy_prism() {
  find target/release/build -path '*prism-sys-*/out/lib/*' -name 'libprism*' \
    \( -name '*.so*' -o -name '*.dylib' \) -exec cp -P {} "$1" \;
}

# The bundled default sound pack, like the Python build's soundpacks/default.
copy_soundpack() {
  mkdir -p "$1/soundpacks"
  cp -R ../soundpacks/default "$1/soundpacks/"
}

case "$(uname -s)" in
  Darwin)
    app="stage/AccessiWeather.app"
    mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
    cp target/release/accessiweather "$app/Contents/MacOS/AccessiWeather"
    copy_prism "$app/Contents/MacOS"
    sed "s/@VERSION@/$version/g" packaging/macos/Info.plist > "$app/Contents/Info.plist"
    cp crates/aw-app/ui/icon.png "$app/Contents/Resources/icon.png"
    copy_soundpack "$app/Contents/Resources"
    codesign --force --deep --sign - "$app" || echo "ad-hoc codesign unavailable; shipping unsigned"
    (cd stage && zip -qry "../dist/$name" AccessiWeather.app)
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    cp target/release/accessiweather.exe stage/AccessiWeather.exe
    cp packaging/README-portable.txt stage/README.txt
    copy_soundpack stage
    if command -v 7z >/dev/null; then
      (cd stage && 7z a -tzip "../dist/$name" ./* > /dev/null)
    else
      powershell -NoProfile -Command "Compress-Archive -Force -Path 'stage\\*' -DestinationPath 'dist\\$name'"
    fi
    ;;
  *)
    mkdir -p stage/accessiweather
    cp target/release/accessiweather stage/accessiweather/
    copy_prism stage/accessiweather
    cp packaging/linux/accessiweather.desktop stage/accessiweather/
    cp crates/aw-app/ui/icon.png stage/accessiweather/accessiweather.png
    cp packaging/README-portable.txt stage/accessiweather/README.txt
    copy_soundpack stage/accessiweather
    tar -C stage -czf "dist/$name" accessiweather
    ;;
esac

if command -v sha256sum >/dev/null; then
  (cd dist && sha256sum "$name" > "$name.sha256")
else
  (cd dist && shasum -a 256 "$name" > "$name.sha256")
fi
ls -la dist
