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

Version 0.3.1 uses three native macOS pages selected from the sidebar: connection, speech
model and notification settings. Connection shows device, Codex and account status; speech
installs or reuses the local model; notifications exposes switches and quiet hours. A persistent
status area retains progress and errors across pages. Navigation does not disconnect the card.
The interface follows system light/dark appearance and uses macOS fonts for Chinese.
The mint passport icon appears in the Dock, Finder and window branding.

This window/icon update requires replacing the Mac app only; the card's P1 features still need
the previous P1 firmware. Handle recordings and unsent drafts before normally quitting the old app.
Existing model paths and notification preferences remain in the original data directory.

## Recording, conversations and alerts

| Feature | Use and limits |
| --- | --- |
| Recording feedback | Hold middle and wait for the recording label before speaking. Preparation, ready, upload and transcription have distinct text/colors. The meter shows relative input strength, not calibrated decibels. Release, review and confirm before sending; releasing during preparation cancels. |
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

| Situation | Behavior / next step |
| --- | --- |
| Temporary BLE loss / card power cycle | Reconnect the original device only; retry backoff from 1 to 15 seconds. |
| Interrupted recording | Discard partial audio; record again after reconnect. |
| Ready draft / tracked queue | Retain in the same process across reconnect and pause; never automatically send or replay the queue. |
| Lost send receipt | Retain request dedupe. Check uncertain Codex outcomes on the desktop; never automatically retry them. |
| Bluetooth off / permission denied | Stop with the specific setting or administrator action. Resolve and click connect. |
| Pairing failure | Pause after three connection/pairing failures. Check PIN; if the Mac forgot the card, clear pairing on the card connection-help page and retry. |
| Protocol mismatch | Stop and request matching firmware. The app does not flash. |
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
`bash tools/build_desktop.sh`; output is `build/desktop/Codex Passport.app`.
The ARM64 bundle includes Python, USB/BLE dependencies, OpenCC and the CPU engine,
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
