"""The USB sync must identify offline firmware before sending time."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
import offline_clock
import desktop_controller


DEVICE = {"port": "/dev/test", "serial": "card-1"}


class Port:
    def __init__(self, reply=True, **_):
        self.port = None
        self.dtr = self.rts = True
        self.sent = []
        self.answer = bytearray()
        self.reply = reply

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def reset_input_buffer(self):
        pass

    @property
    def in_waiting(self):
        return len(self.answer)

    def write(self, data):
        self.sent.append(data)
        if self.reply:
            self.answer.extend(b"CPCLK1:OFFLINE\n" if data == b"CPCLK1?\n" else b"CPCLK1:OK\n")
        return len(data)

    def read(self, length):
        result = self.answer[:length]
        del self.answer[:length]
        return result


class ClockSyncTests(unittest.TestCase):
    def test_sync_exact_card_after_handshake(self):
        port = Port()
        with patch.object(offline_clock, "usb_devices", return_value=[DEVICE]), \
             patch("serial.Serial", return_value=port), \
             patch.object(offline_clock.time, "time", return_value=1704067199.5):
            self.assertTrue(offline_clock.sync_clock("card-1"))
        self.assertEqual(port.port, "/dev/test")
        self.assertEqual(port.sent, [b"CPCLK1?\n", b"CPCLK1:1704067199500\n"])
        self.assertFalse(port.dtr or port.rts)

    def test_other_card_is_never_opened(self):
        with patch.object(offline_clock, "usb_devices", return_value=[DEVICE]), \
             patch("serial.Serial") as opened:
            self.assertFalse(offline_clock.sync_clock("different"))
            opened.assert_not_called()

    def test_no_handshake_never_sends_time(self):
        port = Port(reply=False)
        with patch.object(offline_clock, "usb_devices", return_value=[DEVICE]), \
             patch("serial.Serial", return_value=port):
            self.assertFalse(offline_clock.sync_clock("card-1"))
        self.assertEqual(port.sent, [b"CPCLK1?\n"])

    def test_desktop_syncs_on_attach_without_stealing_busy_link(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = desktop_controller.DesktopController(directory)
            with patch.object(desktop_controller, "usb_devices", return_value=[DEVICE]), \
                 patch.object(desktop_controller, "sync_clock", return_value=True) as sync, \
                 patch.object(desktop_controller, "fetch_battery", return_value=None):
                controller.update(firmware_busy=True)
                controller._sync_connected_clocks()
                sync.assert_not_called()
                controller.update(firmware_busy=False)
                controller._sync_connected_clocks()
                sync.assert_called_once_with("card-1")
                controller._sync_connected_clocks()
                sync.assert_called_once()
            with patch.object(desktop_controller, "usb_devices", return_value=[]):
                controller._sync_connected_clocks()
            with patch.object(desktop_controller, "usb_devices", return_value=[DEVICE]), \
                 patch.object(desktop_controller, "sync_clock", return_value=True) as sync, \
                 patch.object(desktop_controller, "fetch_battery", return_value=None):
                controller._sync_connected_clocks()
                sync.assert_called_once_with("card-1")

    def test_desktop_imports_offline_samples_after_attach(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = desktop_controller.DesktopController(directory)
            sample = (42, [(1, 1791000000, 300, 91, 4050)])
            with patch.object(desktop_controller, "usb_devices", return_value=[DEVICE]), \
                 patch.object(desktop_controller, "sync_clock", return_value=True), \
                 patch.object(desktop_controller, "fetch_battery", return_value=sample) as fetch, \
                 patch.object(desktop_controller, "save_battery", return_value=(Path(directory)/"battery-history.csv", 1)) as save:
                controller._sync_connected_clocks()
            fetch.assert_called_once_with("card-1")
            save.assert_called_once_with(directory, "card-1", sample)
            self.assertIn("新增 1 条", controller.snapshot()["battery_history"])


if __name__ == "__main__":
    unittest.main()
