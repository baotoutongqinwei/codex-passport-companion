#!/usr/bin/env bash
# Package the original generated PNG at macOS's standard icon resolutions.
set -euo pipefail
cd "$(dirname "$0")/.."
source_image="assets/images/codex-passport-icon.png"
icon_tmp="$(mktemp -d /tmp/codex-passport-icon.XXXXXX)"
trap 'rm -rf -- "$icon_tmp"' EXIT
mkdir "$icon_tmp/AppIcon.iconset"
for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$source_image" --out "$icon_tmp/AppIcon.iconset/icon_${size}x${size}.png" >/dev/null
    retina=$((size * 2))
    sips -z "$retina" "$retina" "$source_image" --out "$icon_tmp/AppIcon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$icon_tmp/AppIcon.iconset" -o assets/images/codex-passport.icns
echo 'App icon: assets/images/codex-passport.icns'
