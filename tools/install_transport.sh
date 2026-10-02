#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m venv "${root}/.local/transport-venv"
"${root}/.local/transport-venv/bin/python" -m pip --isolated install --no-user --index-url https://pypi.org/simple -r "${root}/bridge/requirements.txt"
"${root}/.local/transport-venv/bin/python" -c 'import serial, bleak; from opencc import OpenCC; assert OpenCC("t2s").convert("語音識別") == "语音识别"; print("USB/BLE and Simplified Chinese dependencies: PASS")'
