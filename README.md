[简体中文](README.zh_CN.md) · **English**

# Codex Passport Companion

<p align="center"><img src="assets/images/codex-passport-icon.png" width="96" alt="Codex Passport mint card icon"></p>

A pocket Codex companion for [FoloToy AI Passport](https://gitee.com/FoloToy/ai-passport):
review voice input, switch conversations, read replies and check weekly quota on
a 240 × 320 card. The Mac runs Codex and local speech recognition; the card is a
lightweight display, microphone and controller. An independent offline firmware
provides a clock, Pomodoro timer and stopwatch.

This is a community application derived from FoloToy's complete project. It is
not an official OpenAI or FoloToy product. The default application branch is
`feature/codex-companion`; the current P1 and desktop updates are on `feature/codex-p1`.
Upstream history and the reusable BSP are retained.

## Screenshots

### On your Mac

Native connection dashboard, local voice recognition and quiet-hours settings.
The app follows the macOS light/dark appearance.

<p align="center"><img src="assets/images/codex/desktop-connection-dark.png" width="860" alt="Native Mac connection dashboard with the card connected"></p>

| Local voice model · dark | Alert settings · light |
| --- | --- |
| <img src="assets/images/codex/desktop-voice-dark.png" width="430" alt="Local voice model page in dark appearance"> | <img src="assets/images/codex/desktop-alerts-light.png" width="430" alt="Alert switches and quiet hours in light appearance"> |

### On your card

| Weekly quota | Recent conversations | Recording feedback | Task complete |
| --- | --- | --- | --- |
| <img src="assets/images/codex/card-01-quota.png" width="200" alt="Weekly quota and reset dates"> | <img src="assets/images/codex/card-02-threads.png" width="200" alt="Conversation status and unread indicators"> | <img src="assets/images/codex/card-04-record.png" width="200" alt="Recording duration and microphone level"> | <img src="assets/images/codex/card-08-completed.png" width="200" alt="Task completion banner"> |

| Offline clock | Pomodoro | Stopwatch |
| --- | --- | --- |
| <img src="assets/images/codex/card-12-offline-clock.png" width="200" alt="Independent offline clock"> | <img src="assets/images/codex/card-13-offline-focus.png" width="200" alt="Offline Pomodoro timer"> | <img src="assets/images/codex/card-14-offline-stopwatch.png" width="200" alt="Offline stopwatch"> |

Mac dark screenshots show the packaged app; the light settings screenshot uses
isolated sample preferences. Card images are **real LVGL renders at 240 × 320 with
sample data**, not device photographs or hardware acceptance evidence. UI text is
Simplified Chinese. [Capture sources and reproduction](assets/images/codex/README.md).

## Latest updates

| Batch · date | Changes | Upgrade |
| --- | --- | --- |
| 003 · 2026-10-02 | Numbered update history and this screenshot gallery | Documentation only |
| 002 · 2026-10-02 | Desktop 0.3.1, three-page layout, light/dark appearance and app icon | Replace Mac app; no flashing for appearance |
| 001 · 2026-10-02 | Recording feedback, conversation status/unread, quiet task alerts | Update Mac helper and matching card firmware |

[Full update record and test results](docs/codex-updates.md). Release downloads
may lag behind this branch; P1 card features still await hardware acceptance.

## Features

| Feature | Behavior |
| --- | --- |
| Voice | Hold middle to record up to 45 seconds; release, review Simplified Chinese text, then click to send. Whisper base and OpenCC run locally on the Mac. |
| Conversations | Three rows per page ordered by interaction recency, with running/queued/desktop-action/unread state; switch the voice target and read replies. |
| Busy threads | Confirmed messages enter the original thread's queue when supported; uncertain sends are never automatically retried. |
| Quota | One page with 7-day remaining quota, automatic reset time and the earliest two available reset-opportunity expiry dates. No reset is consumed. |
| Clock | Top-left UTC+8, 24-hour time; synced from the connected Mac. |
| Mac window | Native three-page app, light/dark appearance, original icon, account/model checks, USB/BLE choice and model reuse. |
| Feedback and alerts | Recording phases and microphone level; completion/action-needed banners, optional sounds and UTC+8 quiet hours. Requires P1 firmware. |
| Recovery | Reconnect the original USB/BLE device, preserve ready drafts and request dedupe in the running helper, discard interrupted recordings. |

The software adds no paid speech or API service. You still need a supported,
signed-in Codex account and its available quota; this does not provide a free
subscription or unlimited usage. Codex requires Internet access even when voice
recognition is local. Permissions that require the desktop must be handled there.

## Choose a firmware

| Profile | Connection | Mac required | Use |
| --- | --- | --- | --- |
| `ble` | Authenticated Bluetooth LE | Yes | Wireless Codex companion; native Mac app |
| `usb` | USB data cable | Yes | Codex companion without a listening network port; native Mac app |
| `wifi` | Same reachable 2.4 GHz LAN | Yes | Codex companion using the CLI TLS helper |
| `offline` | None during use | No | Clock, 25/5 Pomodoro and stopwatch |

Firmware profiles are separate builds. Selecting BLE/USB in the Mac window does
not change the installed card firmware. The ESP32-C3 has 8 MB Flash and no PSRAM;
it does not run Codex or a speech model by itself.

## Start using the Mac app

1. Open [Releases](https://github.com/baotoutongqinwei/codex-passport-companion/releases) and choose the ARM64 Mac app
   and a matching BLE or USB firmware. Use an Apple Silicon Mac with macOS 15+.
   The app is ad-hoc signed, not Apple notarized; a new Mac may require its normal
   security verification or administrator approval.
2. Flash the selected **merged full image at `0x0`** using the
   [firmware instructions](docs/development/engineering/firmware-layout.md).
   Flashing can replace stored settings. A card already running this companion
   does not need reflashing just to update the Mac application.
3. Install Codex and sign into your existing ChatGPT account. Extract and open
   `Codex Passport.app`; running it requires no Python, ESP-IDF or terminal.
4. Select an existing `ggml-base.bin`, or download the optional roughly 142 MB
   speech model in the window. Both are hash-checked; reusing a model does not copy it.
5. Choose the connection matching the firmware and connect. First BLE pairing
   asks for the six-digit PIN displayed on the card. Keep the Mac awake and app running.

Read the [Mac guide](docs/codex-desktop.md), [all modes](docs/codex-modes.md) and
[controls and limitations](docs/codex-companion.md). Wake a dark card with one of
the three function keys; the separate power key cuts hardware power.
Do not disable corporate network/peripheral protection to connect the card.

## Build from source

Clone the application branch you intend to build (`feature/codex-p1` for the
updates shown above). Start with `AGENTS.md` and
`docs/README.md` if using an AI development agent. The required project skills
are in `skills/`. Existing checkouts and local changes should be preserved.

For firmware, prepare and activate **ESP-IDF 5.5.3** following the
[environment guide](docs/development/engineering/environment-setup.md), then run
these commands from the repository root:

```bash
./tools/validate.sh --all --profile ble
# Other profiles: usb, wifi, offline
bash tools/build_variants.sh
```

Merged images are under `build/variants/<profile>/`. Matching ELF, MAP and flash
segments are archived under `build/firmware/<full-image-sha256>/`.

For the Mac helper, with Python 3.10+ and the build tools available:

```bash
bash tools/install_transport.sh
.local/transport-venv/bin/python tools/bootstrap_bridge.py
.local/transport-venv/bin/python bridge/app.py doctor
.local/transport-venv/bin/python bridge/app.py ble
```

To build the native Mac window, use an Apple Silicon Mac and a Python distribution
with its license file available in the standard library directory:

```bash
.local/transport-venv/bin/python -m pip install -r bridge/desktop-requirements.txt
bash tools/build_desktop.sh
```

Output: `build/desktop/Codex Passport.app`. The bundle includes its runtime and
CPU speech engine; model weights are not bundled. Bootstrap requires Git, CMake,
curl and a C/C++ compiler. Source builds and downloads need additional disk space.

## Validation and limits

| Area | Recorded result |
| --- | --- |
| Build | Four P1 firmware profiles, merged-image/debug-archive verification and native Mac bundle passed; desktop 0.3.1 icon, signature and ZIP checks passed. |
| Host tests | 68 companion Python tests plus repository/BSP/model checks passed. Actual LVGL navigation/rendering and native Mac page/settings checks passed. |
| Device tests | Desktop 0.3.1 BLE state sync and page switching passed. Earlier results include USB voice/reply, BLE 45-second audio and one card power-cycle recovery. |
| Unverified | New P1 card cues, level display and alert wake-up; clean-Mac installation, Intel, native-window USB, long sleep/wake and repeated radio interference. Voice was not repeated for desktop 0.3.1. |

Intel/Windows/Linux desktop bundles are not supplied. Codex's experimental
app-server queue and quota fields can change between versions; an unsupported
account or version may not expose all features. Drafts and dedupe are in memory:
check pending outcomes before quitting. Do not interpret build success as full
hardware acceptance. See the [prioritized backlog](docs/codex-improvements.md).

## Repository and privacy

| Path | Contents |
| --- | --- |
| `main/` | Card application, UI and transport profiles |
| `components/bsp/` | Shared board drivers |
| `bridge/` | Mac helper, native window and speech integration |
| `assets/fonts/` | Chinese source font, generated font and OFL license |
| `tests/`, `tools/` | Host tests, reproducible build and validation tools |
| `docs/`, `skills/` | Bilingual guides, roadmap and AI development skills |

Personal `.local/` configuration, Wi-Fi credentials, TLS keys, account tokens,
recordings, installed models, caches and build directories are excluded from Git.
Temporary audio is removed after recognition or interruption. Never include
conversation text or credentials in public issues. App and firmware binaries are
distributed separately in Releases rather than committed to source history.

## License and acknowledgments

Project code retains FoloToy's [MIT license](LICENSE). The Chinese font uses
[SIL OFL 1.1](assets/fonts/OFL.txt); see [font provenance](assets/fonts/README.md).
Local recognition uses [whisper.cpp](https://github.com/ggml-org/whisper.cpp),
Simplified Chinese conversion uses [OpenCC](https://github.com/yichen0831/opencc-python),
and Bluetooth uses [Bleak](https://github.com/hbldh/bleak). Third-party licenses
remain applicable and packaged runtime notices are included in the Mac app.
