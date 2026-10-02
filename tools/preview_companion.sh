#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cmake -S "${root}/tests/companion_ui" -B "${root}/build/ui-preview" -DCMAKE_BUILD_TYPE=Debug
cmake --build "${root}/build/ui-preview" -j 4
mkdir -p "${root}/build/ui-preview/images"
"${root}/build/ui-preview/companion_ui_preview" "${root}/build/ui-preview/images"
"${root}/build/ui-preview/offline_ui_preview" "${root}/build/ui-preview/images"
