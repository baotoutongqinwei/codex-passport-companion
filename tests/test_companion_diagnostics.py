"""Card command lifecycle and metadata-only console logging."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from diagnostics import COMMANDS, Diagnostics
from service import Companion
from wire import Decoder, dispatch


class FakeRpc:
    def call(self, method, params=None):
        if method == "thread/list": return {"data": [], "nextCursor": None}
        if method == "account/read": return {"account": {"type": "chatgpt"}}
        if method == "account/rateLimits/read": return {"rateLimits": {"primary": {"usedPercent": 1}}}
        raise AssertionError(method)

    def close(self): pass


class DiagnosticTests(unittest.TestCase):
    def test_read_only_allowlist_lifecycle_and_retry(self):
        with tempfile.TemporaryDirectory() as root:
            service = Companion(FakeRpc(), root)
            try:
                with self.assertRaises(ValueError): service.diagnostics.queue("erase")
                ident = service.diagnostics.queue("battery")
                self.assertEqual(service.state()["diagnostic"], {"id": ident, "name": "battery"})
                with self.assertRaises(ValueError): service.diagnostics.queue("memory")
                payload = {"id": ident, "name": "battery", "text": "电量 88%\n芯片温度 31.5 C"}
                response = dispatch(service, (1, 0, "/v1/diagnostic-result", json.dumps(payload).encode()))
                self.assertEqual(Decoder().feed(response)[0][1], 200)
                self.assertNotIn("diagnostic", service.state())
                self.assertEqual(service.diagnostics.complete(payload), {"ok": True})
                self.assertEqual(sum("电量 88%" in line for line in service.diagnostics.snapshot()["lines"]), 1)
                with self.assertRaises(ValueError): service.diagnostics.complete({**payload, "id": "wrong"})
                self.assertIn("memory", COMMANDS)
            finally:
                service.close()

    def test_bounded_metadata_and_invalid_result(self):
        journal = Diagnostics()
        initial = journal.snapshot()["revision"]
        journal.trace("audio", 200)
        self.assertEqual(journal.snapshot()["revision"], initial)
        journal.trace("state", 200)
        journal.trace("state", 200)
        self.assertEqual(sum("state" in line for line in journal.snapshot()["lines"]), 1)
        journal.trace("audio", 409)
        self.assertTrue(any("audio" in line and "409" in line for line in journal.snapshot()["lines"]))
        count = len(journal.snapshot()["lines"])
        journal.trace("audio", 409)
        self.assertEqual(len(journal.snapshot()["lines"]), count + 1)
        ident = journal.queue("device")
        with self.assertRaises(ValueError): journal.complete({"id": ident, "name": "device", "text": "x"*769})
        self.assertTrue(journal.snapshot()["pending"])
        for index in range(200): journal.add("系统", f"事件 {index}")
        self.assertEqual(len(journal.snapshot()["lines"]), 160)
        journal.pending["at"] -= 31
        self.assertIsNone(journal.offer())
        self.assertTrue(any("超时" in line for line in journal.snapshot()["lines"]))


if __name__ == "__main__":
    unittest.main()
