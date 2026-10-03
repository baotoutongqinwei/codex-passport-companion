"""USB/BLE/TLS uploads share validation, durable acknowledgments and offline IDs."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"bridge"))
from battery_history import receive_battery, save_battery
from service import Companion
from wire import dispatch, Decoder
from app import Handler

IDENTITY = "AA:BB:CC:DD:EE:FF"
SAMPLES = [[1, 1791000000, 300, 92, 4080], [2, 1791000300, 600, 91, 4050]]


def packet(**values):
    return {"card_serial": IDENTITY, "log_id": 42, "storage_ok": True, "samples": SAMPLES, **values}


class BatteryUploadTests(unittest.TestCase):
    def test_ack_after_save_and_cross_transport_replay(self):
        with tempfile.TemporaryDirectory() as root:
            reply, summary, added = receive_battery(root, packet())
            self.assertEqual((reply["log_id"], reply["ack"], added), (42, 2, 2))
            self.assertIn("91%", summary)
            self.assertGreater(reply["now"], 1700000000)
            self.assertEqual(receive_battery(root, packet())[2], 0)
            self.assertEqual(save_battery(root, IDENTITY, (42, SAMPLES))[1], 0)
            with (Path(root)/"battery-history.csv").open() as source:
                self.assertEqual(len(list(csv.DictReader(source))), 2)

    def test_failed_persistence_never_acknowledged(self):
        with patch("battery_history.save_battery", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(ValueError, "未保存"):
                receive_battery("unused", packet())

    def test_bad_packets_do_not_write(self):
        invalid = [None, packet(card_serial="../../outside"), packet(log_id=True),
                   packet(storage_ok=1), packet(samples=SAMPLES*9),
                   packet(samples=[SAMPLES[1], SAMPLES[0]]),
                   packet(samples=[[1, 1791000000, 300, True, 4000]]),
                   packet(samples=[[1, 1791000000, -1, 92, 4000]]),
                   packet(samples=[[1, 1791000000, 300, 101, 4000]])]
        with patch("battery_history.save_battery") as save:
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    receive_battery("unused", value)
            save.assert_not_called()

    def test_empty_heartbeat_and_card_storage_error(self):
        with tempfile.TemporaryDirectory() as root:
            reply, summary, count = receive_battery(root, packet(samples=[], storage_ok=False))
            self.assertEqual(reply["ack"], 0)
            self.assertEqual(count, 0)
            self.assertIn("存储失败", summary)
            self.assertFalse((Path(root)/"battery-history.csv").exists())

    def test_usb_ble_and_wifi_routes_share_service(self):
        with tempfile.TemporaryDirectory() as root:
            service = Companion(SimpleNamespace(close=lambda: None), root)
            try:
                for frame_id in (1, 2):  # USB and BLE both carry CPv1 frames.
                    response = dispatch(service, (frame_id, 0, "/v1/battery", json.dumps(packet()).encode()))
                    frame = Decoder().feed(response)[0]
                    self.assertEqual(frame[1], 200)
                    self.assertEqual(json.loads(frame[3])["ack"], 2)
                handler = Handler.__new__(Handler)
                body = json.dumps(packet()).encode()
                handler.headers = {"Content-Length": str(len(body))}
                handler.rfile = io.BytesIO(body)
                handler.path = "/v1/battery"
                handler.server = SimpleNamespace(service=service)
                handler.authorized = lambda: True
                replies = []
                handler.reply = lambda status, result: replies.append((status, result))
                handler.do_POST()
                self.assertEqual(replies[0][0], 200)
                self.assertEqual(replies[0][1]["ack"], 2)
                self.assertIn("91%", service.battery_history)
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
