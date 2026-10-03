"""History aggregation must not fabricate readings or mix devices."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"bridge"))
from battery_history import FIELDS, UTC8, save_battery
from battery_chart import read_history, chart_data

NOW = 1791000000


class BatteryChartTests(unittest.TestCase):
    def test_missing_file_and_empty_window(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(read_history(Path(directory)/"missing.csv", NOW), {})
        data = chart_data([], NOW)
        self.assertEqual(len(data["bins"]), 96)
        self.assertIsNone(data["latest"])
        self.assertIsNone(data["minimum"])

    def test_last_reading_per_bin_and_no_interpolation(self):
        samples = [{"at": NOW-900, "percent": 40, "voltage": 3800},
                   {"at": NOW-1800, "percent": 0, "voltage": 3300},
                   {"at": NOW-850, "percent": 38, "voltage": 3770}]
        data = chart_data(samples, NOW)
        self.assertEqual([row["percent"] if row else None for row in data["bins"][-3:]], [None, 0, 38])
        self.assertEqual(data["minimum"], 0)
        self.assertEqual(data["latest"]["percent"], 38)

    def test_range_boundaries_and_future(self):
        samples = [{"at": at, "percent": pct} for at, pct in (
            (NOW-86401, 99), (NOW-86400, 80), (NOW, 30), (NOW+1, 100))]
        data = chart_data(samples, NOW)
        self.assertEqual(data["bins"][0]["percent"], 80)
        self.assertEqual(data["bins"][-1]["percent"], 30)
        self.assertEqual(len(chart_data(samples, NOW, 7)["bins"]), 84)

    def test_devices_unsynced_invalid_and_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = save_battery(directory, "card-a", (1, [
                (1, NOW-300, 300, 70, 3900), (2, 0, 600, 69, 3890),
                (3, NOW-100, 700, -1, -1), (4, NOW+300, 800, 60, 3800)]))
            save_battery(directory, "card-b", (1, [(1, NOW-300, 300, 90, 4050)]))
            with path.open() as stream: rows = list(csv.DictReader(stream))
            with path.open("a", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writerow(rows[0])
                writer.writerow({**rows[0], "sequence": 5, "recorded_utc": "2026-10-03T10:00:00"})
            cards = read_history(path, NOW)
            self.assertEqual(len(cards["card-a"]["samples"]), 1)
            self.assertEqual(cards["card-a"]["unsynced"], 1)
            self.assertEqual(cards["card-a"]["invalid"], 3)
            self.assertEqual(cards["card-b"]["samples"][0]["percent"], 90)

    def test_utc_offset_and_old_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = save_battery(directory, "card", (1, [
                (1, NOW-8*86400, 300, 90, 4000), (2, NOW, 600, 80, 3900)]))
            text = path.read_text().replace(datetime.fromtimestamp(NOW, timezone.utc).isoformat(timespec="seconds"),
                                           datetime.fromtimestamp(NOW, UTC8).isoformat(timespec="seconds"))
            path.write_text(text)
            samples = read_history(path, NOW)["card"]["samples"]
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0]["at"], NOW)

    def test_schema_mismatch_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"battery-history.csv"
            path.write_text("unexpected,data\n1,2\n")
            with self.assertRaisesRegex(ValueError, "格式"):
                read_history(path, NOW)


if __name__ == "__main__":
    unittest.main()
