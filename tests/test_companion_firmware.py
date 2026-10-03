"""No-device checks for firmware integrity, write scope and desktop interlocks."""
import hashlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
import firmware as fw
from desktop_controller import DesktopController
from local_data import InstanceLock
from service import Companion
from test_companion_bridge import FakeRpc


def image(payload, chip=5):
    header = bytearray(24)
    header[:4] = bytes([0xe9, 1, 2, 0x3f])
    struct.pack_into("<H", header, 12, chip)
    header[23] = 1
    raw = bytes(header) + struct.pack("<II", 0x3c000020, len(payload)) + payload
    checksum = 0xef
    for value in payload: checksum ^= value
    raw += bytes((15 - len(raw)) % 16) + bytes([checksum])
    return raw + hashlib.sha256(raw).digest()


def merged(marker=b""):
    payload = bytearray(4096)
    struct.pack_into("<I", payload, 0, 0xabcd5432)
    payload[16:48] = b"fixture-version".ljust(32, b"\0")
    payload[48:80] = b"FoloToy-AI-Passport".ljust(32, b"\0")
    payload[112:144] = b"v5.5.3".ljust(32, b"\0")
    payload[256:256+len(marker)] = marker
    table = b"".join(struct.pack("<HBBII16sI", 0x50aa, kind, subtype, offset, size,
                                name.encode().ljust(16, b"\0"), 0)
                     for kind, subtype, offset, size, name in fw.LAYOUT)
    table += b"\xeb\xeb" + b"\xff"*14 + hashlib.md5(table).digest()
    table = table.ljust(0xc00, b"\xff")
    app = image(payload)
    full = bytearray(b"\xff" * (0x10000 + len(app)))
    boot = image(bytes(64))
    full[:len(boot)] = boot
    full[0x8000:0x8c00] = table
    full[0x10000:] = app
    return full


DEVICE = {"port": "/dev/test-passport", "serial": "fixture-card", "location": "fixture",
          "vid": 0x303a, "pid": 0x1001}


class FirmwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / "full.bin"
        self.file.write_bytes(merged())

    def test_valid_merged_and_immutable_snapshot(self):
        result = fw.inspect_firmware(self.file)
        self.assertEqual(result["descriptor"]["version"], "fixture-version")
        self.assertEqual([offset for offset, _ in result["images"]], [0, 0x8000, 0x10000])
        self.file.write_bytes(b"changed")
        self.assertEqual(hashlib.sha256(result["data"]).hexdigest(), result["sha256"])

    def test_mode_marker_unknown_and_conflicting_images(self):
        self.assertIsNone(fw.inspect_firmware(self.file)["profile"])
        for mode in ("ble", "usb", "wifi", "offline"):
            self.file.write_bytes(merged(f"CPFW1:{mode}\0".encode()))
            self.assertEqual(fw.inspect_firmware(self.file)["profile"], mode)
        self.file.write_bytes(merged(b"CPFW1:ble\0CPFW1:usb\0"))
        with self.assertRaisesRegex(ValueError, "冲突"):
            fw.inspect_firmware(self.file)

    def test_reject_corruption_chip_partition_and_private_gap(self):
        for index in (0, 12, 0x8000, 0x8060+16, 0x9000, 0xf000, 0x10000+12, 0x10000+55, -1):
            with self.subTest(index=index):
                data = merged(); data[index] ^= 1
                self.file.write_bytes(data)
                with self.assertRaises(ValueError): fw.inspect_firmware(self.file)

    def test_reject_app_only_truncated_and_oversized(self):
        original = merged()
        for data in (original[0x10000:], original[:0x8100], original[:-20], b"x"*(fw.FLASH_SIZE+1)):
            self.file.write_bytes(data)
            with self.assertRaises(ValueError): fw.inspect_firmware(self.file)

    def tool(self, mismatch=False, fail=False, flash_size="8MB", verified=True):
        calls = []
        def run(args, log, report):
            calls.append(args)
            if "flash_id" in args: return "Detected flash size: " + flash_size
            if "read_flash" in args:
                Path(args[-1]).write_bytes(b"bad" if mismatch else bytes(merged()[0x8000:0x8c00]))
                return "read"
            if fail: raise ValueError("simulated unplug")
            if "write_flash" in args:
                return "Hash of data verified.\n" * (3 if args[-2] == "0x10000" else 1) if verified else ""
            raise AssertionError(args)
        return run, calls

    def test_preserve_uses_exact_three_segments_never_nvs_or_erase(self):
        tool, calls = self.tool()
        with patch.object(fw, "usb_devices", return_value=[DEVICE]), patch.object(fw, "run_tool", tool):
            fw.flash_firmware(fw.inspect_firmware(self.file), DEVICE, True, self.root, lambda *_: None)
        write = calls[-1]
        self.assertEqual(write[-6::2], ["0x0", "0x8000", "0x10000"])
        self.assertNotIn("erase_flash", str(calls)); self.assertNotIn("--erase-all", write)

    def test_complete_refresh_is_one_merged_write(self):
        tool, calls = self.tool()
        with patch.object(fw, "usb_devices", return_value=[DEVICE]), patch.object(fw, "run_tool", tool):
            fw.flash_firmware(fw.inspect_firmware(self.file), DEVICE, False, self.root, lambda *_: None)
        self.assertFalse(any("read_flash" in args for args in calls))
        self.assertEqual(calls[-1][-2], "0x0")
        self.assertTrue(calls[-1][-1].endswith("full.bin"))

    def test_mismatch_wrong_size_and_replaced_device_never_write(self):
        for mismatch, size in ((True,"8MB"), (False,"4MB")):
            tool, calls = self.tool(mismatch=mismatch, flash_size=size)
            with patch.object(fw,"usb_devices",return_value=[DEVICE]), patch.object(fw,"run_tool",tool):
                with self.assertRaises(ValueError):
                    fw.flash_firmware(fw.inspect_firmware(self.file), DEVICE, True, self.root, lambda *_: None)
            self.assertFalse(any("write_flash" in args for args in calls))
        with patch.object(fw,"usb_devices",return_value=[dict(DEVICE, serial="different")]), \
                patch.object(fw,"run_tool") as run:
            with self.assertRaises(ValueError):
                fw.flash_firmware(fw.inspect_firmware(self.file), DEVICE, False, self.root, lambda *_: None)
            run.assert_not_called()

    def test_failure_never_reports_success_and_cleans_temporary_images(self):
        for fail, verified in ((True,True),(False,False)):
            events = []
            tool, calls = self.tool(fail=fail, verified=verified)
            with patch.object(fw,"usb_devices",return_value=[DEVICE]), patch.object(fw,"run_tool",tool):
                with self.assertRaises(ValueError):
                    fw.flash_firmware(fw.inspect_firmware(self.file), DEVICE, True, self.root, lambda *e:events.append(e))
            self.assertFalse(any(e[0]==100 for e in events))
            self.assertFalse(Path(calls[-1][-1]).exists())

    def test_subprocess_nonzero_and_timeout_are_failures(self):
        for script, timeout in (("print('fatal error: test');raise SystemExit(2)",3),
                                ("import time;time.sleep(5)",.1)):
            with patch.object(fw,"tool_command",return_value=[sys.executable,"-c",script]):
                with self.assertRaises(ValueError): fw.run_tool([],io.StringIO(),lambda *_:None,timeout=timeout)

    def controller(self):
        c = DesktopController(self.root)
        c.owner = InstanceLock(self.root/"owner")
        self.addCleanup(c.owner.release)
        c.firmware = fw.inspect_firmware(self.file)
        return c

    def test_controller_blocks_pending_and_selection_changes(self):
        import desktop_controller as dc
        c = self.controller()
        with patch.object(dc,"flash_firmware") as write, patch.object(c,"pending",return_value=True):
            c.flash(c.firmware["sha256"], DEVICE, True); c.firmware_worker.join(2)
            write.assert_not_called()
        with patch.object(dc,"flash_firmware") as write:
            c.flash("wrong", DEVICE, True); c.firmware_worker.join(2)
            write.assert_not_called()

    def test_flash_drains_transport_owns_card_and_blocks_exit(self):
        import desktop_controller as dc
        c = self.controller()
        stopped, entered, release = threading.Event(), threading.Event(), threading.Event()
        def transport():
            c.stop.wait(2); stopped.set()
        c.worker = threading.Thread(target=transport); c.worker.start()
        def write(*_):
            self.assertTrue(stopped.is_set())
            self.assertIsNotNone(c.owner.file)
            entered.set(); release.wait(2)
        with patch.object(dc,"flash_firmware",write):
            c.flash(c.firmware["sha256"],DEVICE,True)
            self.assertTrue(entered.wait(2))
            c.close(); self.assertFalse(c.closing)
            self.assertFalse(c.connect("ble"))
            release.set(); c.firmware_worker.join(2)
        self.assertFalse(c.snapshot()["firmware_busy"])

    def test_firmware_only_owner_can_later_connect_without_double_lock(self):
        import desktop_controller as dc
        c = self.controller(); c.owner.acquire()
        rpc = FakeRpc(); rpc.start = lambda: None
        with patch.object(dc,"codex_binary",return_value="codex"), patch.object(dc,"Codex",return_value=rpc):
            c._ready()
        self.assertIsNotNone(c.service)
        c.service.close()

    def test_offline_flash_syncs_after_verified_write(self):
        import desktop_controller as dc
        c = self.controller()
        c.firmware["profile"] = "offline"
        order = []
        with patch.object(dc, "flash_firmware", side_effect=lambda *_: order.append("flash")), \
             patch.object(dc, "sync_clock", side_effect=lambda identity, wait_seconds: order.append("clock") or True):
            c.flash(c.firmware["sha256"], DEVICE, True)
            c.firmware_worker.join(2)
        self.assertEqual(order, ["flash", "clock"])
        self.assertIn("已自动校时", c.snapshot()["flash_detail"])


if __name__ == "__main__": unittest.main()
