"""Fail packaging if a profile silently enabled the wrong radio or application."""
from pathlib import Path
import sys
import subprocess

settings = dict(line.split("=", 1) for line in Path(sys.argv[1]).read_text().splitlines()
                if line.startswith("CONFIG_") and "=" in line)
profile = sys.argv[2]
for name in ("wifi", "usb", "ble", "offline"):
    assert (settings.get("CONFIG_PASSPORT_MODE_"+name.upper()) == "y") == (name == profile), name
assert (settings.get("CONFIG_BT_ENABLED") == "y") == (profile == "ble")
# ESP_WIFI_ENABLED is a hidden SoC capability flag (always y on C3), not a
# radio switch. Verify the linked executable instead of claiming it disables Wi-Fi.
symbols = {line.split()[-1] for line in subprocess.check_output(
    ["riscv32-esp-elf-nm", "--defined-only", sys.argv[3]], text=True).splitlines() if line.split()}
assert ("esp_wifi_init" in symbols) == (profile == "wifi")
assert ("nimble_port_init" in symbols) == (profile == "ble")
assert ("cp_offline_run" in symbols) == (profile == "offline")
assert ("cp_runtime_start" in symbols) == (profile != "offline")
if profile == "usb":
    assert settings.get("CONFIG_ESP_CONSOLE_NONE") == "y"
if profile == "ble":
    assert settings.get("CONFIG_BT_NIMBLE_NVS_PERSIST") == "y"
    assert settings.get("CONFIG_BT_NIMBLE_SM_SC") == "y"
print(f"Profile {profile}: PASS")
