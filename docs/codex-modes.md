[简体中文](codex-modes.zh_CN.md) · **English**

# Choose a Codex card mode

All sources live in the same application checkout on `feature/codex-companion`.
Four separate firmware profiles keep radio stacks and application state bounded
on the ESP32-C3 (8 MB Flash, no PSRAM). Choose a mode before flashing; the card
does not switch installed applications at runtime. No new paid API, hosted
transcription, relay subscription or automatic paid fallback is used. Codex
still needs the existing account's available quota and Internet on the Mac.

| Profile | Card connection | Mac program | Features |
| --- | --- | --- | --- |
| `wifi` | Same 2.4 GHz LAN as Mac | `serve` | Quota, conversations, replies, voice, UTC+8 clock |
| `usb` | USB data cable throughout use | `usb` | Same Codex features; no listening network port |
| `ble` | Authenticated Bluetooth LE | `ble` | Same features; compressed voice, no listening network port |
| `offline` | None; USB only for power/flashing | None | Manual UTC+8 clock, battery, 25/5 Pomodoro, stopwatch |

The three connected profiles share a fixed quota screen: 7-day remaining
percentage, next automatic reset, and the earliest two available reset-opportunity
expiry dates in UTC+8, 24-hour format. Missing details stay explicit; the card
never consumes a reset opportunity. Middle opens conversations; hold down opens
connection instructions. Short up/down do not page or scroll the quota screen.

USB and BLE still need a local Mac helper and an awake Mac; only the offline
profile is independent. A home network or phone hotspot is another connection
option for the existing Wi-Fi profile, provided its clients can communicate.
Corporate endpoint/peripheral policy may still restrict any transport. These
profiles do not change the Mac firewall, VPN or company security software.

Device checkpoint (2026-10-02): the quota-page BLE image was flashed with the
user's approval using three verified segments, preserving NVS/PHY. The first
pairing attempt failed; retrying completed authenticated pairing. Real BLE
traffic then passed at MTU 247, returning clock, weekly quota, reset expirations
and conversation listings. During a bounded startup observation the matching ELF
prefix was `83848bfcb`, free heap 55,768 bytes, largest block 47,104 bytes, with no
observed panic marker. Cable-free use, physical screen/keys, voice throughput,
bond persistence across reboot and reconnect behavior still need acceptance.
Full image SHA-256: `f9b278a35146543061e8151473a3b96a21a0c99eed4f5058ab004b1d50e52503`.

After automatic screen-off, briefly press any of the three function buttons;
the first press only wakes the display. The separate hardware power button
controls device power and may interrupt USB or restart the card. Use it for
power control, not routine display wake-up.

## Install and launch

For USB/BLE on macOS, start with the [native desktop app](codex-desktop.md).
It needs no developer toolchain. The commands below describe the original
development workspace; on a fresh machine follow the repository root README
to prepare the virtual environment and speech engine instead of sourcing a
machine-specific activation script.

```bash
source ~/aipassport/activate.sh
cd ~/aipassport/codex-companion
bash tools/install_transport.sh
bash bridge/start.command
```

The launcher offers Wi-Fi, USB, Bluetooth and read-only diagnostics. Dependencies
are pinned in `bridge/requirements.txt` and isolated in `.local/transport-venv`.
On a fresh machine also run `python3 tools/bootstrap_bridge.py` once to install
the free local speech engine/model. Existing Codex login is required; no API
key is requested. Use only one transport helper per card to avoid competing
drafts. Keep the terminal open; Ctrl+C stops it. Firmware switching requires
separately authorized flashing, not just selecting a launcher item.

### USB

After the USB profile has been flashed, connect a data cable and select USB in
the launcher. A single ESP32-C3 USB port is auto-selected; with multiple cards:

```bash
.local/transport-venv/bin/python bridge/app.py usb --port /dev/cu.usbmodem101
```

The port name can change. Stop serial monitors/configuration tools first. No
SSID, password or TLS configuration is needed. USB console logs are disabled in
this firmware because framing owns the serial channel. The host parser skips
ROM boot text, checks CRC/lengths, and pairs responses with request IDs. On cable
failure, discard interrupted recordings and check the computer before resending
an uncertain action. The helper now waits and reconnects only to the original
card's USB serial number, including when its port name changes. Partial audio
is discarded; pending confirmations and send deduplication remain in memory.
It never automatically replays a send. Keep the helper running while reconnecting.

### Bluetooth LE

Flash the BLE profile, enable Mac Bluetooth and select Bluetooth in the launcher.
Allow the terminal/Python process in macOS Bluetooth privacy settings if prompted.
The app scans only the custom CodexCard service. With multiple cards:

