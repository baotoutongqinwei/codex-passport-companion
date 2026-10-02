"""Card-local unread, alert policy and read-only Codex observation regressions."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from activity import Activity, DEFAULT_ALERTS, load_alerts, quiet_now, save_alerts, thread_status, validate_alerts
from service import Companion
from test_companion_bridge import FakeRpc


def thread(turn="t1", status="completed", text="答复", runtime="idle"):
    return {"id": "thread-a", "name": "测试任务", "status": {"type": runtime},
            "turns": [{"id": turn, "status": status, "items": [
                {"type": "agentMessage", "id": "item-"+turn, "text": text}]}]}


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.activity = Activity({**DEFAULT_ALERTS, "quiet": False})

    def observe(self, raw, **kwargs):
        return self.activity.observe("a", raw, "任务", thread_status(raw), **kwargs)

    def test_historical_baseline_and_revision_guarded_unread(self):
        old = self.observe(thread())
        self.assertFalse(old["unread"])
        self.assertEqual(self.activity.notice(), {})
        new = self.observe(thread("t2", text="新答复"))
        self.assertTrue(new["unread"])
        self.activity.mark_read("a", old["revision"])
        self.assertTrue(new["unread"])
        self.activity.mark_read("a", new["revision"])
        self.assertFalse(self.observe(thread("t2", text="新答复"))["unread"])

    def test_completion_deduplication_even_after_status_flap(self):
        self.observe(thread("t2", "inProgress", runtime="active"))
        self.observe(thread("t2"))
        self.assertEqual(self.activity.notice(monotonic=100)["kind"], "completed")
        self.observe(thread("t2", "inProgress", runtime="active"))
        self.observe(thread("t2"))
        self.assertEqual(self.activity.notice(monotonic=200), {})

    def test_attention_and_failure_are_not_completion(self):
        self.observe(thread("t2", "inProgress", runtime="active"))
        data = thread("t2", "inProgress", runtime="active")
        data["status"]["activeFlags"] = ["waitingOnUserInput"]
        self.observe(data)
        self.assertEqual(self.activity.notice(monotonic=100)["kind"], "attention")
        self.observe(thread("t2", "failed"))
        self.assertEqual(self.activity.notice(monotonic=140)["kind"], "attention")
        self.observe(thread("t3", "interrupted"))
        self.assertEqual(self.activity.notice(monotonic=200), {})

    def test_rate_limit_expiration_and_queue_bound(self):
        for i in range(20):
            self.activity.observe(str(i), thread(), "任务", "active", now=10)
            self.activity.observe(str(i), thread("t2"), "任务", "idle", now=20)
        self.assertEqual(len(self.activity.pending), 8)
        self.assertTrue(self.activity.notice(now=21, monotonic=100))
        self.assertFalse(self.activity.notice(now=22, monotonic=129))
        self.assertTrue(self.activity.notice(now=23, monotonic=130))
        self.assertFalse(self.activity.notice(now=111, monotonic=200))
        for i in range(100):
            self.activity.observe(str(i), thread(), "任务", "idle")
        self.assertLessEqual(len(self.activity.entries), 32)

    def test_suppression_keeps_unread_and_does_not_replay(self):
        self.observe(thread("t2", "inProgress", runtime="active"))
        self.observe(thread("t2", text="录音期间完成"), suppressed=True)
        self.assertTrue(self.activity.entries["a"]["unread"])
        self.observe(thread("t2", text="录音期间完成"))
        self.assertEqual(self.activity.notice(), {})
        self.observe(thread("t3"))
        self.assertEqual(self.activity.notice(suppressed=True), {})
        self.assertEqual(self.activity.notice(), {})

    def test_quiet_hours_are_utc8_and_handle_midnight_and_boundaries(self):
        settings = dict(DEFAULT_ALERTS)
        for hour, expected in ((0, False), (13, False), (14, True), (23, True)):
            self.assertEqual(quiet_now(settings, hour*3600), expected)
        settings.update(start="09:30", end="10:00")
        self.assertFalse(quiet_now(settings, 1*3600+29*60))
        self.assertTrue(quiet_now(settings, 1*3600+30*60))
        self.assertFalse(quiet_now(settings, 2*3600))
        settings.update(start="00:00", end="00:00")
        self.assertTrue(quiet_now(settings, 10*3600))
        settings["quiet"] = False
        self.assertFalse(quiet_now(settings, 10*3600))

    def test_quiet_and_mute_apply_to_alerts_and_record_cues(self):
        self.activity.settings.update(quiet=True, sound=True)
        self.observe(thread(), now=13*3600)
        self.observe(thread("t2"), now=14*3600)
        self.assertEqual(self.activity.notice(now=14*3600), {})
        self.assertFalse(self.activity.sound_allowed(14*3600))
        self.assertTrue(self.activity.sound_allowed(13*3600))
        self.activity.settings["sound"] = False
        self.assertFalse(self.activity.sound_allowed(13*3600))
        self.activity.settings["enabled"] = False
        self.observe(thread("t3"), now=13*3600)
        self.assertEqual(self.activity.notice(now=13*3600), {})

    def test_persist_only_valid_preferences(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(load_alerts(root), DEFAULT_ALERTS)
            settings = save_alerts(root, {"sound": True, "private_text": "not saved"})
            self.assertEqual(load_alerts(root), settings)
            path = Path(root)/"alerts.json"
            self.assertNotIn("private_text", path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            for bad in ({"sound": 1}, {"start": "24:00"}, {"end": "9:00"}, []):
                with self.assertRaises(ValueError): validate_alerts(bad)
            path.write_text('{broken')
            self.assertEqual(load_alerts(root), DEFAULT_ALERTS)


class ServiceActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.rpc = FakeRpc()
        self.rpc.thread = thread()
        self.service = Companion(self.rpc, self.temp.name)
        self.service.activity.settings["quiet"] = False

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def refresh(self, raw):
        self.rpc.thread = raw
        self.service.history.clear()
        return self.service.state("thread-a", page=-1)

    def test_recency_sort_and_explicit_read_receipt(self):
        first = self.service.state("thread-a", page=-1)
        args = next(p for m,p in self.rpc.calls if m=="thread/list")
        self.assertEqual(args["sortKey"], "recency_at")
        self.assertEqual(args["limit"], 3)
        latest = self.refresh(thread("t2", text="新内容"))
        self.assertTrue(latest["threads"][0]["unread"])
        self.assertTrue(self.service.state()["threads"][0]["unread"])
        def read(revision, request):
            self.service.action({"action":"mark_read", "thread_id":"thread-a", "revision":revision,
                                 "request_id": request*32})
        read(first["revision"], "a")
        self.assertTrue(self.service.state()["threads"][0]["unread"])
        read(latest["revision"], "b")
        self.assertFalse(self.service.state()["threads"][0]["unread"])
        self.assertFalse(any(m in ("turn/start", "thread/resume", "thread/queue/add") for m,_ in self.rpc.calls))

    def test_status_flags_queue_count_and_once_only_alert(self):
        self.service.state()
        data = thread("t2", "inProgress", runtime="active")
        data["status"]["activeFlags"] = ["waitingOnApproval"]
        self.service.queued["thread-a"] = {"q1"}
        self.rpc.queued = [{"id":"q1"}]
        view = self.refresh(data)
        self.assertEqual(view["threads"][0]["status"], "needsDesktop")
        self.assertEqual(view["threads"][0]["queued"], 1)
        self.assertEqual(view["alert"]["kind"], "attention")
        self.assertFalse(self.service.state()["alert"])

    def test_history_cache_is_bounded_and_not_a_full_rollout(self):
        data=thread(text="x"*100000)
        data["turns"] *= 20
        self.refresh(data)
        cached = self.service.history["thread-a"][1]
        self.assertLess(len(json.dumps(cached)), 25000)
        self.assertNotIn("items", cached["turns"][0])

    def test_fresh_read_replaces_stale_live_status_and_resolved_approval(self):
        self.service.notify("turn/completed", {"threadId":"thread-a"})
        data = thread("t2", "inProgress", runtime="active")
        self.assertEqual(self.refresh(data)["status"], "active")
        data["status"]["activeFlags"] = ["waitingOnApproval"]
        self.assertEqual(self.refresh(data)["status"], "needsDesktop")
        data["status"]["activeFlags"] = []
        self.assertEqual(self.refresh(data)["status"], "active")
        self.assertEqual(self.refresh(thread("t2"))["status"], "idle")

    def test_another_writer_does_not_replay_previous_live_output(self):
        self.service.notify("turn/started", {"threadId":"thread-a", "turn":{"id":"old"}})
        self.service.notify("item/agentMessage/delta", {"threadId":"thread-a", "delta":"旧输出"})
        self.service.notify("turn/completed", {"threadId":"thread-a"})
        data = thread("new", "inProgress", text="当前输出", runtime="active")
        data["turns"].insert(0,thread("old",text="旧输出")["turns"][0])
        body = self.refresh(data)["body"]
        self.assertEqual(body.count("旧输出"),1)
        self.assertLess(body.index("旧输出"),body.index("当前输出"))

    def test_disconnect_drops_pending_alerts_but_retains_unread(self):
        self.service.state()
        with patch.object(self.service.activity, "notice", return_value={}):
            self.refresh(thread("t2"))
        self.assertTrue(self.service.activity.pending)
        self.service.transport_disconnected()
        self.assertFalse(self.service.activity.pending)
        self.assertTrue(self.service.activity.entries["thread-a"]["unread"])


if __name__ == "__main__": unittest.main()
