"""Offline checks for invalid readings, stale data and safe version comparisons."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from device_info import normalize, presentation, compare
from desktop_controller import DesktopController
from service import Companion
from test_companion_bridge import FakeRpc
from wire import Decoder, dispatch


def sample(**values):
    return dict(schema=1, chip="ESP32-C3", profile="ble", firmware="0.5.0",
                elf_sha256="a"*64, heap_total=200000, heap_free=80000,
                heap_min=60000, heap_largest=40000, app_used=2700000,
                app_capacity=8323072, battery_pct=0, psram_bytes=0, **values)


class DeviceTests(unittest.TestCase):
    def test_draft_monitor_uses_sample_age_not_draft_presence(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = DesktopController(Path(directory))
            service = controller.service = Companion(FakeRpc(), directory)
            try:
                controller.update(state="ready")
                with patch("service.time.monotonic", return_value=100):
                    service.device_report(sample())
                for state in ("ready", "transcribing", "uncertain", "sent"):
                    service.draft = {"state": state}
                    with patch("desktop_controller.time.monotonic", return_value=105):
                        self.assertTrue(controller.snapshot()["device"]["fresh"], state)
                    with patch("desktop_controller.time.monotonic", return_value=116):
                        self.assertFalse(controller.snapshot()["device"]["fresh"], state)
                service.draft = {"state": "sending"}
                with patch("desktop_controller.time.monotonic", return_value=105):
                    self.assertFalse(controller.snapshot()["device"]["fresh"])
                service.draft = None
                service.recording = {"test": True}
                with patch("desktop_controller.time.monotonic", return_value=105):
                    self.assertFalse(controller.snapshot()["device"]["fresh"])
            finally:
                service.recording = None
                service.close()

    def test_missing_and_failed_sensors_are_not_zero(self):
        data = normalize(sample(die_c=float("nan"), battery_mv=-1, rssi_dbm=127))
        view = presentation(data, 1, True)
        self.assertEqual(view["battery"], "0%")
        self.assertEqual(view["temperature"], "--")
        self.assertEqual(view["voltage"], "电压不可用")
        self.assertIn("无 PSRAM", view["memory_spec"])
        self.assertEqual(presentation({}, None, True)["battery"], "--")
        self.assertAlmostEqual(view["heap_percent"], 60)

    def test_types_ranges_and_inconsistent_resources(self):
        data = sample()
        data.update(heap_free=200001, battery_pct=True, uptime_s=-1,
                    app_used=9000000, tasks=2**40, secret="not retained", firmware="bad\nversion")
        parsed = normalize(data)
        for key in ("heap_free", "heap_total", "app_used", "app_capacity", "battery_pct",
                    "uptime_s", "tasks", "secret", "firmware"):
            self.assertNotIn(key, parsed)
        self.assertEqual(presentation(parsed, 0, True)["heap"], "-- / --")
        for value in (None, [], {"schema": True}, {**sample(), "schema": 2},
                      {**sample(), "profile": "wifi"}):
            with self.assertRaises(ValueError): normalize(value)

    def test_staleness_disconnect_and_recording_are_explicit(self):
        data = normalize(sample())
        self.assertTrue(presentation(data, 5, True)["fresh"])
        for age, connected, recording, text in ((16, True, False, "暂停刷新"),
                (1, False, False, "连接已断开"), (1, True, True, "暂停采样")):
            view = presentation(data, age, connected, recording)
            self.assertFalse(view["fresh"])
            self.assertIn(text, view["status"])
        self.assertIn("旧固件", presentation(None, None, True)["status"])

    def test_numerical_version_order_and_build_identity(self):
        current = {"profile": "ble", "firmware": "0.9.0", "elf_sha256": "a"*64}
        candidate = {"profile": "ble", "version": "0.10.0", "elf_sha256": "b"*64}
        self.assertEqual(compare(current, candidate)[0], "upgrade")
        candidate["version"] = "0.8.0"
        self.assertEqual(compare(current, candidate)[0], "newer")
        candidate["version"] = "0.9.0"
        self.assertEqual(compare(current, candidate)[0], "different")
        candidate["elf_sha256"] = "a"*64
        self.assertEqual(compare(current, candidate)[0], "same")

    def test_unknown_legacy_and_cross_mode_never_claim_latest(self):
        current = normalize(sample())
        for candidate in (None, {"profile": None, "version": "1.0.0"},
                          {"profile": "ble", "version": "v0.2.0-dirty"},
                          {"profile": "ble", "version": 5},
                          {"profile": "ble", "version": "0.5.0"}):
            self.assertEqual(compare(current, candidate)[0], "unknown")
        self.assertEqual(compare(current, {"profile": "usb", "version": "9.0.0"})[0], "mode")
        self.assertEqual(compare(None, {"profile": "ble", "version": "0.5.0"})[0], "unknown")

    def test_wire_reporting_is_bounded_and_does_not_call_codex(self):
        with tempfile.TemporaryDirectory() as directory:
            rpc = FakeRpc()
            service = Companion(rpc, directory)
            self.addCleanup(service.close)
            with patch("service.time.monotonic", return_value=100):
                reply = dispatch(service, (1, 0, "/v1/device", json.dumps(sample()).encode()))
            self.assertEqual(Decoder().feed(reply)[0][1], 200)
            self.assertEqual(service.device_at, 100)
            self.assertEqual(service.device["heap_free"], 80000)
            self.assertEqual(rpc.calls, [])
            previous = service.device
            for payload in (b"x"*4097, b"[]", b"{bad", b'{"schema":2}'):
                reply = dispatch(service, (2, 0, "/v1/device", payload))
                self.assertEqual(Decoder().feed(reply)[0][1], 409)
                self.assertIs(service.device, previous)

    def test_controller_prefers_selected_firmware_and_only_alerts_when_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = DesktopController(Path(directory))
            controller.service = Companion(FakeRpc(), directory)
            self.addCleanup(controller.service.close)
            controller.service.device_report({**sample(), "firmware": "0.4.0"})
            controller.firmware_catalog = [{"profile": "ble", "version": "0.5.0", "elf_sha256": "b"*64}]
            controller.update(state="ready", detail="connected")
            self.assertEqual(controller.snapshot()["upgrade"]["kind"], "upgrade")
            self.assertIn("可升级", controller.snapshot()["detail"])
            controller.update(state="waiting")
            self.assertNotIn("可升级", controller.snapshot()["detail"])
            controller.firmware = {"profile": "usb", "descriptor": {"version": "1.0.0", "embedded_elf_sha256": "c"*64}}
            self.assertEqual(controller.snapshot()["upgrade"]["kind"], "mode")


if __name__ == "__main__": unittest.main()
