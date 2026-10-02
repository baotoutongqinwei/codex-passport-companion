[简体中文](codex-updates.zh_CN.md) · **English**

# Codex companion update record

This log records completed development batches for this application. A batch is
not a GitHub release or proof of hardware acceptance. Release downloads may lag
behind the source documented here. Earlier work is described in the
[application guide](codex-companion.md) and repository history.

## Recording each batch

- Append a new numbered entry below after every completed update batch, before
  delivery or commit. Continue from the largest number; never reuse a number.
- Use the completion date in UTC+8 and an actual application version when one
  exists. Documentation-only changes do not need an artificial version bump.
- Record user-visible changes, required Mac updates or card flashing, Build,
  Host tests, Device tests and Unverified separately. Distinguish new results
  from previously recorded results.
- Keep this file and its Chinese counterpart aligned. Update the README's
  latest-batch link and refresh relevant screenshots when the interface changes.
- Use public-safe sample data for card previews. Label LVGL renders explicitly;
  do not present them as device photos. Keep private configuration, recordings,
  personal conversations and binary release packages out of Git.

## 001 — 2026-10-02 — Three P1 improvements (0.3.0)

| Area | Change |
| --- | --- |
| Recording | Distinct preparation, ready, recording, transfer and transcription states; relative microphone level; optional start cue. Review and confirmation remain required before sending. |
| Conversations | Three rows per page, sorted by actual interaction recency; running, queued, desktop-action and card-local unread states. Viewing the latest reply clears its matching unread revision. |
| Task alerts | Six-second completion/action-needed banner, at most once per 30 seconds; bounded queue, deduplication and expiry. Default silent mode and UTC+8 22:00–08:00 quiet hours; no sound during recording. |

**Upgrade:** update both the Mac helper and the matching BLE/USB/Wi-Fi firmware
for the full P1 experience. Offline firmware retains its independent clock,
Pomodoro and stopwatch. Flash only with device-owner approval.

| Validation | Result |
| --- | --- |
| Build | PASS — all four firmware profiles, merged images at `0x0`, debug archives and ARM64 Mac application. |
| Host tests | PASS — 68 companion Python tests plus repository/BSP/model checks; real LVGL rendering and navigation with the application font and a 32 KB pool. |
| Device tests | NOT RUN for the new P1 firmware features. Earlier voice/transport results do not validate the new cues and alerts. |
| Unverified | Real microphone level feedback, cue volume, alert wake-up and button timing after flashing P1 firmware. |

Usage and boundaries: [Mac guide](codex-desktop.md) · [Card guide](codex-companion.md).

## 002 — 2026-10-02 — Desktop interface and icon (0.3.1)

| Area | Change |
| --- | --- |
| Window | Native macOS sidebar with connection, local voice model and alert settings pages; visible connection/account status and persistent error details. |
| Appearance | Light and dark colors follow macOS; system Chinese fonts; clearer spacing, switches and time fields. There is no separate in-app theme selector. |
| Icon | Original mint passport/terminal icon for the window, Dock and Finder; PNG source, ICNS and reproducible icon packaging script. |
| Existing setup | Reuse the installed local speech model and saved preferences; no extra model download or paid service. |

**Upgrade:** replace the Mac app after handling pending recordings/drafts and
quitting the old copy. This appearance update needs no card flashing. P1 card
features still need the firmware described in batch 001. Allow Bluetooth through
the normal macOS permission flow if requested.

| Validation | Result |
| --- | --- |
| Build | PASS — ARM64 app, icon resources, signature integrity and ZIP integrity; complete BLE firmware gate also passed. |
| Host tests | PASS — full gate, three-page navigation, preference persistence, switch behavior and invalid-time rejection; light/dark screenshots checked for Chinese rendering and clipping. |
| Device tests | PASS, limited to BLE smoke testing — packaged app connected and synchronized time, quota and conversation state; switching pages preserved the connection. Existing speech model detected. |
| Unverified | Recording/sending, USB, extended sleep/wake and radio recovery were not repeated for this appearance update; clean-Mac installation and Intel support remain unverified. |

