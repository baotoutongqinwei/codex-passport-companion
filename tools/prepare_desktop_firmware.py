#!/usr/bin/env python3
"""Package only verified, standard-layout firmware for the desktop picker."""
import hashlib
import json
from pathlib import Path
import sys

from archive_firmware import verify_archive

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
from firmware import inspect_firmware


def main():
    out = ROOT / "build/desktop-firmware"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for profile in ("ble", "usb", "offline", "wifi"):
        path = ROOT / f"build/variants/{profile}/FoloToy-AI-Passport-full.bin"
        if not path.is_file():
            raise SystemExit("Build all profiles with tools/build_variants.sh before packaging the desktop app.")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        manifest = verify_archive(ROOT / "build/firmware" / digest)
        inspected = inspect_firmware(path)
        if inspected["sha256"] != digest or inspected["descriptor"] != manifest["app_descriptor"]:
            raise ValueError("Firmware changed during verification")
        (out / f"{profile}.bin").write_bytes(data)
        if inspected["profile"] != profile:
            raise ValueError(f"Firmware mode marker mismatch: {profile}")
        rows.append({"profile": profile, "sha256": digest, "version": inspected["descriptor"]["version"],
                     "elf_sha256": manifest["app_elf_sha256"]})
    (out / "catalog.json").write_text(json.dumps(rows, indent=2) + "\n")
    print("Desktop firmware: four verified profiles, no NVS/PHY payloads")


if __name__ == "__main__":
    main()
