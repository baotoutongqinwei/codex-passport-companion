[简体中文](codex-improvements.zh_CN.md) · **English**

# Companion improvements

Accepted on 2026-10-02. Keep existing firmware modes, the fixed UTC+8 clock,
one-page weekly quota, local Simplified Chinese recognition, and review before
send. No paid service or larger speech model is introduced. This is a backlog,
not a claim that every reference feature has been tested on this device.

| Priority | Improvement | Scope and acceptance | Status |
| --- | --- | --- | --- |
| P0 / 1 | Double-click Mac application | Native window; Codex login, model and connection checks; USB/BLE selection; optional verified model download or reuse; no Python or ESP-IDF required by packaged-app users | Implemented; Mac window and live card sync verified |
| P0 / 2 | BLE recovery and actionable errors | Reconnect the original device; distinguish power/permissions/pairing/protocol faults; retain ready drafts and in-memory dedupe; discard partial audio; never resend uncertain operations | Implemented; host regression and one physical power-cycle recovery passed, confirmed by user |
| P1 | Clear recording feedback | Preparation/ready/recording/transcribing states, text plus color, lightweight level indicator, optional sound; preserve confirmation before sending | User confirmed P1 meter and recognition; batch 006 stable hint passed host/LVGL checks, new hint and sound still need device acceptance |
| P1 | Conversation visibility | Recent actual interactions, active/queued/needs-desktop/unread status | Implemented; three rows and card read receipts; device acceptance pending |
| P1 | Completion and attention alerts | Deduplicate, rate-limit, quiet hours, mute; no playback during recording | Implemented; silent default, UTC+8 22:00–08:00 quiet; device acceptance pending |
| P2 | Quota pacing hint | Optional heuristic based on remaining quota and elapsed period; preserve the fixed weekly page, automatic reset and two opportunity expiry dates | Backlog |
| P2 | Persistent display settings | Brightness, sound and screen timeout | Backlog |
| P2 | Optional tap-to-record | Tap start/stop alongside hold-to-record | Backlog |
| P2 | Version guidance | Compare the card with bundled/selected firmware and show upgrades | Local comparison implemented; online release checks pending |
| Deferred | Card approvals | Requires a separately reviewed permission flow | Not scheduled |
| Deferred | Phone companion | Additional platform maintenance and pairing work | Not scheduled |
| Deferred | Elaborate animations | Requires measured RAM and performance budget | Not scheduled |

## 2026-10-03 code-review follow-ups

| Priority | Work | Status |
| --- | --- | --- |
| P1 | Decouple draft standby from battery sampling | Implemented in batch 015; host/LVGL pass, hardware pending |
| P1 | Isolate quota failures and label cached data | Batch 015 fallback and batch 016 asynchronous refresh implemented; slow-response/strict send checks pass, hardware pending |
| P2 | Distinguish Bluetooth scan, permission, connection, authentication and notification failures | Batch 016 implemented; fault injection passes, hardware pending |
| P2 | Separate service/controller responsibilities and share request dispatch while preserving access differences | Pending; incremental cleanup alongside related features |
| P3 | Indexed battery history with CSV export | Pending; address as long-term history grows |

## References

- [Community companion](https://ai-passport.folotoy.cn/plays/270/): desktop onboarding, reconnect, notification controls.
- [Codex Passport](https://ai-passport.folotoy.cn/plays/343/): quota pacing, recent threads, bounded alerts.
- [OpenClaw Android](https://ai-passport.folotoy.cn/plays/799/): distinct preparation/recording feedback and matched versions.
- [Codex Voice](https://ai-passport.folotoy.cn/plays/540/): voice controls and conversation navigation.
- [Codex Buddy](https://ai-passport.folotoy.cn/plays/96/): completion feedback and desktop integration.

These are design references, not imported implementations. See the
[Mac application guide](codex-desktop.md) for P0 and P1 changes and their limits.
