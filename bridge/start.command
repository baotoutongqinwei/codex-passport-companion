#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
python=".local/transport-venv/bin/python"
[[ -x "$python" ]] || python=python3
mode="${1:-}"
if [[ -z "$mode" ]]; then
    echo "1. Wi-Fi   2. USB 数据线   3. 蓝牙   4. 只读诊断"
    read -r -p "选择模式 [2]：" choice
    case "${choice:-2}" in
        1) mode=serve ;; 2) mode=usb ;; 3) mode=ble ;; 4) mode=doctor ;;
        *) echo "无效选择"; exit 2 ;;
    esac
fi
exec "$python" bridge/app.py "$mode"
