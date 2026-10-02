[简体中文](codex-desktop.zh_CN.md) · **English**

# Mac companion application

The native window is the beginner entry point for USB and BLE firmware. Existing
Wi-Fi CLI and standalone offline firmware remain available; see [modes](codex-modes.md).
P1 features need the matching updated Mac app and firmware. Other ideas are in the [backlog](codex-improvements.md).

## First launch

1. Use an Apple Silicon Mac with macOS 15 or later. Install Codex and sign into
   your existing ChatGPT account. Supported capabilities depend on Codex version
   and account. This helper does not provide a subscription or unlimited quota.
2. Extract and open `Codex Passport.app`, optionally moving it to Applications.
   Packaged-app users need no Python, ESP-IDF, CMake or terminal. This free build
   is ad-hoc signed, not Apple notarized. Other Macs may block it; follow normal
   macOS verification or administrator procedures. Do not disable security controls.
3. Read the Codex/account checks. The optional base speech model is about 142 MB.
   Choose an existing `ggml-base.bin` to reuse without copying, or download it
   from the window. Imports/downloads are SHA-256 checked. Without the model,
   clock, quota and conversations still work; voice does not.
4. Select USB or BLE to match the installed firmware and connect. USB requires a
   data cable. For BLE, turn on the card and allow the normal Bluetooth prompt.
   First pairing asks for the six-digit PIN displayed on the card. With multiple
   cards, turn on only the target or use CLI `--address`.
5. Keep the app and Mac running. Wake the card using a function key. Its separate
   power key cuts hardware power; Mac sleep also suspends service.

Only one updated GUI/CLI helper can own the card. Older diagnostic scripts
predate this lock: check their drafts/queue and stop them first. The app never
downloads a model automatically or calls a paid recognition service.

## Window and icon

Version 0.5.0 uses five native macOS pages selected from the sidebar: connection, speech
model, notification settings, firmware flashing and device information. Connection shows device, Codex and account status; speech
installs or reuses the local model; notifications exposes switches and quiet hours. A persistent
status area retains progress and errors across pages. Navigation does not disconnect the card.
The interface follows system light/dark appearance and uses macOS fonts for Chinese.
The mint passport icon appears in the Dock, Finder and window branding.

The new device page requires replacing the Mac app and flashing matching 0.5.0 firmware.
Handle recordings and unsent drafts before normally quitting the old app.
Existing model paths and notification preferences remain in the original data directory.

## Flash firmware from the window

1. Open the firmware page. Choose a bundled BLE, USB, offline or Wi-Fi image, or select a
   local merged `.bin`. Wi-Fi still requires the existing CLI configuration and TLS service;
   this page does not add graphical Wi-Fi setup. Flashing itself needs neither Codex login
   nor a speech model, and makes no network request.
2. Turn on the card and connect a USB data cable. Scan, then select the exact port and serial
   number. Multiple cards require an explicit selection. Bluetooth cannot flash firmware.
3. Keep configuration preservation enabled for an update. The app reads the partition table
   and requires an exact match before writing the bootloader, table and application segments.
   It leaves NVS and PHY regions untouched. For a first installation or incompatible layout,
   explicitly disable preservation and confirm that pairing and Wi-Fi settings will reset.
   That option writes the merged image at `0x0`; it does not erase the entire chip.
4. Review firmware version, SHA-256, selected device and data impact, then confirm. Recordings,
   drafts and tracked queues block flashing. The helper drains and pauses the existing connection,
   checks exclusive ownership, and verifies the ESP32-C3 target and 8 MB Flash before writing.
5. Keep USB connected until writing and hash verification finish. The card reboots; return to
   the connection page and select the newly installed mode. A local log is available from the
   firmware page. On failure, read the message and log before retrying; no automatic write retry occurs.

Only standard project layouts are supported: NVS at `0x9000`, PHY at `0xF000`, factory app at
`0x10000`. App-only, oversized, corrupted, wrong-chip, custom-layout and extra-data images are
rejected. Both ESP image checksums/SHA digests and partition MD5 are verified. Imported firmware
is not authenticated as an official release by these integrity checks; use a trusted source.
The selected bytes are retained through confirmation to prevent a changed file being written.
Normal application exit is blocked while firmware work is in progress.

