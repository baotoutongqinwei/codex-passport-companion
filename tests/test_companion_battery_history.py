"""Card exports survive USB reconnection and import idempotently."""
import csv
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
import battery_history

DEVICE = {"port": "/dev/test", "serial": "card-1"}


class Port:
    def __init__(self, payload, **_):
        self.port = None
        self.dtr = self.rts = True
        self.answer = bytearray()
        self.payload = payload
        self.sent = []

    def __enter__(self): return self
    def __exit__(self, *_): pass
    def reset_input_buffer(self): pass
    @property
    def in_waiting(self): return len(self.answer)
    def write(self, data):
        self.sent.append(data)
        if data == b"CPBAT1?\n": self.answer.extend(self.payload)
        return len(data)
    def read(self, length):
        result = self.answer[:length]
        del self.answer[:length]
        return result


class BatteryHistoryTests(unittest.TestCase):
    def test_summary_only_labels_monotonic_gauge_decline(self):
        samples = [(1, 1791000000, 10, 91, 4050), (2, 1791001800, 1810, 87, 3970)]
        self.assertIn("近 30 分下降 4%", battery_history.battery_summary(samples))
        self.assertNotIn("下降", battery_history.battery_summary(samples[:1]))
        self.assertNotIn("下降", battery_history.battery_summary(samples+[\
            (3, 1791002100, 2110, 88, 3990)]))
        self.assertIn("时间未校准", battery_history.battery_summary([(1, 0, 300, 91, 4050)]))

    def test_complete_export_and_private_deduplicated_csv(self):
        payload = (b"boot log\nCPBAT1:BEGIN,42,2\n"
                   b"CPBAT1:D,8,1791000000,300,91,4050\n"
                   b"CPBAT1:D,9,1791000300,600,87,3970\n"
                   b"CPBAT1:END,42\n")
        port = Port(payload)
        with patch.object(battery_history, "usb_devices", return_value=[DEVICE]), \
             patch("serial.Serial", return_value=port):
            exported = battery_history.fetch_battery("card-1")
        self.assertEqual(exported[0], 42)
        self.assertEqual(exported[1][-1], (9, 1791000300, 600, 87, 3970))
        self.assertEqual(port.sent, [b"CPBAT1?\n"])
        self.assertFalse(port.dtr or port.rts)
        with tempfile.TemporaryDirectory() as directory:
            path, added = battery_history.save_battery(directory, "card-1", exported)
            self.assertEqual(added, 2)
            self.assertEqual(battery_history.save_battery(directory, "card-1", exported)[1], 0)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            with path.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["battery_pct"], "87")
            self.assertTrue(rows[1]["recorded_utc8"].endswith("+08:00"))

    def test_wrong_card_never_opened(self):
        with patch.object(battery_history, "usb_devices", return_value=[DEVICE]), \
             patch("serial.Serial") as opened:
            self.assertIsNone(battery_history.fetch_battery("other"))
            opened.assert_not_called()

    def test_card_storage_error_is_visible(self):
        with patch.object(battery_history, "usb_devices", return_value=[DEVICE]), \
             patch("serial.Serial", return_value=Port(b"CPBAT1:ERR\n")):
            with self.assertRaisesRegex(ValueError, "不可用"):
                battery_history.fetch_battery("card-1")

    def test_missing_end_rejects_partial_import(self):
        port = Port(b"")
        with patch.object(battery_history, "usb_devices", return_value=[DEVICE]), \
             patch("serial.Serial", return_value=port), \
             patch.object(battery_history, "_line", side_effect=[
                 b"CPBAT1:BEGIN,42,1", b"CPBAT1:D,8,1791000000,300,91,4050", None]):
            with self.assertRaisesRegex(ValueError, "结束标记"):
                battery_history.fetch_battery("card-1")


if __name__ == "__main__": unittest.main()
