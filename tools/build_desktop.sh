#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python="${PASSPORT_PYTHON:-.local/transport-venv/bin/python}"
if [[ ! -x "$python" ]]; then
    echo "Install bridge/desktop-requirements.txt in a Python virtual environment first." >&2
    exit 1
fi
"$python" -m PyInstaller --noconfirm --clean --distpath build/desktop --workpath build/desktop-work bridge/desktop.spec
codesign --verify --deep --strict "build/desktop/Codex Passport.app"
echo 'Desktop app: build/desktop/Codex Passport.app'