```bash
.local/transport-venv/bin/python bridge/app.py ble-scan
.local/transport-venv/bin/python bridge/app.py ble --address <device-identifier>
```

macOS identifiers are UUIDs, not MAC addresses. The authenticated characteristic
read triggers the macOS pairing dialog: enter the six-digit code displayed on
the card. Pairing uses LE Secure Connections with MITM protection and persistent
bonds (maximum three). Only authenticated encrypted connections carry card data.
The PIN wakes and keeps the screen lit. To reset trust, open connection instructions
from the quota page, **hold middle to clear all card BLE bonds**, then forget the
old CodexCard entry on the Mac and reconnect. Merely forgetting the Mac entry
does not erase the card's stored bond. No other NVS settings are erased.

Voice uses independent IMA ADPCM blocks, about a quarter of PCM size. The Mac
decodes them before the existing local speech recognizer. If negotiated MTU is
below 128, voice is unavailable while text/quotas still work. Disconnects or slow
audio transfers abort the recording; there is no silent paid fallback or auto-send.
Later acceptance passed a 45-second BLE recording on the earlier helper and
one native-app card power-cycle recovery. Sustained RF interference, range,
fresh-machine pairing and microphone quality across environments remain unverified.
Bluetooth pairing and client behavior follow [Bleak's macOS documentation](https://bleak.readthedocs.io/en/stable/backends/macos.html).

## Fully offline controls

| Page/action | Controls |
| --- | --- |
| Change tool | Up/down cycles clock → Pomodoro → stopwatch; timers keep running |
| Set clock | Middle enters hours, then minutes, then saves; up/down adjusts; hold up cancels |
| Pomodoro | Middle starts/pauses; after completion, middle starts the next 5-minute rest or 25-minute focus |
| Reset Pomodoro | Hold middle resets the session and completed-round count |
| Stopwatch | Middle starts/pauses/resumes; hold middle clears |
| Sleep/wake | After 60 seconds the backlight turns off; first press only wakes; focus completion wakes the display |

Clock is 24-hour UTC+8, with seconds at top left on every page. Enter the current
UTC+8 time manually; seconds start at zero. It continues during display sleep.
Power loss/reboot resets clock and timers because no battery-backed RTC is
assumed; `--:--:--` clearly indicates the need to set time. Pomodoro completion
is a visual indication and waits for confirmation, without automatically starting
another phase. No Codex, speech recognition, conversations or quota exist offline.

## Build, verification and protocol

```bash
bash tools/build_variants.sh
bash tools/preview_companion.sh
# Rebuild one profile independently:
bash tools/validate.sh --all --profile usb
```

Each image is `build/variants/<profile>/FoloToy-AI-Passport-full.bin`, flashed at
`0x0`, with size report alongside it. Its SHA-256 selects the matching verified
`build/firmware/<sha256>/` ELF/MAP bundle. The top-level merged image remains the
Wi-Fi profile for compatibility. Use the variant path explicitly when selecting
another image. Merged flashing may reset configuration; review the
[stored-data policy](development/engineering/firmware-layout.md) and obtain approval.

The gate verifies the linked ELF includes only the selected application's radio
initialization routines. `CONFIG_ESP_WIFI_ENABLED` is a hidden SoC capability
flag, so it cannot be used as proof Wi-Fi is running or absent. Linker memory
remainder is not runtime free heap; radio, audio and task allocations need board
measurement. All profiles reuse the same Chinese bitmap font and BSP.

CPv1 frames: 16-byte header (`CPv1`, u32 ID, u16 status, u16 UTF-8 path length,
u32 body length), path, body and IEEE CRC32; integers little-endian. Status zero
means request; responses use 200–599 and an empty path. Path ≤1536 bytes,
body ≤8192, request body ≤4096. Card requests are sequential; responses have a
30-second timeout and stale IDs are discarded. Framing is not authentication:
USB trusts the physically connected computer; BLE separately authenticates peers.
ADPCM bodies contain u16 sample count, i16 predictor, u8 step index, zero reserved
byte, then one nibble per sample (low first, including sample zero); at most 2048
samples. Blocks are independently decodable and checked before writing audio.

Host tests cover actual C/Python codec interoperability, corrupted/oversized data,
fragmented PTY round trips, simulated authenticated BLE, idempotent sends, local
compressed Mandarin transcription, offline timing and real LVGL/font rendering.
They do not establish hardware acceptance. New firmware device tests require
explicit approval and should include 45-second voice, disconnects, low battery,
button release, Chinese layout, bond persistence, clock sync and desktop-thread
send/reply behavior. See [the common companion guide](codex-companion.md).
