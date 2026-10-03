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

## 009 — 2026-10-02 — Local card device page (firmware 0.6.0)

| Area | Change |
| --- | --- |
| Card display | A single-screen summary of battery/voltage, chip temperature, used/total allocatable heap, application/partition usage, Flash capacity, firmware and uptime. Header shows chip/profile; the top-left clock stays visible. Missing readings remain `--`. |
| Controls | From quota, click down to enter and middle/up/down to return; hold down still opens connection help. Offline tools add device information after the stopwatch, with middle returning to clock and running timers preserved. |
| Sampling | Card header, device page and physical USB/BLE reports share a synchronized sample. Hardware reads move to the existing UI worker outside the LVGL lock, roughly every five idle seconds, pausing during voice handling. Offline tools use five seconds on this page, thirty elsewhere. No extra task or Wi-Fi reporting path. |
| Documentation | Refreshed quota/offline-clock footers and added both device-page LVGL previews to the README. These images contain public sample values, not hardware measurements. |

**Upgrade:** flash matching 0.6.0 firmware. Desktop 0.5.0 remains compatible; use
its local `.bin` picker. Its existing bundled 0.5.0 images predate this page.
Merged images support `0x0` provisioning, which can reset stored data; use the
compatible segmented preservation option for an update. The card now runs
offline 0.6.0 following the authorized configuration-preserving flash below.

| Validation | Result |
| --- | --- |
| Build | PASS — complete gate and all four firmware profiles, merged layouts and matching ELF archives. No new Mac application build was required. |
| Host tests | PASS — 87 companion Python tests, new pure-C measurement/formatting checks, C/BSP/repository gates and Chinese glyph coverage. Actual LVGL navigation/layout checks passed, including 200 companion and 500 offline page-switch cycles in a 32 KB pool. |
| Device tests | Offline 0.6.0: configuration-preserving segmented flash passed three write verifications; 18-second serial observation showed matching 0.6.0/ELF, display, battery, button and temperature initialization, with no crash logged. |
| Unverified | Real-screen Chinese glyphs and physical navigation, sleep/wake, card/desktop battery agreement after refresh, shared sampling while connected/recording, actual task-stack/heap margins and screen-off power; USB/BLE/Wi-Fi 0.6.0 remain unflashed. Earlier pending checks remain. |

## 010 — 2026-10-03 — Native diagnostic console (desktop 0.6.0, firmware 0.7.0)

| Area | Change |
| --- | --- |
| Console | Sixth native desktop page displays bounded connection events, request categories/status codes and actionable errors. Successful polls are sampled, audio chunks omitted, and the last 160 entries remain only in memory. |
| Commands | Four card-native, read-only queries cover device summary, battery/temperature, heap/tasks and firmware identity. One command is offered through the existing state response and returned over the same USB/authenticated BLE link. Thirty-second timeout and result IDs prevent duplicate display. |
| Scope | No arbitrary shell access, new listener, background card task, voice payload logging, or Wi-Fi telemetry. Offline 0.6.0 on the tested card remains unchanged until a separately approved flash. |

**Upgrade:** desktop 0.6.0 shows events with an older connected card. Card
command replies require matching USB/BLE 0.7.0 firmware. The four 0.7.0 images
retain the on-card device page; Wi-Fi and offline profiles do not offer desktop
diagnostic commands. Full images support `0x0` provisioning; preserve NVS with
the compatible segmented desktop update option.

| Validation | Result |
| --- | --- |
| Build | PASS — complete gate, four 0.7.0 profiles, verified merged images and matching ELF archives; ARM64 desktop 0.6.0 built with four matching images and signature checked. |
| Host tests | PASS — 89 companion Python tests, pure-C card diagnostic formatting, existing C/BSP and repository checks; real LVGL companion/offline previews passed 200/500 page switches. Native desktop console was visually inspected with labeled sample events. |
| Device tests | New 0.7.0 firmware NOT RUN. The card currently has offline 0.6.0. |
| Unverified | Live command round trips and errors on USB/BLE 0.7.0, native console layout on another Mac, sustained event volume and reconnect during a pending command. |

## 011 — 2026-10-03 — Offline USB time sync (desktop 0.7.0, firmware 0.8.0)

