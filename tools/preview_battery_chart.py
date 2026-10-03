#!/usr/bin/env python3
"""Render the real battery window with public fixtures; never access a device."""
import argparse
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"bridge"))
import AppKit as A
from battery_history import save_battery
from battery_chart_view import BatteryHistoryWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("build/battery-preview"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyProhibited)
    with tempfile.TemporaryDirectory() as directory:
        now = int(time.time())
        samples = []
        for index in range(288):
            if 95 <= index <= 125:
                continue  # A visible gap demonstrates missing data without interpolation.
            percent = max(0, 100-int(index*.30))
            samples.append((index+1, now-(288-index)*300, index*300, percent, 3300+percent*8))
        save_battery(directory, "DEMO-CARD · 示例数据", (1, samples))
        view = BatteryHistoryWindow.alloc().init().setup(directory)
        view.checked = time.monotonic()
        view.load()
        view.refresh_(None)
        assert view.card_ids == ["DEMO-CARD · 示例数据"]
        for name, appearance, days in (("dark", A.NSAppearanceNameDarkAqua, 0),
                                       ("light", A.NSAppearanceNameAqua, 0),
                                       ("week", A.NSAppearanceNameDarkAqua, 1),
                                       ("empty", A.NSAppearanceNameAqua, 0)):
            if name == "empty": view.cards = {}
            view.window.setAppearance_(A.NSAppearance.appearanceNamed_(appearance))
            view.range.setSelectedSegment_(days)
            view.render()
            view.window.displayIfNeeded()
            rep = view.root.bitmapImageRepForCachingDisplayInRect_(view.root.bounds())
            view.root.cacheDisplayInRect_toBitmapImageRep_(view.root.bounds(), rep)
            data = rep.representationUsingType_properties_(A.NSBitmapImageFileTypePNG, {})
            data.writeToFile_atomically_(str(args.output/f"desktop-battery-{name}.png"), True)
        # Exercise the same actions used by the UI without starting USB/BLE workers.
        view.select_sample(samples and {"at": now, "percent": 0, "voltage": -1})
        assert "0%" in view.detail.stringValue()
        view.window.close()
    print("Native battery chart: light/dark, week, empty and sample selection PASS")


if __name__ == "__main__":
    main()
