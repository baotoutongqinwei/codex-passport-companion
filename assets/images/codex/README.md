[简体中文](README.zh_CN.md) · **English**

# Companion screenshots

Captured on 2026-10-02 for the fork's root README. These images document the
application UI; they are not third-party product photos. They are distributed
with the project's MIT terms, with the Chinese font retaining its
[SIL OFL license](../../fonts/OFL.txt).

| Files | Source | Dimensions |
| --- | --- | --- |
| `desktop-device-dark.png`, `desktop-device-details-dark.png` | Native 0.5.0 device page in an isolated preview with fictional hardware readings and version metadata; no real device access. | 1720 × 1264 |
| `desktop-connection-dark.png`, `desktop-voice-dark.png` | Native screenshots of packaged Mac app 0.3.1, connected over BLE. Only generic application status is visible. | 1720 × 1264 |
| `desktop-alerts-light.png` | Native 0.3.1 window in an isolated light-appearance test, with sample/default preferences. | 1720 × 1264 |
| `desktop-flasher-dark.png` | Native 0.4.0 flashing page in an isolated preview, with a fictional USB port/serial and real validated firmware metadata. No device is opened or flashed. | 1720 × 1264 |
| `card-01-quota.png`, `card-02-threads.png`, `card-04-record.png`, `card-08-completed.png` | Actual companion UI and font rendered by LVGL, using deterministic public sample state in `tests/companion_ui/preview.c`. | 240 × 320 |
| `card-12-offline-clock.png`, `card-13-offline-focus.png`, `card-14-offline-stopwatch.png` | Actual offline UI rendered by `tests/companion_ui/offline_preview.c`. | 240 × 320 |

Batch 006 refreshed `card-04-record.png` to show the stable listening hint.

Card images are renders, not device photographs. Quota, dates, conversation
titles, battery values and task status are fixture data. The same application
code and Chinese font are used by the firmware. A rendered screenshot does not
prove microphone, speaker, button or power behavior on hardware.

## Refreshing the gallery

1. Build and launch the Mac app as described in the [desktop guide](../../../docs/codex-desktop.md).
   Capture its complete window after checking for private text, paths and identifiers.
   Navigate without disconnecting the card or changing saved preferences. For an
   alternate appearance, use an isolated preview; do not change the user's system
   settings solely to obtain a screenshot.
2. Activate the existing build environment and run `bash tools/preview_companion.sh`
   from the repository root. It compiles the actual UI and runs its assertions.
3. Convert the selected PPM frames losslessly to PNG. On macOS, from the repository root:

```bash
for name in 01-quota 02-threads 04-record 08-completed 12-offline-clock 13-offline-focus 14-offline-stopwatch; do
  sips -s format png "build/ui-preview/images/${name}.ppm" \
    --out "assets/images/codex/card-${name}.png" >/dev/null
done
```

4. Inspect every selected image for missing Chinese glyphs, clipping and unwanted
   private content. Keep the native pixels; size images with README HTML rather
   than repainting the UI. Record the refresh in the [batch log](../../../docs/codex-updates.md).