| Area | Change |
| --- | --- |
| Clock | Offline firmware accepts only a fixed USB clock handshake. The Mac confirms the offline response before sending Unix milliseconds; the card renders fixed UTC+8 in 24-hour format with aligned second boundaries. |
| Automatic triggers | After a verified offline flash and reboot, desktop attempts time sync. While running, it detects USB attach/reconnect and periodically corrects drift. A failed flash never sends time; a successful flash without time acknowledgement reports that separately and retries. |
| Independence | No Codex login, network or speech model is needed. The clock continues after unplugging, and manual setting remains. Full power loss still requires another USB or manual sync; display sleep does not. |
| Interface | Refreshed Simplified Chinese unset-clock prompt and LVGL gallery. |

**Upgrade:** install desktop 0.7.0 and flash offline 0.8.0 together. The tested
card still has offline 0.6.0; this batch has not been authorized for flashing.
The merged image provisions from `0x0`; preserve existing settings through the
desktop's compatible segmented update. A USB cable alone cannot supply time
when the desktop program is closed.

| Validation | Result |
| --- | --- |
| Build | PASS — all four 0.8.0 firmwares, `0x0` merged images and matching ELF archives; ARM64 desktop 0.7.0 packages four verified profiles and passes signature checks. |
| Host tests | PASS — 94 companion Python tests, pure-C clock conversion/handshake checks, repository/BSP/Chinese glyph gates; real LVGL offline UI survived 500 page changes, and the new unset-clock prompt was visually inspected. |
| Device tests | NOT RUN — offline 0.8.0 has not been flashed; the existing offline 0.6.0 startup check does not validate USB clock sync. |
| Unverified | Real-card handshake, time accuracy, USB unplug/rapid reconnect, independent running after Mac app exit, and resync after full power loss. |

## 012 — 2026-10-03 — Battery history while unplugged (desktop 0.8.0, offline firmware 0.9.0)

| Area | Change |
| --- | --- |
| Card sampling | The offline card reuses CW2017/device readings to save percentage, voltage and boot uptime every five minutes; at ≤10% it samples every minute, and a three-point drop can add a sample after 30 seconds. Recording continues with the display asleep and USB unplugged. |
| Persistence | A 192-entry NVS ring covers about 16 hours at the normal interval. Saved samples survive full power loss; the device page shows count and storage failures. The existing clock and four-page navigation remain. |
| Import | The Mac requests a bounded, complete export from the exact USB serial identity and deduplicates samples into a private CSV. Device Info shows the latest reading and a monotonic gauge trend, with a button to open the CSV. Samples before clock sync retain uptime but leave absolute time blank. |
| Limits | BSP has no verified charging-state/current interface; the log does not infer charging, and a decline describes fuel-gauge readings only. No paid service, network or Codex login is needed. |

**Upgrade:** install desktop 0.8.0 and flash offline firmware 0.9.0 with
configuration preservation. The tested card still has offline 0.6.0 and this
batch has no new flashing authorization, so real unplugged logging has not
started. Full `0x0` images can provision a blank device but affect stored
configuration; use the compatible segmented update for normal upgrades.
Logging runs on the card without the Mac; USB reconnection imports while the
desktop app runs.

| Validation | Result |
| --- | --- |
| Build | PASS — all four 0.9.0 profiles, `0x0` merged images and matching ELF archives; signed ARM64 desktop 0.8.0 bundle. |
| Host tests | PASS — 100 companion Python tests, new pure-C ring/interval checks, repository/BSP/Chinese glyph gates; actual offline LVGL UI survived 500 page changes and the record count was visually inspected. |
| Device tests | NOT RUN — offline 0.9.0 has not been flashed; the earlier offline 0.6.0 startup result cannot verify continuous sampling or NVS writes. |
| Unverified | Actual NVS headroom/write/recovery, unplugged sampling and USB import, time accuracy, instrumentation power cost, real charging state and gauge calibration; a full discharge trace is needed to assess runtime. |

## 013 — 2026-10-03 — Native battery bar chart (desktop 0.8.1)

| Area | Change |
| --- | --- |
| Chart | Open battery history from Device Info. Last 24 hours uses 15-minute bars; seven days uses two-hour bars. Select a card, inspect a sample by clicking a bar, and see the latest reading and period minimum. Red means ≤20%; zero remains visible. |
| Data fidelity | Reuse the existing local CSV. Each interval uses its last measured sample; gaps remain empty. Unsynced, invalid and future-dated rows are excluded with visible counts. Devices stay separate and imports are deduplicated. Charging and remaining runtime are not inferred. |
| Desktop | Native light/dark appearance, background file parsing and approximately ten-second refresh while open; no added runtime dependencies. README screenshots use explicitly fictional data rendered by the real view. |

