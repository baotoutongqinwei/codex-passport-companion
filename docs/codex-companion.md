[简体中文](codex-companion.zh_CN.md) · **English**

# Codex Passport companion

An independent 240×320 interface for an existing signed-in Codex account. The
card reuses the BSP and connects to a Mac over Wi-Fi, USB or authenticated BLE,
depending on the installed firmware. Codex and offline speech recognition run
on the Mac. A fourth firmware runs a clock, Pomodoro and stopwatch independently.
See [mode selection, setup and controls](codex-modes.md). The shared Codex
features below apply to the three companion profiles, not the offline tools.

## Features and limits

| Feature | Behavior |
| --- | --- |
| Clock | Top-left on every page, fixed UTC+8, 24-hour `HH:MM:SS`, updated every second. Synced from the Mac's Unix time, independent of its display timezone. Until the first successful sync after boot: `--:--:--`. After a disconnect, the local clock continues; idle screen-off behavior is unchanged. |
| Quota | One fixed screen: 7-day remaining percentage, next automatic reset, and the earliest two available reset-opportunity expiry dates. All dates use UTC+8 and 24-hour time. No long-term quota or monetary credit balance is shown. Unknown/missing details stay explicit. Refresh every 30 seconds; quota events invalidate the cache. Reset opportunities are read only, never consumed by the card. |
| Conversations | Three local Codex conversations per page, sorted by actual interaction recency, with status, tracked pending counts and card unread markers. Select and page through messages, jump to the latest reply. This is not a ChatGPT cloud chat client. |
| Replies | Bridge polls every 1.5 seconds; history cache lasts 5 seconds. Turns started through the bridge also receive text delta events. Long replies are paginated. |
| Voice | Hold the middle button, release to finish, review text, then click to send. Up to 45 seconds, 16 kHz mono PCM; buffer on the card is 8 KB. Recognition defaults to Chinese; local conversion normalizes the preview and sent text to Simplified Chinese. |
| Cost | No hosted transcription, API-key login, purchase or paid fallback. Only the signed-in ChatGPT account and its available quota are used. Unknown/exhausted quota and other providers block sends. Existing subscription terms still apply. |
| Busy conversations | If the thread is active or another client owns its writer, add confirmed text to the original thread's Codex queue. Additional recordings can be confirmed into the same queue. The helper tracks up to 32 pending voice messages per session across conversations, showing the selected conversation's pending count. Queue acceptance does not mean execution; check the desktop app. |
| Permissions | Tool approval requests are declined; the card indicates that the computer is needed. The bridge does not grant permissions or forward approval dialogs into the desktop app. |
| Errors | Interrupted recordings are discarded. Explicit send/queue rejection keeps the draft ready. A send/queue timeout is marked uncertain and is never automatically retried. Check the computer before recording the same request again. |
| Chinese | Shipped 16 px bitmap font covers ASCII, U+4E00–U+9FEF and selected punctuation. Unsupported characters, including emoji and CJK extensions, become `?`. |

The bridge is a separate `codex app-server` process using the desktop app's
installed binary and account. This installation rejects resuming a thread owned
by the desktop with `thread already has an active writer`. The helper uses the
installed protocol's `thread/queue/add` on that explicit rejection, without
taking the writer lock, starting the queued turn itself, or changing permissions.
An active thread also uses this queue route. Each confirmed recording has its
own deduplication ID. Further recordings are appended while earlier tracked
messages remain queued, even if the thread briefly reports idle. Queue rejection
or the tracking limit retains the draft; uncertain results are never retried
automatically. Entries are removed from tracking only after a complete queue
read confirms their absence; that absence alone does not prove execution.
Tracking is in memory; after restarting the helper, check the desktop queue.
The queue API is version-dependent. One real USB voice/queue/desktop/card reply
round trip has passed. A later four-message USB test had two simultaneously pending
messages and delivered all four in order to the desktop; card replies for that
multi-message run remain unconfirmed. Threads using desktop-specific dynamic tools may require the
desktop. Do not expect approval prompts to be mirrored automatically.

## Start on this workspace

For a packaged Mac window and first-run checks, see the [desktop guide](codex-desktop.md).
The [prioritized improvement list](codex-improvements.md) tracks subsequent work.