The bundled tool is unmodified [esptool 4.12.0](https://github.com/espressif/esptool/tree/v4.12.0),
under GPL-2.0-or-later. The application includes its license and dependency licenses under
`Contents/Resources/licenses`. Firmware binaries are build outputs, not tracked source files.

## Recording, conversations and alerts

| Feature | Use and limits |
| --- | --- |
| Recording feedback | Hold middle and wait for the recording label before speaking. Preparation, ready, upload and transcription have distinct text/colors. The meter shows relative input strength, not calibrated decibels. Batch 006 firmware keeps the listening hint steady even during pauses; amplitude alone does not judge speech quality. Release, review and confirm before sending; releasing during preparation cancels. |
| Recent conversations | Three per page, ordered by Codex's actual interaction time, `recency_at`. Rows show processing, desktop attention, failure and pending voice messages tracked by this helper. Requires a Codex version supporting that sort key. |
| Card unread | First observation establishes a baseline; later assistant-reply changes mark unread. Displaying that revision on the latest conversation page while awake clears it. Codex desktop read state is unchanged. Restarting the Mac helper establishes a new baseline. |
| Task alerts | Completion or attention briefly appears in the top status line for six seconds. A sleeping display wakes for six seconds without navigating. At most one alert per 30 seconds; up to eight pending, discarded after 90 seconds. The same task event is not repeated. |
| Settings | The Mac window can disable task alerts, enable sound and set quiet hours. Defaults: alerts on, sound off, UTC+8 22:00–08:00 quiet. Equal endpoints mean all-day quiet. Switches apply immediately; click Save hours after editing times. |
| Sound | Optional recording-ready cue plays before capture; microphone buffers are drained before recording. Task cues and recording share one audio worker, preventing simultaneous playback during capture. Quiet hours also disable the recording cue. |

Observation covers the three listed conversations, the selected conversation and up to eight recently
opened conversations via background polling, not every Codex conversation globally. Content caches
last five seconds, so status can lag. Alerts are supplementary: recording, pending drafts, quiet hours
and disabled alerts suppress playback without a catch-up burst. Once taken for delivery, even an alert
lost during disconnect is not replayed. Unread and notification queues live only in the Mac process;
unread markers remain the entry point for missed replies. Handle permission requests on the computer.

Private `alerts.json` stores only switches and times, never conversation content. The Wi-Fi CLI uses
the same file in its own data directory; share `PASSPORT_DATA_DIR` with the GUI to share preferences
and restart the CLI after changing them. Standalone offline firmware retains clock, Pomodoro and
stopwatch; it has no Codex recording, conversations or alerts.

## Recovery and data

### Device information and firmware comparisons (0.5.0)

The fifth sidebar page shows readings from the connected USB/BLE card. Scroll
for hardware details. Update both the Mac app and card to 0.5.0 to receive data;
older firmware remains usable and displays an explicit unknown-version/waiting
state instead of fabricated readings. This batch also includes the stable
recording hint from batch 006. Wi-Fi and offline firmware do not report monitoring data.

| Reading | Meaning |
| --- | --- |
| Hardware | ESP32-C3 revision, core count, configured CPU frequency, detected Flash capacity, PSRAM capacity, display geometry and board peripheral models. Static SRAM/RTC specifications are shown separately from measured heap usage. |
| Memory | Allocated/free internal byte-addressable heap, lowest free heap since boot and largest free block. The denominator is allocatable heap, not all physical SRAM; it excludes static/reserved memory. |
| Storage | Application image bytes against its partition capacity; Flash chip capacity separately. NVS shows used/free/total entries, not file-storage bytes. |
| Battery | CW2017 percentage and voltage through the existing BSP; failed reads stay unavailable. |
| Temperature | Optional ESP32-C3 die sensor via the BSP, configured for 10–80 °C; not ambient or battery temperature. The sensor is disabled after each read. |
| Runtime | Boot uptime, reset reason, task count and minimum free stack for the communication task. BLE RSSI is available; USB signal strength is not applicable. |

Sampling uses the existing physical transport worker roughly every five seconds
while idle. Recording and draft handling pause sampling; age and connection
status label stale data explicitly. Reconnecting clears the previous device's
displayed sample. No recording, account or conversation content is included.
There is no HTTP monitoring endpoint, cloud upload, history file or new listener.
CPU utilization, charge status/current, battery temperature and power draw are
not exposed as measurements.

The [Espressif chip datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-c3_datasheet_en.pdf)
specifies 400 KB SRAM (including 16 KB cache) and 8 KB RTC SRAM. These are chip
specifications, not an additional pool of free heap.

The page compares the current version/build with a selected local image, or
the matching bundled profile when no image is selected. It distinguishes an
upgrade, identical build, higher card version, same-version different build,
mode change and unknown version. It does not call a local bundle the latest
GitHub release. Only plain numeric semantic versions are ordered; legacy Git
descriptions remain unknown. The firmware ELF hash identifies exact builds.
The upgrade button opens the existing flashing page and selects the matching
bundled mode; it never flashes automatically. An initial update of old firmware
is needed before version reporting becomes available.

Firmware version is maintained in root `CMakeLists.txt` (`PROJECT_VER`); release
changes must increment it. The embedded `CPFW1` mode marker, application version
and ELF hash feed the desktop's verified firmware catalog. Rebuilding the same
version may create a different build and is not silently classified as newer.

### Connection and recovery behavior

| Situation | Behavior / next step |
| --- | --- |
| Temporary BLE loss / card power cycle | Reconnect the original device only; retry backoff from 1 to 15 seconds. |
| Interrupted recording | Discard partial audio; record again after reconnect. |
| Ready draft / tracked queue | Retain in the same process across reconnect and pause; never automatically send or replay the queue. |
| Lost send receipt | Retain request dedupe. Check uncertain Codex outcomes on the desktop; never automatically retry them. |
| Bluetooth off / permission denied | Stop with the specific setting or administrator action. Resolve and click connect. |
| Pairing failure | Pause after three connection/pairing failures. Check PIN; if the Mac forgot the card, clear pairing on the card connection-help page and retry. |
| Protocol mismatch | Stop and request matching firmware; the user can explicitly choose the USB flashing page. Never flash automatically. |
| Quota backend unavailable | Keep the link, periodically retry state, show an actionable message. Never invent quota. |
| Pause | Drain the current RPC and disconnect. Keep drafts, discard partial audio. |
| Quit | Warn about recordings, unsent/uncertain drafts or tracked queue entries. Exit clears memory, but does not recall accepted Codex messages. |

Packaged data lives in `~/Library/Application Support/CodexPassport`. `voice.json`
may reference a verified external model; it contains no conversation content.
For development, `PASSPORT_DATA_DIR` selects an existing private data directory.
Temporary audio is removed after transcription or interruption. Recognition
remains local Whisper base with Simplified Chinese conversion. The GUI opens no
network listener. CLI usage and existing firmware controls are unchanged.

## Build and verification

Developers install `bridge/desktop-requirements.txt` in `.local/transport-venv`
and prepare the pinned CPU engine with `tools/bootstrap_bridge.py`. Run
`bash tools/build_variants.sh` in the activated IDF environment first, then
`bash tools/build_desktop.sh`; output is `build/desktop/Codex Passport.app`.
The packaging script verifies all four content-addressed archives and prepares a firmware catalog.
The ARM64 bundle includes Python, USB/BLE dependencies, esptool, verified firmware, OpenCC and the CPU engine,
but no model, account tokens, personal configuration or recordings.
Source launch: `.local/transport-venv/bin/python bridge/desktop.py`.
See [assets](../assets/README.md) for icon sources and provenance. After changing the source PNG,
run `bash tools/build_desktop_icon.sh` on macOS to regenerate ICNS. The application build includes
both ICNS and the PNG used by the window.

`tests/test_companion_desktop.py` is in the validation gate. It covers device
identity, lost receipts, uncertain sends, bounded failures, stop during
scan/pairing/dispatch, preserved drafts, model verification and exclusive ownership.
`tests/test_companion_activity.py` covers unread receipts, status refresh, dedupe, throttling,
expiry, mute, UTC+8 midnight quiet hours and persistent settings. Actual LVGL rendering checks
recording phases, three conversation rows and alert layout. Physical cue volume, microphone
capture and button timing still require flashed-device acceptance.
Physical radio loss, clean-Mac pairing, Gatekeeper, Intel, long idle and sleep/wake
are separate checks, not proved by host tests.

`tests/test_companion_firmware.py` checks image corruption, chip/layout mismatches, configuration
preservation, reset write scope, device substitution, interrupted writes, process timeout,
pending-work protection, connection draining and ownership. Static-only environments install
`bridge/flash-requirements.txt` as well as `bridge/requirements.txt`.