**Upgrade:** replace the Mac app with 0.8.1. This batch changes no firmware source.
Collecting real readings still requires offline 0.9.0 from batch 012, which has
not yet been flashed. The seven-day chart uses history already imported to the
Mac; the card still retains at most 192 samples. No commit, publication or flash
was performed.

| Validation | Result |
| --- | --- |
| Build | PASS — signed ARM64 desktop 0.8.1; complete offline 0.9.0 regression gate and verified merged-image archive. Rebuilt offline image SHA-256: `bbcff43e4df17f45756f2fc90bcc0f05ba416f06178b431cbee0f5a45b34c35b`; matching ELF: `85b3697153b160fbc71cc57efe9c98bd82fda14670a0f34942f0e032bc114688`. |
| Host tests | PASS — 106 companion Python tests including six chart-data tests, plus existing C/BSP/repository gates. Native light/dark, seven-day, empty-state and sample-detail rendering checked with isolated fixtures. |
| Device tests | NOT RUN — this batch is desktop-only; no device was flashed or queried by the preview. |
| Unverified | Real imported discharge history, multi-day accumulation, actual battery health and clean-Mac installation; fictional preview data does not establish battery performance. |

## 014 — 2026-10-03 — Battery history across all profiles (desktop 0.9.0, firmware 0.10.0)

| Area | Change |
| --- | --- |
| Card | BLE, USB, Wi-Fi and offline share one NVS logger started independently of transport setup. It records while disconnected and screen-off, reuses the existing battery cache, and retains the same ring across compatible profile changes. Voice work defers Flash writes and stale cache values are not relabeled as fresh measurements. |
| Replay | BLE/USB CPv1 and authenticated Wi-Fi TLS send at most 16 samples per batch. The factory MAC matches the USB identity. The Mac validates and saves before acknowledging the last sequence; interrupted/repeated pages are deduplicated. Offline keeps the existing USB import. |
| Clock and UI | Battery acknowledgments also sync the clock without depending on Codex quota success. Repeated clock polls do not force extra Flash writes. All device pages show the count/storage failure, and desktop 0.9.0 shares the chart and CSV across modes. The CLI honors `PASSPORT_DATA_DIR` for application data. |

**Upgrade:** desktop 0.9.0 and the corresponding 0.10.0 firmware. NVS schema and
partition layout remain compatible. The user requested BLE flashing; BLE 0.9.0
first passed a preserved-configuration write and startup observation, then the
same active request was extended to shared battery recording and BLE 0.10.0 was
flashed. Current full-image SHA-256:
`4d2bf3fa1f852dc100cc3847b2878d6e00a0b1f1dca67cb76f2bbd211a405e07`;
matching ELF: `b82a954b5dbf703400f9bc3acae2a61249fcd01ab91cbf0646558c72406bbce5`.
The verified debug archive is under `build/firmware/<full-image-sha256>/`.

| Validation | Result |
| --- | --- |
| Build | PASS — all four 0.10.0 profiles and merged images; signed ARM64 desktop 0.9.0. BLE static DRAM usage is 191202/321296 bytes; this is not runtime heap headroom. |
| Host tests | PASS — 111 companion Python tests, pure-C batch/ring tests and complete BLE gate; other three firmware gates pass. Actual LVGL companion/offline previews pass 200/500 navigation cycles, and Chinese device-page layouts were inspected. |
| Device tests | PARTIAL — BLE 0.10.0 preserved-configuration flash verified all three segments; twenty-second startup confirms version/ELF, gauge/audio initialization and advertising. The directly run helper passed Mac scan, authenticated connection, real Codex state sync and CSV battery import. A controlled reboot restored old records, added calibrated samples and deduplicated replay (six rows). Packaged desktop handoff is blocked by a macOS code-requirement mismatch in its old Bluetooth grant, pending reauthorization. |
| Unverified | Unplugged multi-hour discharge, physical power loss during writes, Wi-Fi/USB/offline 0.10.0 on-device import, audio under background logging, and physical battery calibration. |

## 015 — 2026-10-03 — Draft standby and quota fault isolation (desktop 0.9.1, firmware 0.10.1)