Build target: Apple Silicon, macOS 15+. The free build is ad-hoc signed and not
Apple notarized. [Screenshot gallery](../README.md#screenshots) ·
[Icon provenance](../assets/README.md).

## 003 — 2026-10-02 — Update history and README gallery

| Area | Change |
| --- | --- |
| History | Added this numbered bilingual log, backfilled batches 001–002 and recorded the continuing rule in the agent instructions. |
| README | Added three Mac screenshots and seven card screens: quota, conversations, recording, task alert, offline clock, Pomodoro and stopwatch. Updated feature and validation summaries. |
| Evidence | Mac dark screenshots come from the packaged app; the light settings view uses isolated sample preferences. Card images are actual LVGL output with deterministic sample data, not photographs. |

**Upgrade:** documentation and screenshots only; no application replacement or
flashing required. This source commit also includes the previously uncommitted
implementation from batches 001–002. It does not publish a GitHub release.

| Validation | Result |
| --- | --- |
| Build | PASS from batch 002; production code unchanged in this documentation batch. |
| Host tests | PASS — pre-commit static gate, bilingual/local-link checks and regenerated LVGL card previews. |
| Device tests | PASS, limited to the existing BLE connection while taking desktop screenshots; no flashing or new firmware acceptance. |
| Unverified | P1 hardware acceptance remains as listed in batch 001. |

## 004 — 2026-10-02 — Integrate into the default master branch

| Area | Change |
| --- | --- |
| Integration | Created `master` from the previous default branch and fast-forwarded it to P1/desktop commit `57f92c2`, preserving history. |
| GitHub | Set `master` as the default branch. Existing `feature/codex-companion` and `feature/codex-p1` branches remain available. |
| Documentation | Updated both READMEs so the default checkout contains the current application, screenshots and update history. |

**Upgrade:** source integration and documentation only. No new runtime change,
binary release or flashing is part of this batch.

| Validation | Result |
| --- | --- |
| Build | PASS from batch 002; application and firmware code unchanged. |
| Host tests | PASS — pre-commit static/host gate and fast-forward ancestry check. GitHub API confirmed the new default branch. |
| Device tests | NOT RUN in this integration batch; earlier results remain in batches 001–003. |
| Unverified | P1 hardware acceptance remains as listed in batch 001. |

## 005 — 2026-10-02 — Desktop USB firmware flashing (0.4.0)

| Area | Change |
| --- | --- |
| Entry point | Added a fourth native sidebar page with four bundled firmware profiles, local merged `.bin` selection, USB device scanning, version/hash details, progress and a local log. |
| Preservation | Updates preserve pairing/configuration by default, after exact partition comparison. First installation can explicitly confirm a merged `0x0` write that resets configuration; no whole-chip erase is used. |
| Validation | Rejects corrupted, wrong-chip, app-only, extra-data and unsupported-layout images. Checks selected USB identity, chip/Flash size, existing connection ownership and pending work before writes. |
| Packaging | Bundles pinned esptool and its dependencies/licenses; end users need neither Python nor ESP-IDF. Existing speech model/settings remain reusable. |

**Upgrade:** replace the Mac application; adding the entry point requires no card flash.
Each device write has a separate confirmation. Wi-Fi remains dependent on the existing CLI
configuration/service. The firmware page does not introduce graphical Wi-Fi setup.

| Validation | Result |
| --- | --- |
| Build | PASS — desktop ARM64 bundle, bundled CLI startup, ESP32-C3 flasher resources, signatures and ZIP integrity; complete BLE firmware gate. Four bundled firmware archives were individually verified. |
| Host tests | PASS — 11 new firmware tests, 79 companion Python tests total, plus the repository gate. Native Chinese layout, firmware selection, preservation/reset confirmations and cancellation checked with an isolated sample USB device. |
| Device tests | Packaged 0.4.0 discovered the real USB card, verified its selected firmware and restored BLE time/quota/conversation sync. Real writes through the new GUI NOT RUN. The preceding separately authorized P1 flash passed segment verification and startup observation; that does not validate this new entry point. |
| Unverified | Actual GUI write, unplug/retry and new-Mac setup; P1 microphone/cue/alert acceptance and long-duration battery/radio behavior remain pending. |

The new README screenshot uses a fictional port and serial number; it is not evidence of a real flash.
See [desktop instructions](codex-desktop.md#flash-firmware-from-the-window).

## 006 — 2026-10-02 — Stable recording hint

| Area | Change |
| --- | --- |
| Recording feedback | The listening hint stays fixed throughout recording. The relative level meter remains live; pauses and level changes no longer switch between low/normal/high-volume advice. Amplitude alone cannot distinguish a pause from quiet speech. |
| Controls | Hold to record, release to finish, 45-second maximum and review-before-send remain unchanged. No speech model or dependency changes. |
| Documentation | Refreshed the recording screenshot and both README summaries; recorded the user's P1 meter and recognition confirmation separately from the new fix. |

**Upgrade:** flash the updated BLE, USB or Wi-Fi companion firmware. Mac 0.4.0 can
load it through the local `.bin` picker; the already-installed app's bundled
images predate this fix. No Mac replacement or offline-tool firmware update is needed.
The merged images support `0x0` provisioning, which can reset configuration;
use the desktop default preservation option for a compatible segmented update.

| Validation | Result |
| --- | --- |
| Build | PASS — complete BLE gate plus USB/Wi-Fi firmware gates; merged layouts, matching ELF archives and desktop local-image validation passed for all three profiles. |
| Host tests | PASS — complete static/host gate (79 companion Python tests), Chinese glyph coverage, actual LVGL normal/quiet/loud previews and 200 page switches; 6,048 bytes remain in the 32 KB LVGL pool. |
| Device tests | NOT RUN for this new firmware. The user confirmed the preceding flashed P1 meter and recognition work; this is not acceptance of the new hint. |
| Unverified | New hint on hardware and actual GUI flashing; earlier pending cue/alert, new-Mac and long-duration device checks remain open. |

## 007 — 2026-10-02 — Device information and local upgrades (0.5.0)

| Area | Change |
| --- | --- |
| Device page | Added a fifth native page with hardware/firmware identity, heap usage and headroom, application partition usage, NVS entries, battery/voltage, die temperature, uptime, BLE signal, reset reason and task/stack information. Chip SRAM specifications are separate from measured heap. |
| Sampling | Idle USB/authenticated-BLE samples roughly every five seconds; recording/draft handling pauses sampling. Disconnects and old readings are explicit; missing sensors never become zero. Reuses the battery BSP and adds an optional BSP die-temperature reader. No Wi-Fi/HTTP monitoring or cloud upload. |
| Versions | Numeric firmware version 0.5.0, mode marker retained independently of logging, and ELF build identity. Compare the selected image or same-mode bundled image; distinguish upgrades, newer cards, identical/different builds, mode changes and unknown legacy versions. |
| Upgrade entry | A notification links to the existing flashing page and selects the matching bundled mode. Writing still requires confirmation. All four bundled images were refreshed; the recording hint from batch 006 is included. |

**Upgrade:** replace the Mac app and flash matching 0.5.0 USB/BLE firmware to enable
readings. Old card firmware remains compatible but cannot report a version or
metrics until its first update. No speech-model download, paid dependency or
GitHub-release lookup was added. Wi-Fi and standalone offline modes retain their
existing functions without device monitoring.

| Validation | Result |
| --- | --- |
| Build | PASS — all four firmware gates, merged `0x0` layouts and exact ELF archives; desktop ARM64 bundle, bundled firmware/CLI validation, signature and ZIP checks. |
| Host tests | PASS — 87 companion Python tests including seven monitoring/version tests and the new mode-marker check, plus C/BSP/repository gates. Invalid/missing data, stale samples, legacy versions, downgrade/mode boundaries and endpoint size limits covered. |
| Desktop checks | PASS — native Chinese overview/detail layout with public sample data, scrolling, upgrade navigation and packaged 0.5.0 startup/account self-check. Preview screenshots are labeled as fixtures. |
| Device tests | PASS (bounded smoke test) — after user authorization, the packaged desktop flashed BLE 0.5.0 while preserving configuration; all three written segments verified. A 20-second startup observation matched ELF `4875e676d0724185` without a crash. BLE reconnected and time/quota/chat synchronization resumed; the reported 0.5.0 build matches the selected image. Observed 99%, 4.135 V, 30.7°C die temperature, about 53.0 KiB free heap and 2.2 KiB minimum network-task stack headroom. Merged SHA-256: `883d4a574e20115f2d5b5857af8a8dab801e07a4068ea2cef68e18b22cdc9277`. |
| Unverified | Card-screen versus desktop battery comparison, sensor accuracy, sustained monitoring/recording headroom, GUI flashing failure recovery, batch 006 hint and earlier cue/alert/new-Mac/long-duration checks. USB reset currently displays as unknown; CPU utilization, charging current/state and battery temperature are not reported measurements. |

See [device-page behavior and measurement definitions](codex-desktop.md#device-information-and-firmware-comparisons-050).

## 008 — 2026-10-02 — Consolidate 0.5.0 source and device results

| Area | Change |
| --- | --- |
| Source | Collected batches 005–007: desktop flashing, the stable listening hint, device monitoring and local firmware comparison, with their tests, build tooling and bilingual guides. |
| Evidence | Recorded the authorized BLE 0.5.0 desktop flash, preserved configuration, verified segments, clean bounded startup, reconnection and real version/resource readings in batch 007. Card-versus-desktop battery comparison remains unconfirmed. |
| Integration | Local Git submission and fast-forward integration into `master`; no remote push or release publication is included. Generated applications, firmware/debug archives, raw logs and private settings remain outside Git. |

**Upgrade:** this source/documentation consolidation does not create another
firmware build. The tested card already runs the exact 0.5.0 image identified in
batch 007; no additional flashing is needed for this entry.

| Validation | Result |
| --- | --- |
| Build | PASS from batch 007; no subsequent production-code changes. |
| Host tests | PASS — pre-commit static/host gate, including 87 companion Python tests, repository and bilingual/local-link checks. |
| Device tests | PASS within batch 007's recorded smoke-test scope; no repeated write in this integration batch. |
| Unverified | Battery comparison, sustained monitoring/recording and remaining hardware acceptance stay as listed in batch 007. |
