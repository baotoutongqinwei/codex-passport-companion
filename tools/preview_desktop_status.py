#!/usr/bin/env python3
"""Render native desktop states with synthetic data and no device/account I/O."""
import argparse
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
import AppKit as A
import desktop
from desktop_controller import DesktopController
from service import Companion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("build/desktop-status-preview"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyProhibited)
    with tempfile.TemporaryDirectory() as directory, \
         patch.object(desktop, "data_root", return_value=Path(directory)), \
         patch.object(DesktopController, "doctor"), \
         patch.object(DesktopController, "start_clock_sync"):
        view = desktop.WindowDelegate.alloc().init()
        view.applicationDidFinishLaunching_(None)
        view.timer.invalidate()
        controller = view.controller
        # No RPC object: the preview may only read locally supplied fixtures.
        service = controller.service = Companion(None, directory)
        try:
            service.device_report(dict(schema=1, chip="ESP32-C3", profile="ble", firmware="0.10.1",
                elf_sha256="a"*64, heap_total=200000, heap_free=80000, heap_min=65000,
                heap_largest=40000, app_used=2700000, app_capacity=8323072,
                battery_pct=76, battery_mv=3960, die_c=34.5, uptime_s=7200, psram_bytes=0))
            service.draft = {"state": "ready"}
            controller.update(codex="本机已就绪 · 示例", account="ChatGPT · 示例账户",
                              connection="蓝牙 · 示例卡片")
            cases = (("draft", "ready", "草稿待确认 · 设备采样继续刷新（示例数据）", 4),
                     ("bluetooth-error", "error", "连续三次失败，已暂停。无法连接卡片，请检查电源、距离及是否被其他程序占用", 0))
            for name, state, detail, page in cases:
                for theme, appearance in (("dark", A.NSAppearanceNameDarkAqua), ("light", A.NSAppearanceNameAqua)):
                    controller.update(state=state, detail=detail)
                    view.window.setAppearance_(A.NSAppearance.appearanceNamed_(appearance))
                    view.show_page(page)
                    view.refresh_(None)
                    if name == "draft": assert controller.snapshot()["device"]["fresh"]
                    view.window.displayIfNeeded()
                    rep = view.root.bitmapImageRepForCachingDisplayInRect_(view.root.bounds())
                    view.root.cacheDisplayInRect_toBitmapImageRep_(view.root.bounds(), rep)
                    data = rep.representationUsingType_properties_(A.NSBitmapImageFileTypePNG, {})
                    assert data.writeToFile_atomically_(str(args.output/f"desktop-{name}-{theme}.png"), True)
        finally:
            service.rpc = type("ClosedPreviewRpc", (), {"close": lambda self: None})()
            service.close()
            view.window.setDelegate_(None)
            view.window.close()
    print("Native desktop: retained-draft monitoring and Bluetooth failure, light/dark PASS")


if __name__ == "__main__":
    main()