| Area | Change |
| --- | --- |
| Draft monitoring | Device sampling, battery logging and replay continue while reviewing a draft or transcribing on the Mac. Preparation, capture, finishing and sending still defer background work. UI and transport share pure-model mode policies. |
| Display | A draft can dim after 60 seconds without input and remains intact. The first button press only wakes the display. A newly available draft starts a full viewing interval. Offline sleep behavior is unchanged. |
| Quota degradation | Quota failures no longer discard the thread list, conversation, draft or time response. Cached values retain their actual update timestamp and are marked stale; no cache means unknown. Retry after 30 seconds and clear the warning on recovery. Sending always forces a fresh check and never sends or queues on quota-read failure. |
| Scope | This batch addresses the first two review findings. Bluetooth error classification, core-module separation and history indexing remain follow-up work. No dependencies added. |

**Upgrade:** desktop 0.9.1 and the corresponding 0.10.1 firmware. Partition layout
and battery-log schema are unchanged; preserve configuration during upgrades.
The card still runs the previous BLE 0.10.0. This batch has not been flashed;
earlier hardware results do not establish acceptance of these fixes.

| Validation | Result |
| --- | --- |
| Build | PASS — all four 0.10.1 firmware gates, merged-image/debug archives, signed ARM64 desktop 0.9.1. BLE static DRAM remains 191202 bytes. |
| Host tests | PASS — 114 companion Python tests, including cold-cache quota failure, cached fallback/backoff/recovery and strict send checks. Pure C simulates an hour-long retained draft with continued logging while dimmed and capture protection. Actual LVGL verifies wake without sending, stale/unavailable quota labels, and 200 companion / 500 offline navigation cycles. |
| Device tests | NOT RUN — no flash in this batch. |
| Unverified | Physical draft standby beyond a minute, wake/sampling/replay, real quota outage/recovery, audio coexistence timing and sustained unplugged discharge. |

BLE full-image SHA-256: `5dff385f5016583243b0aab144311d27ba33c3c6766d3e166ddef4b93f131e78`; matching ELF: `5675acbbe20a29810c373c1212213091c8f603c6c22707ae18a7a9e9ac78ad8c`.
Verified archive: `build/firmware/5dff385f5016583243b0aab144311d27ba33c3c6766d3e166ddef4b93f131e78/`.
The new desktop is staged in `build/desktop-resilience/Codex Passport.app`; the running app was not replaced. No USB card was detected at handoff.

## 016 — 2026-10-03 — Background quota and desktop connection resilience (desktop 0.9.2)

| Area | Change |
| --- | --- |
| Quota | A separate single worker refreshes the cache without blocking state reads or recognition. Cold caches are unknown; failed refreshes keep timestamps and back off. Sending still forces a fresh read even after waiting for an in-flight background read. |
| Bluetooth | Distinguish scan, permission, connection, authentication, notification setup and established-link failures. Pre-session retries remain bounded; OS identifiers are hidden and connection errors no longer suggest clearing pairing. |
| Monitoring | Draft presence alone no longer marks device readings stale. Fresh samples remain live during review/transcription; recording/sending and samples older than 15 seconds remain explicitly paused/stale. |
| Scope | No firmware source changes, paid service or new runtime dependencies. Preserve previous modifications on `feature/desktop-connection-resilience`. Native preview fixtures and bilingual documentation refreshed. |

**Upgrade:** desktop 0.9.2 only for this batch. Card-side continued sampling during draft review still requires batch 015 firmware 0.10.1. New app staged at `build/desktop-async/Codex Passport.app`; the running app was not replaced. No flash, commit or push performed.

| Validation | Result |
| --- | --- |
| Build | PASS — ARM64 desktop 0.9.2 packaged and signature verified. Complete BLE gate passed. All four bundled 0.10.1 images verified against their debug archives; USB/offline/Wi-Fi reused from batch 015. |
| Host tests | PASS — 120 companion Python tests plus C/BSP/repository gates. Event-controlled slow RPC tests cover immediate snapshots, one in-flight quota job, independent ASR and strict send recheck. BLE fault injection checks stage-specific messages and permission failures. Fresh/stale monitoring covers draft, transcription, sending and recording. Native light/dark previews pass; selected Chinese layouts inspected. |
| Device tests | NOT RUN — no physical BLE/USB session or flashing this batch. |
| Unverified | Real macOS permission/pairing and interrupted-link recovery with 0.9.2; physical 0.10.1 draft sampling/standby; real quota outage/recovery and long-duration discharge. Prior packaged-app Bluetooth authorization may still need reauthorization. |

Rebuilt BLE merged-image SHA-256: `e99b71790084671b2a2301e6f653e0e17e754bb63a3dd38ff56034928745d51a`; matching ELF: `a5ff5e590728f2e00528fc113bf7695ac50b879bd2cb242e47290f694426131b`. The build identity differs from batch 015; the firmware version remains 0.10.1. Verified archive: `build/firmware/e99b71790084671b2a2301e6f653e0e17e754bb63a3dd38ff56034928745d51a/`.

