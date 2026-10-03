"""No model calls: verify forwarding policy, recordings, bounds and TLS."""
import copy
import hashlib
import http.client
import io
import json
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from app import create_server
from rpc import Codex, RpcError
from service import Companion, ClientError, MAX_QUEUED_MESSAGES, MAX_RECORD_BYTES, display_text, glyph_width, paginate, quota_view


class FakeRpc:
    def __init__(self):
        self.calls = []
        self.account = {"type": "chatgpt"}
        self.thread = {"id": "thread-a", "name": "测试对话", "cwd": "/test",
                       "modelProvider": "openai", "status": {"type": "idle"},
                       "turns": [{"items": [{"type": "agentMessage", "text": "回复中文内容"*80}]}]}
        self.limits = {"rateLimits": {"primary": {"usedPercent": 12, "resetsAt": 2000000000},
                                      "secondary": {"usedPercent": 30}}}
        self.on_turn = None
        self.on_resume = None
        self.on_queue = None
        self.queued = []

    def call(self, method, params=None):
        self.calls.append((method, params))
        if method == "account/read": return {"account": self.account}
        if method == "account/rateLimits/read": return self.limits
        if method == "thread/list": return {"data": [self.thread], "nextCursor": "a+/="}
        if method == "thread/resume" and self.on_resume: self.on_resume()
        if method in ("thread/read", "thread/resume"): return {"thread": copy.deepcopy(self.thread)}
        if method == "thread/queue/add":
            if self.on_queue: self.on_queue()
            queued = dict(id=f'queue-{len(self.queued)+1}',
                          clientUserMessageId=params['clientUserMessageId'], input=params['input'])
            self.queued.append(queued)
            return {'queuedSubmission': queued}
        if method == "thread/queue/list": return {'data': copy.deepcopy(self.queued), 'nextCursor': None}
        if method == "turn/start":
            if self.on_turn: self.on_turn()
            return {"turn": {"id": "turn-1"}}
        raise AssertionError(method)

    def close(self): pass


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.rpc = FakeRpc()
        self.service = Companion(self.rpc, self.temp.name, asr=lambda _: "请检查代码")
        self.service.asr_ready = lambda: True
        self.counter = 0

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def action(self, action, **params):
        self.counter += 1
        return self.service.action(dict(action=action, request_id=f"request-{self.counter:016}", **params))

    def ready(self):
        self.service.draft = {"id": "draft-a", "thread_id": "thread-a", "state": "ready", "text": "检查代码"}

    def test_state_pages_and_unicode_bounds(self):
        self.service.refresh_limits()
        state = self.service.state("thread-a", page=-1)
        self.assertEqual(state["page"], state["pages"]-1)
        self.assertEqual(state["quota"]["primary"]["remaining"], 88)
        self.assertLessEqual(len(state["body"].splitlines()), 7)
        self.assertEqual(display_text("中文😀é"), "中文??")
        for text in ("", "中"*1000, "a"*1000, "a\n"*100):
            pages = paginate(text)
            self.assertTrue(pages)
            for page in pages:
                self.assertLessEqual(len(page.split("\n")), 7)
                for line in page.split("\n"):
                    self.assertLessEqual(sum(glyph_width(c) for c in line), 200)

    def test_quota_unknown_and_invalid(self):
        for value in (None, True, -1, 101, float("nan")):
            result = quota_view({"rateLimits": {"primary": {"usedPercent": value}}})
            self.assertEqual(result["primary"]["remaining"], -1)
        self.assertEqual(quota_view({"rateLimitsByLimitId": {"codex": {"primary": {"usedPercent": 100}}}})["primary"]["remaining"], 0)

    def test_quota_outage_keeps_chat_draft_and_transport_response(self):
        from wire import dispatch, Decoder
        self.ready()
        original = self.rpc.call
        for failed_method in ("account/read", "account/rateLimits/read"):
            self.service.limits_retry_at = 0
            def failing(method, params=None):
                if method == failed_method:
                    raise RpcError("synthetic outage")
                return original(method, params)
            with patch.object(self.rpc, "call", side_effect=failing):
                packet = dispatch(self.service, (1, 0, "/v1/state?thread=thread-a", b""))
                _, status, _, body = Decoder().feed(packet)[0]
                result = json.loads(body)
                self.assertEqual(status, 200)
                self.assertTrue(result["threads"])
                self.assertIn("回复中文内容", result["body"])
                self.assertEqual(result["draft"]["text"], "检查代码")
                self.assertTrue(result["quota"]["stale"])
                self.assertEqual(result["quota"]["updated"], 0)
                self.assertEqual(result["quota"]["primary"]["remaining"], -1)
                self.assertGreater(result["now"], 1700000000)
                with self.assertRaises(RpcError):
                    self.service.limits_future.result(timeout=1)

    def test_quota_cache_preserves_timestamp_backs_off_and_recovers(self):
        with patch("service.time.monotonic", return_value=100):
            self.service.refresh_limits()
            initial = copy.deepcopy(self.service.quota_snapshot())
        original = self.rpc.call
        attempts = []
        def failing(method, params=None):
            if method == "account/rateLimits/read":
                attempts.append(method)
                raise RpcError("synthetic outage")
            return original(method, params)
        with patch.object(self.rpc, "call", side_effect=failing):
            with patch("service.time.monotonic", return_value=131):
                stale = self.service.quota_snapshot()
                with self.assertRaises(RpcError):
                    self.service.limits_future.result(timeout=1)
            with patch("service.time.monotonic", return_value=145):
                self.service.state("thread-a")
                self.service.quota_snapshot()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(stale["updated"], initial["updated"])
        self.assertEqual(stale["primary"], initial["primary"])
        self.assertTrue(stale["stale"])
        self.rpc.limits["rateLimits"]["primary"]["usedPercent"] = 50
        with patch("service.time.monotonic", return_value=162):
            self.service.quota_snapshot()
            self.service.limits_future.result(timeout=1)
            recovered = self.service.quota_snapshot()
        self.assertFalse(recovered["stale"])
        self.assertEqual(recovered["primary"]["remaining"], 50)

    def test_send_never_uses_cached_quota_after_failure(self):
        self.ready()
        self.service.refresh_limits(force=True)
        original = self.rpc.call
        attempts = []
        def failing(method, params=None):
            attempts.append(method)
            if method == "account/rateLimits/read":
                raise RpcError("synthetic outage")
            return original(method, params)
        with patch.object(self.rpc, "call", side_effect=failing):
            with self.assertRaises(RpcError):
                self.action("send", draft_id="draft-a")
            with self.assertRaises(RpcError):
                self.action("send", draft_id="draft-a")
        self.assertEqual(attempts.count("account/rateLimits/read"), 2)
        self.assertNotIn("turn/start", attempts)
        self.assertNotIn("thread/queue/add", attempts)
        self.assertEqual(self.service.draft["state"], "ready")

    def test_slow_quota_does_not_block_state_or_asr_and_only_schedules_once(self):
        self.ready()
        entered, release = threading.Event(), threading.Event()
        original = self.rpc.call
        reads = []
        def slow(method, params=None):
            if method == "account/rateLimits/read":
                reads.append(method)
                entered.set()
                if not release.wait(3): raise RpcError("test deadline")
            return original(method, params)
        with patch.object(self.rpc, "call", side_effect=slow), ThreadPoolExecutor() as worker:
            try:
                cold = self.service.quota_snapshot()
                self.assertTrue(cold["stale"])
                self.assertEqual(cold["updated"], 0)
                self.assertTrue(entered.wait(1))
                future = self.service.limits_future
                for _ in range(10):
                    result = worker.submit(self.service.state, "thread-a").result(timeout=1)
                    self.assertEqual(result["draft"]["text"], "检查代码")
                    self.assertTrue(result["threads"])
                    self.assertIs(self.service.limits_future, future)
                self.assertEqual(self.service.executor.submit(lambda: "ASR available").result(timeout=1), "ASR available")
                self.assertEqual(len(reads), 1)
            finally:
                release.set()
            future.result(timeout=1)
        self.assertFalse(self.service.quota_snapshot()["stale"])

    def test_send_after_background_refresh_still_checks_new_quota(self):
        self.ready()
        entered, release, sending = threading.Event(), threading.Event(), threading.Event()
        original = self.rpc.call
        reads = []
        def changing(method, params=None):
            if method == "account/rateLimits/read":
                reads.append(method)
                if len(reads) == 1:
                    entered.set()
                    if not release.wait(3): raise RpcError("test deadline")
                    return {"rateLimits": {"primary": {"usedPercent": 10}}}
                return {"rateLimits": {"primary": {"usedPercent": 100}}}
            return original(method, params)
        def send():
            sending.set()
            return self.action("send", draft_id="draft-a")
        with patch.object(self.rpc, "call", side_effect=changing), ThreadPoolExecutor() as worker:
            try:
                self.service.quota_snapshot()
                self.assertTrue(entered.wait(1))
                result = worker.submit(send)
                self.assertTrue(sending.wait(1))
                self.assertFalse(result.done())
                self.assertNotIn("turn/start", [m for m, _ in self.rpc.calls])
            finally:
                release.set()
            with self.assertRaisesRegex(ClientError, "额度已用完"):
                result.result(timeout=1)
        self.assertEqual(len(reads), 2)
        self.assertNotIn("turn/start", [m for m, _ in self.rpc.calls])
        self.assertEqual(self.service.draft["state"], "ready")

    def test_closed_service_never_schedules_quota_reads(self):
        self.service.close()
        self.assertTrue(self.service.quota_snapshot()["stale"])
        self.assertIsNone(self.service.limits_future)
        self.assertEqual(self.rpc.calls, [])

    def test_record_sequence_duplicate_and_limit(self):
        ident = self.action("record_start", thread_id="thread-a")["record_id"]
        self.service.audio(ident, 0, b"\x00\x01"*1024)
        self.service.audio(ident, 0, b"\x00\x01"*1024)
        self.assertEqual(self.service.recording["size"], 2048)
        for seq, chunk in ((0,b"\x00\x02"*1024), (3,b"\x00\x01"), (1,b"x"), (1,b"x"*4098)):
            with self.assertRaises(ClientError): self.service.audio(ident, seq, chunk)
        self.service.recording["size"] = MAX_RECORD_BYTES
        with self.assertRaises(ClientError): self.service.audio(ident, 1, b"\x00\x01")
        self.action("cancel")
        self.assertFalse(list(Path(self.temp.name).glob("record-*")))

    @patch("service.time.time", return_value=1700000000)
    def test_quota_weekly_and_nearest_available_resets(self, _):
        def credit(expiry, **fields):
            return dict(id="private-id", status="available", resetType="codexRateLimits", expiresAt=expiry, **fields)
        rows = [credit(1700300000), credit(1700200000), credit(1700100000), credit(None)]
        result = quota_view({"rateLimitsByLimitId": {"codex": {
            "primary": {"usedPercent": 84, "resetsAt": 1791165964, "windowDurationMins": 10080},
            "secondary": None}}, "rateLimitResetCredits": {"availableCount": 4, "credits": rows}})
        self.assertEqual(result["primary"], {"remaining": 16, "reset": 1791165964, "minutes": 10080})
        self.assertEqual(result["secondary"]["remaining"], -1)
        self.assertEqual(result["reset_credits"], {"available": 4, "complete": True,
                                                  "expirations": [1700100000, 1700200000]})
        self.assertNotIn("private-id", json.dumps(result))
        # Distinct opportunities expiring together still occupy two rows.
        rows[1]["expiresAt"] = 1700100000
        self.assertEqual(quota_view({"rateLimitResetCredits": {"availableCount": 4, "credits": rows}})
                         ["reset_credits"]["expirations"], [1700100000, 1700100000])

    @patch("service.time.time", return_value=1700000000)
    def test_quota_excludes_unavailable_expired_and_invalid_resets(self, _):
        rows = [dict(status="available", resetType="codexRateLimits", expiresAt=1700100000)]
        for status in ("redeeming", "redeemed", "unknown"):
            rows.append(dict(rows[0], status=status, expiresAt=1700000010))
        rows.append(dict(rows[0], resetType="unknown", expiresAt=1700000010))
        for expiry in (1700000000, 1699999999, True, "1700000010", float("nan"), 253402272000):
            rows.append(dict(rows[0], expiresAt=expiry))
        rows.extend([None, "bad"])
        result = quota_view({"rateLimitResetCredits": {"availableCount": 7, "credits": rows}})
        self.assertEqual(result["reset_credits"], {"available": 7, "complete": False,
                                                  "expirations": [1700100000]})

    def test_quota_reset_details_unknown_partial_and_no_expiry(self):
        for summary in (None, "invalid", {}, {"availableCount": True}, {"availableCount": -1}):
            self.assertEqual(quota_view({"rateLimitResetCredits": summary})["reset_credits"],
                             {"available": -1, "complete": False, "expirations": []})
        for count, rows, complete in ((0, None, False), (0, [], True), (4, None, False), (4, [], False),
                (1, [dict(status="available", resetType="codexRateLimits", expiresAt=None)], True)):
            self.assertEqual(quota_view({"rateLimitResetCredits": {"availableCount": count, "credits": rows}})
                             ["reset_credits"], {"available": count, "complete": complete, "expirations": []})

    def test_quota_refresh_reads_credit_details_without_consuming(self):
        self.rpc.calls.clear()
        self.service.refresh_limits(force=True)
        self.assertEqual(self.rpc.calls, [("account/read", None),
                                         ("account/rateLimits/read", {"excludeResetCreditDetails": False})])

    def test_transcription_keeps_original_target_and_requires_confirmation(self):
        ident = self.action("record_start", thread_id="thread-a")["record_id"]
        for seq in range(4): self.service.audio(ident, seq, b"\x00\x01"*1024)
        with self.assertRaises(ClientError): self.action("record_finish", record_id=ident, chunks=3)
        self.action("record_finish", record_id=ident, chunks=4)
        self.service.executor.submit(lambda: None).result(timeout=3)
        self.assertEqual(self.service.draft["state"], "ready")
        self.service.state("thread-b")
        self.assertFalse(any(m == "turn/start" for m,_ in self.rpc.calls))
        self.action("send", draft_id=ident)
        sends = [p for m,p in self.rpc.calls if m == "turn/start"]
        self.assertEqual(sends[0]["threadId"], "thread-a")
        self.assertEqual(sends[0]["input"][0]["text"], "请检查代码")

    def test_send_is_idempotent_and_keeps_early_delta(self):
        self.ready()
        self.rpc.on_turn = lambda: self.service.notify("item/agentMessage/delta", {"threadId": "thread-a", "delta": "实时回复"})
        request = {"action": "send", "draft_id": "draft-a", "request_id": "1"*32}
        first = self.service.action(request)
        self.assertEqual(first, self.service.action(request))
        self.assertEqual(len([m for m,_ in self.rpc.calls if m == "turn/start"]), 1)
        self.assertEqual(self.service.live["thread-a"]["output"], "实时回复")
        with self.assertRaises(ClientError): self.service.action(dict(request, draft_id="other"))

    def test_send_timeout_never_retries(self):
        self.ready()
        def fail(): raise RpcError("timeout")
        self.rpc.on_turn = fail
        request = {"action": "send", "draft_id": "draft-a", "request_id": "2"*32}
        with self.assertRaises(RpcError): self.service.action(request)
        with self.assertRaises(ClientError): self.service.action(request)
        with self.assertRaises(ClientError): self.action("send", draft_id="draft-a")
        self.assertEqual(self.service.draft["state"], "uncertain")
        self.assertEqual(len([m for m,_ in self.rpc.calls if m == "turn/start"]), 1)

    def test_no_paid_fallback(self):
        cases = [("apikey", "openai", 5), ("chatgpt", "custom", 5),
                 ("chatgpt", "openai", 100), ("chatgpt", "openai", None)]
        for account, provider, used in cases:
            self.ready()
            self.rpc.account["type"] = account
            self.rpc.thread["modelProvider"] = provider
            self.rpc.limits["rateLimits"]["primary"]["usedPercent"] = used
            with self.assertRaises(ClientError): self.action("send", draft_id="draft-a")
        self.assertFalse(any(m == "turn/start" for m,_ in self.rpc.calls))

    def test_active_thread_and_bounded_failed_actions(self):
        self.ready(); self.rpc.thread["status"] = {"type": "active"}
        result = self.action("send", draft_id="draft-a")
        self.assertTrue(result['queued'])
        self.assertFalse(any(m in ('thread/resume','turn/start') for m,_ in self.rpc.calls))
        for _ in range(140):
            with self.assertRaises(ClientError): self.action("unknown")
        self.assertLessEqual(len(self.service.actions), 128)

    def test_active_writer_queues_original_draft_once_without_starting_turn(self):
        self.ready()
        def busy(): raise RpcError('thread 11111111-1111-1111-1111-111111111111 already has an active writer', rejected=True, code=-32600)
        self.rpc.on_resume = busy
        request = dict(action='send',draft_id='draft-a',request_id='writer-request-000001')
        first = self.service.action(request)
        self.assertEqual(self.service.action(request),first)
        self.assertTrue(first['queued'])
        self.assertEqual(self.rpc.queued[0]['input'][0]['text'],'检查代码')
        self.assertEqual(len(self.rpc.queued),1)
        self.assertFalse(any(m in ('turn/start','thread/queue/start') for m,_ in self.rpc.calls))
        self.assertNotIn('thread-a',self.service.resumed)
        self.action('cancel')  # Firmware clears its confirmation after an accepted send.
        self.service.transport_disconnected()
        self.assertIn('等待电脑处理',self.service.state('thread-a',page=-1)['body'])
        self.rpc.queued.clear()
        self.assertNotIn('等待电脑处理',self.service.state('thread-a',page=-1)['body'])
        self.assertFalse(self.service.queued)

    def test_queue_rejection_preserves_draft_and_timeout_never_resends(self):
        self.rpc.thread['status'] = {'type':'active'}
        for rejected in (True,False):
            self.ready()
            def fail(): raise RpcError('queue unavailable',rejected=rejected)
            self.rpc.on_queue = fail
            with self.assertRaises((ClientError,RpcError)):
                self.action('send',draft_id='draft-a')
            expected = 'ready' if rejected else 'uncertain'
            self.assertEqual(self.service.draft['state'],expected)
            if rejected:
                self.assertEqual(self.service.draft['text'],'检查代码')
            else:
                before = len(self.rpc.calls)
                with self.assertRaises(ClientError): self.action('send',draft_id='draft-a')
                self.assertEqual(len(self.rpc.calls),before)
        self.assertFalse(self.service.queued)

    def test_multiple_queued_drafts_keep_order_target_and_independent_deduplication(self):
        self.rpc.thread['status'] = {'type': 'active'}
        requests = []
        for number in range(3):
            ident = f'draft-{number}'
            self.service.draft = dict(id=ident, thread_id='thread-a', state='ready', text=f'测试{number}')
            request = dict(action='send', draft_id=ident, request_id=f'queue-request-{number:016}')
            first = self.service.action(request)
            self.assertTrue(first['queued'])
            self.assertEqual(self.service.action(request), first)
            requests.append(request)
            self.action('cancel')
            # Even an idle status must not let a later draft overtake pending input.
            self.rpc.thread['status'] = {'type': 'idle'}
        self.assertEqual([q['input'][0]['text'] for q in self.rpc.queued], ['测试0', '测试1', '测试2'])
        self.assertEqual([q['clientUserMessageId'] for q in self.rpc.queued],
                         ['passport-draft-0', 'passport-draft-1', 'passport-draft-2'])
        sends = [p for m, p in self.rpc.calls if m == 'thread/queue/add']
        self.assertEqual([p['threadId'] for p in sends], ['thread-a'] * 3)
        self.assertFalse(any(m in ('thread/resume', 'turn/start', 'thread/queue/start') for m, _ in self.rpc.calls))
        self.assertEqual(self.service._pending_queue_count('thread-a'), 3)
        self.service.transport_disconnected()
        self.service.action(requests[0])
        self.assertEqual(len(self.rpc.queued), 3)
        self.rpc.queued.pop(0)
        self.assertEqual(self.service._pending_queue_count('thread-a'), 2)
        self.rpc.queued.clear()
        self.assertEqual(self.service._pending_queue_count('thread-a'), 0)
        self.assertFalse(self.service.queued)

    def test_queue_limit_preserves_draft_and_frees_consumed_slots(self):
        self.rpc.thread['status'] = {'type': 'active'}
        for number in range(MAX_QUEUED_MESSAGES):
            ident = f'draft-{number}'
            self.service.draft = dict(id=ident, thread_id='thread-a', state='ready', text='测试')
            self.action('send', draft_id=ident)
            self.action('cancel')
        self.ready()
        with self.assertRaisesRegex(ClientError, '32条'):
            self.action('send', draft_id='draft-a')
        self.assertEqual(self.service.draft['state'], 'ready')
        self.assertEqual(len(self.rpc.queued), MAX_QUEUED_MESSAGES)
        self.rpc.queued.clear()
        self.assertTrue(self.action('send', draft_id='draft-a')['queued'])
        self.assertEqual(self.service._pending_queue_count('thread-a'), 1)

    def test_queue_tracking_survives_failed_or_incomplete_reads_and_concurrent_add(self):
        self.service.queued = {'thread-a': {'queue-1', 'queue-2'}, 'thread-b': {'other'}}
        with patch.object(self.rpc, 'call', side_effect=RpcError('unavailable')):
            self.assertEqual(self.service._pending_queue_count('thread-a'), 2)
        with patch.object(self.rpc, 'call', return_value={'data': [{'id': 'queue-2'}], 'nextCursor': 'more'}):
            self.assertEqual(self.service._pending_queue_count('thread-a'), 2)
        def listed(*_):
            self.service.queued['thread-a'].add('queue-3')
            return {'data': [{'id': 'queue-2'}], 'nextCursor': None}
        with patch.object(self.rpc, 'call', side_effect=listed):
            self.assertEqual(self.service._pending_queue_count('thread-a'), 2)
        self.assertEqual(self.service.queued, {'thread-a': {'queue-2', 'queue-3'}, 'thread-b': {'other'}})

    def test_later_queue_failure_does_not_drop_earlier_entries(self):
        self.rpc.thread['status'] = {'type': 'active'}
        self.ready()
        self.action('send', draft_id='draft-a')
        self.action('cancel')
        self.service.draft = dict(id='draft-b', thread_id='thread-a', state='ready', text='第二条')
        def fail():
            raise RpcError('timeout')
        self.rpc.on_queue = fail
        with self.assertRaises(RpcError):
            self.action('send', draft_id='draft-b')
        self.assertEqual(self.service.draft['state'], 'uncertain')
        self.assertEqual(self.service.queued, {'thread-a': {'queue-1'}})
        self.assertEqual(len(self.rpc.queued), 1)

    def test_turn_rejection_restores_ready_draft_without_fake_active_status(self):
        self.ready()
        def rejected(): raise RpcError('request rejected',rejected=True,code=-32602)
        self.rpc.on_turn = rejected
        with self.assertRaises(RpcError): self.action('send',draft_id='draft-a')
        self.assertEqual(self.service.draft['state'],'ready')
        self.assertEqual(self.service.draft['text'],'检查代码')
        self.assertNotIn('thread-a',self.service.live)
        self.assertFalse(any(m=='thread/queue/add' for m,_ in self.rpc.calls))

    def test_only_explicit_writer_rejection_falls_back_after_turn_start(self):
        self.ready()
        def rejected(): raise RpcError('thread already has an active writer',rejected=True)
        self.rpc.on_turn = rejected
        self.assertTrue(self.action('send',draft_id='draft-a')['queued'])
        self.assertNotIn('thread-a',self.service.resumed)
        self.assertNotIn('thread-a',self.service.live)
        self.assertEqual(len(self.rpc.queued),1)

    def test_rpc_error_distinguishes_server_rejection_from_transport_loss(self):
        rpc = Codex()
        for transport_error in (False,True):
            def reply(request):
                rpc.pending[request['id']].put({'error':{'message':'thread already has an active writer','code':-32000},
                                              'transport_error':transport_error})
            with patch.object(rpc,'_write',side_effect=reply):
                with self.assertRaises(RpcError) as caught: rpc.call('thread/resume',{})
            self.assertEqual(caught.exception.rejected,not transport_error)
            self.assertEqual(caught.exception.active_writer,not transport_error)
            self.assertEqual(caught.exception.code,-32000)

    def test_writer_errors_with_and_without_thread_id(self):
        for message in ('thread already has an active writer',
                        'thread 11111111-1111-1111-1111-111111111111 already has an active writer',
                        'Failed to resume: Thread thread-a already has an active writer'):
            self.assertTrue(RpcError(message,rejected=True,code=-32600).active_writer)
            self.assertFalse(RpcError(message).active_writer)
        self.assertFalse(RpcError('thread not found',rejected=True).active_writer)

    def test_speech_preview_and_queue_use_same_simplified_chinese(self):
        self.service.asr = lambda _: '請檢查這個對話的語音識別與額度餘額，Codex USB 24 小時。'
        path = Path(self.temp.name)/'record-traditional.pcm'
        path.write_bytes(b'00')
        self.service.draft = dict(id='draft-a',thread_id='thread-a',state='transcribing',text='')
        self.service._transcribe(dict(id='draft-a',path=path))
        expected = '请检查这个对话的语音识别与额度余额，Codex USB 24 小时。'
        self.assertEqual(self.service.draft['state'],'ready')
        self.assertEqual(self.service.state('thread-a')['draft']['text'],expected)
        self.assertFalse(path.exists())
        self.rpc.thread['status'] = {'type':'active'}
        self.action('send',draft_id='draft-a')
        self.assertEqual(self.rpc.queued[0]['input'][0]['text'],expected)

    def test_missing_chinese_converter_does_not_emit_traditional_draft(self):
        self.service.simplifier = None
        self.service.asr = lambda _: '繁體語音'
        path = Path(self.temp.name)/'record-missing-converter.pcm'
        path.write_bytes(b'00')
        self.service.draft = dict(id='draft-a',thread_id='thread-a',state='transcribing',text='')
        self.service._transcribe(dict(id='draft-a',path=path))
        self.assertEqual(self.service.draft['state'],'failed')
        self.assertIn('中文转换组件',self.service.draft['text'])
        self.assertFalse(path.exists())

    def test_cancel_during_asr_does_not_restore_draft(self):
        self.ready()
        path = Path(self.temp.name)/"record-test.pcm"; path.write_bytes(b"00")
        self.action("cancel")
        self.service._transcribe({"id": "draft-a", "path": path})
        self.assertIsNone(self.service.draft)
        self.assertFalse(path.exists())

    def test_recording_expiration(self):
        self.action("record_start", thread_id="thread-a")
        self.service.recording["last"] -= 21
        self.service.state()
        self.assertIsNone(self.service.recording)
        self.assertFalse(list(Path(self.temp.name).glob("record-*")))

    def test_clock_timestamp_is_fresh_after_rpc_work(self):
        def update_clock(*_):
            fake_time.return_value = 1800000001.875
            return {"primary": {"remaining": 50}}
        with patch("service.time.time", return_value=1800000000.125) as fake_time:
            with patch.object(self.service, "refresh_limits", side_effect=update_clock):
                self.assertEqual(self.service.state()["now"], 1800000001.875)

    def test_live_output_not_duplicated_and_permissions_remain_visible(self):
        self.rpc.thread["turns"] = [{"id": "t", "items": [{"type": "agentMessage", "text": "实时消息"}]}]
        self.service.notify("turn/started", {"threadId": "thread-a", "turn": {"id": "t"}})
        self.service.notify("item/agentMessage/delta", {"threadId": "thread-a", "delta": "实时消息"})
        self.assertEqual(self.service.state("thread-a", page=-1)["body"].count("实时消息"), 1)
        self.service.notify("passport/needsDesktop", {"threadId": "thread-a"})
        self.service.notify("turn/completed", {"threadId": "thread-a"})
        self.service.notify("thread/status/changed", {"threadId": "thread-a", "status": {"type": "idle"}})
        state = self.service.state("thread-a", page=-1)
        self.assertEqual(state["status"], "needsDesktop")

    def test_tls_authentication_and_endpoint_round_trip(self):
        root = Path(self.temp.name)
        cert, key = root/"cert.pem", root/"key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                        "-days", "1", "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1",
                        "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)
        server = create_server(self.service, "test-token", "127.0.0.1", 0, cert, key)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        client = http.client.HTTPSConnection("127.0.0.1", server.server_port, timeout=3,
                                            context=ssl.create_default_context(cafile=str(cert)))
        try:
            client.request("GET", "/v1/state")
            response = client.getresponse(); self.assertEqual(response.status, 401); response.read()
            client.request("GET", "/v1/state?thread=thread-a&page=-1", headers={"Authorization": "Bearer test-token"})
            response = client.getresponse(); self.assertEqual(response.status, 200)
            data = json.loads(response.read()); self.assertEqual(data["id"], "thread-a")
            client.request("POST", "/v1/action", body="[]", headers={"Authorization": "Bearer test-token"})
            response = client.getresponse(); self.assertEqual(response.status, 409); response.read()
        finally:
            client.close(); server.shutdown(); server.server_close(); thread.join()


