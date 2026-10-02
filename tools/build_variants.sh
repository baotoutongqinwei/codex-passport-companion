#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
bash tools/validate.sh --all --profile wifi
for profile in usb ble offline; do
    bash tools/validate.sh --firmware --profile "$profile"
done