P1 update, 2026-10-02: recording phases and a relative level meter, three conversation rows
sorted by actual interaction, card unread markers, and completion/attention alerts with mute
and quiet hours are implemented. See the [desktop guide](codex-desktop.md#recording-conversations-and-alerts)
for use and observation limits. The 68 companion host tests, actual LVGL layout and 200 page
switches passed (6,048 bytes free in the 32 KB pool), as did read-only local Codex integration
and Mac settings-window checks. P1 was subsequently flashed and the user confirmed that
the meter and recognition work. Batch 006 replaces amplitude-dependent hints with a stable
listening message; that new firmware still needs device acceptance. See the
[numbered updates](codex-updates.md) for current results and remaining checks.

Earlier P0 desktop update, 2026-10-02: a native ARM64 Mac app now provides account/model
checks, USB/BLE controls and on-demand verified model installation or reuse.
BLE reconnect keeps the original device, service, drafts and deduplication.
The 54 companion host tests and full BLE validation gate passed. The packaged
window, Chinese text, existing-model reuse, bundled speech engine and live card
state synchronization were exercised on this Mac. One physical power-cycle
automatically reconnected, and the user confirmed time/quota recovery.
Clean-Mac installation/permissions and long sleep/wake remain unverified.
The rebuilt BLE merged image is `e74eefcee67c7a60da61dde5e389682aa6fbce297ab6974ca769829cf558dc95`,
matching ELF `c2170085163c8e28b7f23b643c424aac9a2c2ee570b968367ca38f4547339922`.
Firmware behavior is unchanged and this rebuild was not flashed. Older device
records below describe their specific historical versions. Subsequent BLE audio
tests on the earlier installed image received 6.176 and 45 seconds without
transport errors and delivered both confirmed voice messages to the desktop.

```bash
source ~/aipassport/activate.sh
cd ~/aipassport/codex-companion
python3 bridge/app.py doctor
```

The offline engine and model are already installed on the development Mac. For
a fresh checkout, run `python3 tools/bootstrap_bridge.py` after activating the
toolchain. It downloads the MIT-licensed whisper.cpp v1.8.7 at commit
`48f628a84833905ee4a0658ee6d4a5c915ce1997` and a multilingual base model, verifies
the model hash, and builds a CPU backend. This requires a one-time download,
disk space and a C/C++ compiler, but no paid account or speech API.

Chinese conversion uses [opencc-python-reimplemented 0.1.7](https://pypi.org/project/opencc-python-reimplemented/0.1.7/)
(Apache License), with the offline `t2s` dictionary. Both bootstrap and
`tools/install_transport.sh` install this pinned dependency; the latter prepares
the launcher's virtual environment. Install it in the active Python environment
before running the host test gate. Conversion runs before the length/font checks,
so the card preview and confirmed outgoing text are identical. Missing conversion
support makes speech unavailable instead of silently showing Traditional Chinese.

```bash
# One time: use the Mac's LAN IPv4 address, preferably a DHCP reservation.
python3 bridge/app.py setup --host <Mac-LAN-IP>
python3 bridge/app.py serve
```

Leave the bridge terminal running. Allow local network access if macOS asks.
Once configured, `bridge/start.command` offers a mode menu from Finder; select Wi-Fi.
The pairing token, certificate and private key stay in ignored `.local/`.
They are not included in firmware or the source package. Changing the Mac's IP
requires creating a new certificate/configuration and reconfiguring the card;
preserve the old three pairing files until the new setup works. Do not expose
the bridge port to the Internet.

After explicitly approving and completing flashing, in another activated
terminal run:

```bash
cd ~/aipassport/codex-companion
python3 bridge/app.py configure --port /dev/cu.usbmodem101
```

The serial device name can change. The command asks locally for the 2.4 GHz
WPA2/WPA3-compatible Wi-Fi name and password without echoing the password. It
saves credentials, the pinned certificate, token and initial clock in NVS and
restarts the card. This command does not flash. Never send the password in chat.

## Three-button controls

| Page | Controls |
| --- | --- |
| Quota | Middle: conversations; hold down: connection instructions. Short up/down do not page or scroll. |
| Conversations | Up/down: selection; middle: open; hold down: next page; hold up: quota |
| Conversation | Up/down: message pages; hold down: latest; middle: menu; hold middle: record |
| Recording | Release middle: finish and transcribe; hold up: cancel |
| Transcript | Up/down: scroll; middle: send only when ready; hold up: cancel |
| Idle screen | Backlight turns off after 60 seconds; a button wakes it without triggering an action |

## Build and validation

```bash
./tools/validate.sh
bash tools/preview_companion.sh
python3 tools/archive_firmware.py verify build/firmware/<image-sha256>
```

The complete gate includes the baseline tests plus bounded UTF-8/URL handling,
font coverage, pagination, recording sequence/expiry/cancellation, frozen voice
target, quota restrictions, duplicate-send protection and a real local TLS
round trip. The preview compiles the real UI against LVGL with a 32 KB allocator
and saves quota, conversation, recording-phase and alert PPM frames under `build/ui-preview/images/`. It is not hardware
acceptance. The firmware gate creates the merged image for offset `0x0` and a
matching ELF/MAP archive. Flashing replaces the current application and may
reset saved data; obtain explicit approval first.

On-device checks still required: Chinese layout/scrolling; ADC press/release;
microphone volume and 45-second recording; Wi-Fi/TLS under heap pressure;
disconnect/reconnect; clock sync, second ticks and midnight rollover; quota freshness; sending to an existing conversation;
reply streaming; reset/pairing persistence and idle/wake behavior. Runtime logs
include free heap, largest block, minimum heap and network stack watermark.
Do not archive logs containing personal conversation text or credentials.

See the [font provenance](../assets/fonts/README.md) and
[firmware/data policy](development/engineering/firmware-layout.md).

## Development checkpoint — 2026-10-02

Latest quota-page increment: the installed read-only API returned one weekly
window and four available reset opportunities. Details are filtered to available
Codex resets and sorted by future expiry; at most two dates are sent without IDs.
Missing/capped details are marked incomplete; no expiry date is invented.
Host tests and six actual LVGL quota states passed, including calendar boundaries,
one-screen controls and 200 page switches (8,464 bytes free in the 32 KB pool).
The Mac helper now returns both dates over USB; no reset was consumed and no
speech model was changed. The user authorized the new USB image: segmented
flashing verified all three written images without erasing NVS/PHY. A 12-second
receive-only startup check saw a valid state-request frame; after restoring the
Mac helper, four state requests succeeded with clock, weekly quota and two expiry
dates, with no errors. Firmware console logs are disabled; this does not prove
absence of runtime faults. Screen appearance and button acceptance remain pending.
USB complete gate: PASS; merged SHA-256
`9b250caf2d8db7b831a8d1b4b198987f936472ded4e0aa86407030af1c9b7ce3`;
matching ELF `37beaf064ba1e01023c0b7a989315e92dd74847d20cbd0e527767273ab994fde`.
The physical test records below refer to earlier images, not this new quota screen.

Accepted scope: no added paid services; Wi-Fi, USB and authenticated BLE companion
profiles plus independent clock/Pomodoro/stopwatch; UTC+8 and Chinese font in all
profiles. All source remains local on `feature/codex-companion`, without commit
or publication. Each variant is packaged separately; flashing requires a fresh
selection and confirmation. Exact image and matching ELF hashes are in the
delivered variant manifests rather than copied from an earlier build.

The earlier Wi-Fi clock image (`adc9ee132bdaf833cd217a593e3cd278b4780859b7a04255b71fa83c49fc1dba`)
was successfully flashed with authorization and joined Wi-Fi. The card-to-Mac
connection timed out, so successful live card quota/reply/clock sync was not
established. This is a managed corporate Mac with network filters; the exact
blocking component is unproven. No security settings were changed.

Host validation includes actual C/Python framing, PTY USB, mocked BLE, offline
timer logic, full Chinese coverage and real LVGL rendering. Companion UI passed
200 stress cycles with 9,240 pool bytes free; offline UI passed 500 cycles with
17,672 free. A real Mac read-only smoke test transferred 85 compressed Mandarin
blocks (172,180 PCM bytes → 43,555 bytes), decoded and transcribed them locally,
read Codex conversations/quota/time, and submitted zero prompts.

USB device update, 2026-10-02: explicitly authorized and flashed the verified USB
build on `/dev/cu.usbmodem101`. Merged image identity:
`1f4bc6741636e0a552ead950b704f18b8d94886f829380334ee5dd198a07babe`;
matching ELF: `cb86156fd692c353acea66eeed8c504aa21ed1ad9815edef92ac6f6e9b99c704`.
Identical old/new partition tables allowed segmented writes at 0x0, 0x8000 and
0x10000 without overwriting NVS or PHY data. All three write hashes passed.
The card then completed over 30 real USB state exchanges without errors; the
responses contained time, quota, conversations and local-ASR availability. USB
console logs are disabled, so framed traffic was observed instead of a text
serial monitor. The Mac USB helper remains running; the former Wi-Fi helper
was stopped.

Device tests: USB flashing and bidirectional state transport PASS; display and
button acceptance pending user observation. Microphone quality, 45-second
capture, runtime RAM/stack margins, battery life, timer accuracy and existing
desktop-thread send/reply remain unverified. BLE and offline firmware hardware
tests have not run. No prompts were sent during this USB check.

USB reconnect correction: the user reported loss after the card's automatic
screen-off while the Mac remained active. The host logged `Device not configured`
and exited; the same USB device was subsequently enumerated. The screen-off
implementation only changes backlight PWM, and no matching Mac sleep was found;
the initial device disappearance remains unexplained. The host now reconnects
by the original card's USB serial number and discards partial audio while
preserving draft/send deduplication. Tests cover changed port, another card,
partial recording cleanup and a lost send response without duplicate execution.
This is a host-only fix; the flashed USB firmware and ELF identities are unchanged.

The user subsequently confirmed normal automatic screen-off/wake with a function
button, and clarified that the earlier wake attempt used the separate hardware
power button. That provides a likely explanation for USB re-enumeration, though
no reset-reason telemetry was captured. The hardware power button is separate
from the three BSP function buttons; routine display wake uses a function button.

USB audio correction, 2026-10-02: the host received audio chunks, but fixed
512-byte pyserial reads waited for a 200 ms timeout on short frame tails. A local
PTY test using real pyserial measured a median 207 ms acknowledgment and 9.9 kB/s,
below the microphone's 32 kB/s PCM rate. Reading only queued bytes (or waiting for
one byte when idle) reduced the same test to about 1 ms. A regression test covers
1,024/2,048-byte PCM chunks and requires acknowledgments without timeout padding.
Host static checks pass; firmware is unchanged. These are host measurements;
physical microphone transcription and sustained 45-second recording still need
device acceptance.

Voice device update: the user confirmed successful microphone transcription.
Observed transport: 114 audio chunks, 117,760 PCM bytes (3.68 seconds), a nonzero
microphone signal, and a ready transcript. The subsequent send failed before
`turn/start` because the desktop owned the writer. Queue fallback and explicit
RPC-rejection handling are covered by host tests; real desktop queue dispatch
and reply return remain pending. No synthetic prompt was sent to test this path.

Follow-up correction: the actual installed server error is
`thread <thread-id> already has an active writer` (JSON-RPC code -32600), while
the first matcher and test omitted the identifier. Consequently the previous
device retry never reached the queue API. The matcher now accepts both forms;
a live resume rejection confirmed it is recognized, without starting a turn.
Regression tests cover that exact shape, transport uncertainty, and identical
Simplified Chinese preview/queued text. A real local synthetic-audio check of
Whisper (`zh`) plus OpenCC passed. Actual desktop queue dispatch remains pending.

USB send acceptance: a subsequent physical recording transferred 189,440 PCM
bytes (5.92 seconds) in 184 chunks, with zero device-facing errors. The writer
rejection was recognized and exactly one `thread/queue/add` succeeded; the
transcribed message then appeared in the intended desktop conversation. This
confirms microphone-to-transcript-to-queue-to-desktop delivery for this attempt.
The user then confirmed that the test reply appeared on the card, completing
this physical voice/text/queue/desktop/reply round trip. Sustained 45-second
capture remains unverified. The acceptance record stores metadata only, not the
spoken content.