**Desktop handoff follow-up:** 0.9.2 was launched and its real Codex account self-check passed. BLE scanning failed three times and paused with the new scan/permission guidance. macOS TCC logs confirm that the existing Bluetooth grant does not match the new app code signature. Permission refresh was started in System Settings and is pending explicit user authorization to complete/relaunch. No successful card connection or flash is claimed.

## 017 — 2026-10-03 — Battery icon and level colors (firmware 0.10.2)

| Area | Change |
| --- | --- |
| Card status bar | A small filled battery icon identifies the percentage. Both icon and text use red at 0–20%, yellow at 21–50%, and green at 51–100%; 20% is red and 50% is yellow. Invalid/unavailable readings show an empty gray icon and `--`. |
| Profiles | BLE, USB and Wi-Fi share the same indicator as offline clock/focus/stopwatch/device pages. The UTC+8 clock keeps its position; the redundant CODEX header word makes room for the icon and 100%. |
| Implementation | Reuse BSP readings, one shared color function and one shared LVGL widget. The icon uses two graphical objects, no bitmap or font glyph. No charging-state claim is inferred from the battery level. |

**Upgrade:** flash the matching 0.10.2 firmware. Desktop 0.9.2 remains compatible; its existing package still bundles 0.10.1, so select the newly delivered merged `.bin` file to flash 0.10.2. Partition layout and battery-log schema are unchanged. The implementation stage did not change Bluetooth permissions, flash, commit or push; see the subsequently authorized flash below.

| Validation | Result |
| --- | --- |
| Build | PASS — complete Wi-Fi gate and USB/BLE/offline firmware gates; all four 0.10.2 merged images and matching debug archives verified. |
| Host tests | PASS — 120 companion Python tests plus C/BSP/repository gates. Color boundaries cover 0/20/21/50/51/100 and invalid readings; actual LVGL exercises both interfaces, dynamic fill and fallback, with 200 companion / 500 offline navigation cycles. |
| Device tests | PARTIAL — user-authorized BLE 0.10.2 flash preserved configuration and verified all three written segments. A controlled 20-second startup confirmed 0.10.2, the matching displayed ELF prefix, battery/audio initialization and BLE advertising without a panic. The user confirmed the currently displayed battery icon and color work correctly; every threshold was not physically crossed. |
| Unverified | Physical transitions across the 20%/50% thresholds and display acceptance of the other three profiles; the current BLE icon and color were confirmed by the user. |

README card images refreshed; new threshold images are real LVGL renders using synthetic readings. Chinese glyphs/layouts inspected; the icon does not depend on Chinese font coverage.

Build identities (debug archives at `build/firmware/<merged SHA-256>/`):

| Profile | Merged SHA-256 | Matching ELF SHA-256 |
| --- | --- | --- |
| ble | `deb453499cf4ab5e26c7f76f9b942c41350729bed1c7194d4478a30b73279ab1` | `66491939e358169e65ba1737c8980abd4bbd7a882d5f2a65097f53dbd8076301` |
| usb | `7f56b92371c237be51308d95bd4ff51f364b261b4852ae0d179e5f1cd06fcc54` | `220beaf6e4a1b53e860556821e170b27d1ab10737d24c3f96739fcde34ba00a0` |
| wifi | `afa6620e4458cb00f94492eb441ca00c5d13ee4509d8067c413fb2ae25895f15` | `ecef33fe97d32f4f7db1e1eb901c9a787478860b400b83ea9db72e0c430d6028` |
| offline | `ef30acaaf9fd6ba261d00d9de656343169d44b56a3e1605f97bfc5098ce83f9d` | `aba4cbe1fae620fd359353e9db2d26ee1cea91954e62e24d06e418bc976bac28` |

**Authorized flash follow-up:** the existing partition table matched before writing only the bootloader at `0x0`, table at `0x8000` and app at `0x10000`; NVS/PHY configuration regions were not written. The exact BLE identity matches this batch archive. Serial monitoring was closed afterward. The desktop local-file picker left its Open button disabled; that issue remains to investigate separately. This flash used the same verified core directly and does not establish GUI-picker acceptance.

**User acceptance and integration:** the user confirmed the new battery icon and current level color, and authorized committing batches 009–017 and merging them into local `master`. This does not establish acceptance of every profile/threshold or resolution of the earlier desktop permission/file-picker issues.
