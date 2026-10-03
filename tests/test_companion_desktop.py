"""Offline lifecycle/reconnect regression tests; never contact a real chat."""
import asyncio
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
import local_data
import transports
import desktop_controller as desktop
from service import Companion, ClientError
from rpc import RpcError
from wire import Decoder, encode
from test_companion_bridge import FakeRpc


class LocalDataTests(unittest.TestCase):
    def setUp(self):
        # Downloads are byte-stream fakes here. Linux CI need not have the
        # macOS system certificate path used by the packaged desktop app.
        context = patch.object(local_data.ssl, "create_default_context", return_value=object())
        context.start()
        self.addCleanup(context.stop)

    def test_exclusive_owner_and_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock"
            first, second = local_data.InstanceLock(path), local_data.InstanceLock(path)
            first.acquire()
            with self.assertRaisesRegex(ValueError, "另一份"):
                second.acquire()
            first.release()
            second.acquire()
            second.release()

    def test_model_download_atomic_verification_and_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"verified model"
            with patch.object(local_data, "MODEL_HASH", hashlib.sha256(payload).hexdigest()), \
                 patch.object(local_data.urllib.request, "urlopen", return_value=io.BytesIO(payload)) as download:
                local_data.install_model(root)
                self.assertEqual(local_data.voice_paths(root)[1].read_bytes(), payload)
                local_data.install_model(root)
                self.assertEqual(download.call_count, 1)
            existing = root / "existing.bin"
            existing.write_bytes(payload)
            with patch.object(local_data, "MODEL_HASH", hashlib.sha256(payload).hexdigest()):
                local_data.use_model(root, existing)
            self.assertEqual(local_data.voice_paths(root)[1], existing.resolve())
            before = (root / "voice.json").read_bytes()
            with patch.object(local_data, "MODEL_HASH", "bad hash"), \
                 patch.object(local_data.urllib.request, "urlopen", return_value=io.BytesIO(b"corrupt")):
                with self.assertRaisesRegex(ValueError, "校验失败"):
                    local_data.install_model(root)
            self.assertEqual((root / "models/ggml-base.bin").read_bytes(), payload)
            self.assertEqual((root / "voice.json").read_bytes(), before)
            self.assertEqual(len(list((root / "models").iterdir())), 1)

    def test_cancel_download_cleans_partial(self):
        with tempfile.TemporaryDirectory() as root, \
             patch.object(local_data.urllib.request, "urlopen", return_value=io.BytesIO(b"model")):
            with self.assertRaisesRegex(ValueError, "取消"):
                local_data.install_model(root, cancelled=lambda: True)
            self.assertEqual(list((Path(root) / "models").iterdir()), [])


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.rpc = FakeRpc()
        self.service = Companion(self.rpc, self.temp.name, asr=lambda _: "检查代码")
        self.service.asr_ready = lambda: True
        self.stop = threading.Event()
        self.events = []
        self.card = SimpleNamespace(address="original-card", name="CodexCard")
        self.other = SimpleNamespace(address="other-card", name="CodexCard")
        self.BleakError = type("BleakError", (Exception,), {})

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def modules(self, client):
        return {"bleak": SimpleNamespace(BleakClient=client),
                "bleak.exc": SimpleNamespace(BleakError=self.BleakError)}

    def test_reconnect_pins_identity_retains_draft_queue_and_dedupe(self):
        self.service.draft = {"id": "draft-a", "thread_id": "thread-a", "state": "ready", "text": "测试"}
        self.service.queued = {"thread-b": {"pending-1"}}
        self.service.actions["record-request-01"] = ("fingerprint", {"ok": True})
        scans, opened, sessions = 0, [], []
        async def scan():
            nonlocal scans
            scans += 1
            if scans == 1: return [(self.card, None)]
            if scans == 2: return [(self.other, None)]
            return [(self.other, None), (self.card, None)]
        class Client:
            def __init__(_self, device, **_): opened.append(device.address)
            async def connect(_self): pass
            async def disconnect(_self): pass
        async def session(client, service, disconnected, stop, report):
            sessions.append(service)
            report("connected", "ok")
            if len(sessions) == 1: raise transports.LinkLost("connection lost")
            stop.set()
        async def fast(*_): pass
        with patch.dict(sys.modules, self.modules(Client)), patch.object(transports, "scan_ble", scan), \
             patch.object(transports, "ble_session", session), patch.object(transports, "retry_delay", fast):
            asyncio.run(transports.serve_ble(self.service, stop=self.stop, report=lambda *e: self.events.append(e)))
        self.assertEqual(opened, ["original-card", "original-card"])
        self.assertEqual(sessions, [self.service, self.service])
        self.assertEqual(self.service.draft["state"], "ready")
        self.assertEqual(self.service.queued, {"thread-b": {"pending-1"}})
        self.assertIn("record-request-01", self.service.actions)
        self.assertEqual(self.rpc.calls, [])

    def test_ble_lost_send_ack_does_not_repeat_accepted_or_uncertain_send(self):
        for uncertain in (False, True):
            with self.subTest(uncertain=uncertain):
                self.service.actions.clear()
                self.service.live.clear()
                self.rpc.calls.clear()
                self.service.draft = {"id":"draft-a", "thread_id":"thread-a", "state":"ready", "text":"检查代码"}
                def timeout(): raise RpcError("transport timeout")
                self.rpc.on_turn = timeout if uncertain else None
                request = encode(1, 0, "/v1/action", json.dumps(dict(action="send", draft_id="draft-a",
                                  request_id="send-request-000002")).encode())
                stop = threading.Event()
                attempts, replies = [], []
                outer = self
                class Client:
                    mtu_size, is_connected = 247, True
                    def __init__(self, _device, disconnected_callback, **_):
                        attempts.append(self); self.decoder = Decoder(); self.index = len(attempts)
                    async def connect(self): pass
                    async def disconnect(self): self.is_connected = False
                    async def read_gatt_char(self, _): return b"CPv1-IMA"
                    async def start_notify(self, _, callback): callback(None, request)
                    async def stop_notify(self, _): pass
                    async def write_gatt_char(self, _, data, response):
                        if self.index == 1: raise outer.BleakError("lost ack")
                        replies.extend(self.decoder.feed(data))
                        if replies: stop.set()
                async def scan(): return [(self.card, None)]
                async def fast(*_): pass
                with patch.dict(sys.modules, self.modules(Client)), patch.object(transports, "scan_ble", scan), \
                     patch.object(transports, "retry_delay", fast):
                    asyncio.run(transports.serve_ble(self.service, stop=stop))
                self.assertEqual(len(attempts), 2)
                self.assertEqual(sum(m == "turn/start" for m, _ in self.rpc.calls), 1)
                self.assertEqual(self.service.draft["state"], "uncertain" if uncertain else "sent")
                self.assertEqual(replies[0][1], 409 if uncertain else 200)

    def test_stop_during_pairing_clears_partial_audio(self):
        self.service.action(dict(action="record_start", request_id="record-request-001", thread_id="thread-a"))
        path = self.service.recording["path"]
        stop = self.stop
        class Client:
            is_connected = True
            def __init__(self, *_, **__): pass
            async def connect(self): pass
            async def disconnect(self): self.is_connected = False
            async def read_gatt_char(self, _):
                stop.set()
                await asyncio.sleep(100)
        async def scan(): return [(self.card, None)]
        with patch.dict(sys.modules, self.modules(Client)), patch.object(transports, "scan_ble", scan):
            start = time.monotonic()
            asyncio.run(transports.serve_ble(self.service, stop=stop))
        self.assertLess(time.monotonic()-start, 1)
        self.assertIsNone(self.service.recording)
        self.assertFalse(path.exists())

    def test_stop_during_scan_and_backoff(self):
        async def exercise():
            async def scan():
                self.stop.set()
                await asyncio.sleep(100)
            with self.assertRaises(transports.Stopped):
                await transports.cancellable(scan(), self.stop, 120)
            await transports.retry_delay(self.stop, 15)
        started = time.monotonic()
        asyncio.run(exercise())
        self.assertLess(time.monotonic()-started, 1)

    def test_ble_errors_identify_phase_without_exposing_os_error(self):
        outer = self
        for phase, expected in (("scan", "扫描超时"), ("connect", "无法连接"),
                                ("auth", "身份验证"), ("notify", "数据通道")):
            with self.subTest(phase=phase):
                attempts, events = [], []
                class Client:
                    is_connected = True
                    def __init__(self, *_, **__): pass
                    async def connect(self):
                        if phase == "connect": raise outer.BleakError("private-device-id")
                    async def disconnect(self): self.is_connected = False
                    async def read_gatt_char(self, _):
                        if phase == "auth": raise outer.BleakError("private-device-id")
                        return b"CPv1-IMA"
                    async def start_notify(self, *_): raise outer.BleakError("private-device-id")
                async def scan():
                    attempts.append(1)
                    if phase == "scan": raise asyncio.TimeoutError("private-device-id")
                    return [(outer.card, None)]
                async def fast(*_): pass
                with patch.dict(sys.modules, self.modules(Client)), patch.object(transports, "scan_ble", scan), \
                     patch.object(transports, "retry_delay", fast), self.assertRaises(ClientError) as failure:
                    asyncio.run(transports.serve_ble(self.service, stop=self.stop, report=lambda *e: events.append(e)))
                message = str(failure.exception)
                self.assertEqual(len(attempts), 3)
                self.assertIn(expected, message)
                self.assertNotIn("private-device-id", message + str(events))
                self.assertNotIn("清除配对", message)
                if phase != "auth": self.assertNotIn("六位", message)

    def test_ble_permission_error_stops_without_pairing_retries(self):
        error = self.BleakError("private-os-description")
        error.reason = SimpleNamespace(name="DENIED_BY_SYSTEM")
        async def scan(): raise error
        with patch.dict(sys.modules, self.modules(object)), patch.object(transports, "scan_ble", side_effect=scan) as scanner:
            with self.assertRaisesRegex(ClientError, "电脑管理员"):
                asyncio.run(transports.serve_ble(self.service, stop=self.stop))
            self.assertEqual(scanner.call_count, 1)

    def test_pairing_failures_bounded_and_protocol_error_not_retried(self):
        for protocol_error in (False, True):
            attempts = []
            outer = self
            class Client:
                is_connected = True
                def __init__(self, *_, **__): attempts.append(1)
                async def connect(self):
                    if not protocol_error: raise outer.BleakError("pairing failed")
                async def disconnect(self): self.is_connected = False
                async def read_gatt_char(self, _): return b"incompatible"
            async def scan(): return [(self.card, None)]
            async def fast(*_): pass
            with patch.dict(sys.modules, self.modules(Client)), patch.object(transports, "scan_ble", scan), \
                 patch.object(transports, "retry_delay", fast), self.assertRaises(ClientError):
                asyncio.run(transports.serve_ble(self.service, stop=self.stop))
            self.assertEqual(len(attempts), 1 if protocol_error else 3)

    def test_system_denial_is_actionable(self):
        for reason, text in (("POWERED_OFF", "关闭"), ("DENIED_BY_SYSTEM", "管理员"),
                             ("DENIED_BY_USER", "隐私")):
            exc = SimpleNamespace(reason=SimpleNamespace(name=reason))
            self.assertIn(text, transports.bluetooth_error(exc))

    def test_pause_drains_dispatch_before_return(self):
        entered, release = threading.Event(), threading.Event()
        stop, disconnected = self.stop, None
        class Client:
            is_connected, mtu_size = True, 247
            async def read_gatt_char(self, _): return b"CPv1-IMA"
            async def start_notify(self, _, callback): callback(None, encode(1, 0, "/v1/action", b"{}"))
            async def stop_notify(self, _): pass
            async def write_gatt_char(self, *_args, **_kwargs): pass
        def dispatch(*_):
            entered.set(); release.wait(3); return encode(1, 200, body=b"{}")
        async def exercise():
            task = asyncio.create_task(transports.ble_session(Client(), self.service, asyncio.Event(), stop))
            while not entered.is_set(): await asyncio.sleep(0.01)
            stop.set()
            await asyncio.sleep(0.1)
            self.assertFalse(task.done())
            release.set()
            await task
        with patch.object(transports, "dispatch", dispatch): asyncio.run(exercise())


class ControllerTests(unittest.TestCase):
    def test_single_service_survives_pause_and_requires_exit_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = desktop.DesktopController(Path(directory))
            controller.owner = local_data.InstanceLock(Path(directory) / "lock")
            rpc = FakeRpc()
            rpc.start = lambda: None
            seen = []
            def run(service, mode, stop, report):
                seen.append(service)
                report("ready", "ok")
            with patch.object(desktop, "Codex", return_value=rpc), \
                 patch.object(desktop, "codex_binary", return_value="codex"), patch.object(desktop, "run", run):
                controller.doctor(); controller.worker.join(2)
                controller.service.draft = {"state":"ready"}
                controller.connect("ble"); controller.worker.join(2)
                controller.connect("usb"); controller.worker.join(2)
                self.assertEqual(seen, [controller.service, controller.service])
                self.assertTrue(controller.pending())
                self.assertEqual(controller.snapshot()["state_success"], 2)
                controller.close()
                for _ in range(100):
                    if controller.closed: break
                    time.sleep(.01)
                self.assertTrue(controller.closed)


if __name__ == "__main__": unittest.main()