class RpcTests(unittest.TestCase):
    def test_approval_requests_are_declined_and_reported(self):
        notices = []
        rpc = Codex(lambda method, params: notices.append((method, params)))
        requests = [{"id": 1, "method": "item/commandExecution/requestApproval", "params": {"threadId": "a"}},
                    {"id": 2, "method": "item/fileChange/requestApproval", "params": {"threadId": "a"}},
                    {"id": 3, "method": "item/tool/requestUserInput", "params": {"threadId": "a"}}]
        class Process:
            stdin = io.StringIO()
            stdout = io.StringIO("\n".join(json.dumps(r) for r in requests))
            def poll(self): return None
        rpc.process = Process()
        rpc._read()
        replies = [json.loads(line) for line in rpc.process.stdin.getvalue().splitlines()]
        self.assertEqual(replies[0]["result"], {"decision": "decline"})
        self.assertEqual(replies[1]["result"], {"decision": "decline"})
        self.assertEqual(replies[2]["result"], {"answers": {}})
        self.assertEqual(len(notices), 3)
        self.assertTrue(all(method == "passport/needsDesktop" for method,_ in notices))

    def test_timeout_cleans_pending_without_resending(self):
        rpc = Codex()
        written = []
        rpc._write = written.append
        with self.assertRaises(RpcError): rpc.call("turn/start", {}, timeout=0.001)
        self.assertEqual(len(written), 1)
        self.assertFalse(rpc.pending)


if __name__ == "__main__": unittest.main()
