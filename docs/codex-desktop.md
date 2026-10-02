[简体中文](codex-desktop.zh_CN.md) · **English**

# Mac companion application

The native window is the beginner entry point for USB and BLE firmware. Existing
Wi-Fi CLI and standalone offline firmware remain available; see [modes](codex-modes.md).
This update requires no firmware change. Other ideas are in the [backlog](codex-improvements.md).

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

`tests/test_companion_desktop.py` is in the validation gate. It covers device
identity, lost receipts, uncertain sends, bounded failures, stop during
scan/pairing/dispatch, preserved drafts, model verification and exclusive ownership.
Physical radio loss, clean-Mac pairing, Gatekeeper, Intel, long idle and sleep/wake
are separate checks, not proved by host tests.
