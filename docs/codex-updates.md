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
