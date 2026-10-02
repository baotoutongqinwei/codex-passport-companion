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
| P1 | Clear recording feedback | Preparation/ready/recording/transcribing states, text plus color, lightweight level indicator, optional sound; preserve confirmation before sending | Implemented; host and actual LVGL checks; device acceptance pending |
| P1 | Conversation visibility | Recent actual interactions, active/queued/needs-desktop/unread status | Implemented; three rows and card read receipts; device acceptance pending |
| P1 | Completion and attention alerts | Deduplicate, rate-limit, quiet hours, mute; no playback during recording | Implemented; silent default, UTC+8 22:00–08:00 quiet; device acceptance pending |
| P2 | Quota pacing hint | Optional heuristic based on remaining quota and elapsed period; preserve the fixed weekly page, automatic reset and two opportunity expiry dates | Backlog |
| P2 | Persistent display settings | Brightness, sound and screen timeout | Backlog |
| P2 | Optional tap-to-record | Tap start/stop alongside hold-to-record | Backlog |
| P2 | Version guidance | Compatible host/firmware version display and update instructions | Backlog |
| Deferred | Card approvals | Requires a separately reviewed permission flow | Not scheduled |
| Deferred | Phone companion | Additional platform maintenance and pairing work | Not scheduled |
| Deferred | Elaborate animations | Requires measured RAM and performance budget | Not scheduled |

## References

- [Community companion](https://ai-passport.folotoy.cn/plays/270/): desktop onboarding, reconnect, notification controls.
- [Codex Passport](https://ai-passport.folotoy.cn/plays/343/): quota pacing, recent threads, bounded alerts.
- [OpenClaw Android](https://ai-passport.folotoy.cn/plays/799/): distinct preparation/recording feedback and matched versions.
- [Codex Voice](https://ai-passport.folotoy.cn/plays/540/): voice controls and conversation navigation.
- [Codex Buddy](https://ai-passport.folotoy.cn/plays/96/): completion feedback and desktop integration.

These are design references, not imported implementations. See the
[Mac application guide](codex-desktop.md) for P0 and P1 changes and their limits.
