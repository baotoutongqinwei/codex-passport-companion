"""Bounded device-facing state, recording and offline transcription."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import threading
import time
import wave

try:
    from opencc import OpenCC
except ImportError:
    OpenCC = None

from rpc import RpcError
from local_data import voice_paths

PAGE_CHARS = 360
MAX_RECORD_BYTES = 16000 * 2 * 45
MAX_DRAFT_CHARS = 600
MAX_QUEUED_MESSAGES = 32
# Rounded-up bitmap advances, U+0020..U+007E, verified against the generated font.
ASCII_WIDTHS = [4,6,8,9,9,15,11,5,6,6,8,9,5,6,5,7,9,9,9,9,9,9,9,9,9,9,5,5,9,9,9,8,
                16,10,11,11,11,10,9,11,12,5,9,11,9,13,12,12,11,12,11,10,10,12,10,15,10,9,10,
                6,7,6,9,9,10,9,10,9,10,9,6,9,10,5,5,9,5,15,10,10,10,10,7,8,7,10,9,13,8,9,8,6,5,6,9]


def glyph_width(char):
    return ASCII_WIDTHS[ord(char)-32] if 32 <= ord(char) <= 126 else 16


class ClientError(ValueError):
    pass


def paginate(text):
    """Seven lines per card, using the shipped font's pixel advances."""
    lines, line, width = [], "", 0
    for char in display_text(text, 48000).replace("\t", "  "):
        advance = glyph_width(char)
        if char == "\n":
            lines.append(line); line, width = "", 0
        else:
            if width + advance > 200:
                lines.append(line); line, width = "", 0
            line += char; width += advance
    if line or not lines:
        lines.append(line)
    return ["\n".join(lines[i:i+7]) for i in range(0, len(lines), 7)]


def display_text(value, limit=360):
    """Match the firmware's declared bitmap coverage. Unsupported glyphs stay visible."""
    text = str(value or "")
    return "".join(c if c in "\n\t" or 0x20 <= ord(c) <= 0x7e or
                   (0x3000 <= ord(c) <= 0x303f and not 0x302a <= ord(c) <= 0x3032) or 0x4e00 <= ord(c) <= 0x9fef or
                   0xff01 <= ord(c) <= 0xff60 else "?" for c in text)[:limit]


def quota_view(result):
    buckets = result.get("rateLimitsByLimitId") or {}
    rate = buckets.get("codex") or result.get("rateLimits") or {}
    def window(name):
        data = rate.get(name) or {}
        used = data.get("usedPercent")
        return {"remaining": max(0, min(100, 100 - used)) if isinstance(used, (int, float)) and not isinstance(used, bool) and 0 <= used <= 100 else -1,
                "reset": data.get("resetsAt") or 0,
                "minutes": data.get("windowDurationMins") or 0}
    balance = (rate.get("credits") or {}).get("balance")
    now = int(time.time())
    summary = result.get("rateLimitResetCredits")
    summary = summary if isinstance(summary, dict) else {}
    count = summary.get("availableCount")
    count = count if type(count) is int and 0 <= count <= 2147483647 else -1
    rows = summary.get("credits")
    available = [item for item in (rows if isinstance(rows, list) else [])
                 if isinstance(item, dict) and item.get("status") == "available"
                 and item.get("resetType") == "codexRateLimits"]
    expirations = sorted(item["expiresAt"] for item in available
                         if type(item.get("expiresAt")) is int
                         and now < item["expiresAt"] <= 253402271999)[:2]
    # A missing/capped detail list is not evidence that no opportunities expire.
    complete = isinstance(rows, list) and count >= 0 and len(available) == count
    if any(item.get("expiresAt") is not None and
           (type(item["expiresAt"]) is not int or not now < item["expiresAt"] <= 253402271999)
           for item in available):
        complete = False
    return {"primary": window("primary"), "secondary": window("secondary"),
            "blocked": bool(rate.get("rateLimitReachedType")),
            "credits": str(balance if balance is not None else "--")[:24],
            "reset_credits": {"available": count, "complete": complete, "expirations": expirations},
            "updated": now}


def extract_messages(thread, exclude_turn=None):
    parts = []
    for turn in thread.get("turns", []):
        if exclude_turn and turn.get("id") == exclude_turn:
            continue
        for item in turn.get("items", []):
            if item.get("type") == "agentMessage":
                parts.append("Codex\n" + str(item.get("text", "")))
            elif item.get("type") == "userMessage":
                text = "\n".join(c.get("text", "") for c in item.get("content", []) if c.get("type") == "text")
                if text:
                    parts.append("你\n" + text)
    return "\n\n".join(parts)[-24000:]


class Companion:
    def __init__(self, rpc, root, asr=None):
        self.rpc = rpc
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.asr = asr or self.transcribe
        self.simplifier = OpenCC('t2s') if OpenCC else None
        self.lock = threading.RLock()
        self.actions = OrderedDict()
        self.recording = None
        self.draft = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.limits = None
        self.limits_at = 0
        self.live = {}
        self.history = {}
        self.resumed = set()
        self.queued = {}
        self.last_error = ""
        self.account = {}
        self.send_lock = threading.Lock()

    def notify(self, method, params):
        with self.lock:
            ident = params.get("threadId")
            if method == "account/rateLimits/updated":
                # Force a full read to retain all quota buckets.
                self.limits_at = 0
            elif ident:
                state = self.live.setdefault(ident, {})
                if method == "turn/started":
                    state.update(status="active", output="", turn_id=(params.get("turn") or {}).get("id"))
                    self.history.pop(ident, None)
                elif method == "item/agentMessage/delta":
                    state["output"] = (state.get("output", "") + params.get("delta", ""))[-24000:]
                elif method == "turn/completed":
                    if state.get("status") != "needsDesktop":
                        state["status"] = "idle"
                    self.history.pop(ident, None)
                elif method == "thread/status/changed":
                    if state.get("status") != "needsDesktop":
                        state["status"] = (params.get("status") or {}).get("type", "unknown")
                elif method == "passport/needsDesktop":
                    state["status"] = "needsDesktop"
                elif method == "error":
                    state["status"] = "error"
                # Prevent unbounded subscriptions from growing the companion.
                if len(self.live) > 32:
                    self.live.pop(next(iter(self.live)))

    def refresh_limits(self, force=False):
        if force or time.monotonic() - self.limits_at > 30 or self.limits is None:
            self.account = self.rpc.call("account/read").get("account") or {}
            self.limits = quota_view(self.rpc.call("account/rateLimits/read", {"excludeResetCreditDetails": False}))
            self.limits_at = time.monotonic()
        return self.limits

    def state(self, ident="", cursor="", page=0):
        with self.lock:
            self._expire_recording()
        result = self.rpc.call("thread/list", {"limit": 4, "cursor": cursor or None,
                                               "sortKey": "updated_at", "modelProviders": []})
        threads = []
        for thread in result.get("data", []):
            threads.append({"id": thread["id"],
                            "title": display_text(thread.get("name") or thread.get("preview") or "未命名对话", 28),
                            "project": display_text(Path(thread.get("cwd") or "/").name, 20),
                            "status": (thread.get("status") or {}).get("type", "unknown")})
        view = {"threads": threads, "next": result.get("nextCursor") or "", "title": "",
                "id": ident, "body": "", "status": "idle", "page": 0, "pages": 1,
                "quota": self.refresh_limits(), "draft": {}, "asr": self.asr_ready()}
        if ident:
            cached = self.history.get(ident)
            if not cached or time.monotonic() - cached[0] > 3:
                thread = self.rpc.call("thread/read", {"threadId": ident, "includeTurns": True})["thread"]
                with self.lock:
                    live = self.live.get(ident, {})
                    exclude = live.get("turn_id") if live.get("status") == "active" else None
                cached = (time.monotonic(), thread.get("name") or thread.get("preview") or "对话",
                          extract_messages(thread, exclude), (thread.get("status") or {}).get("type", "unknown"))
                if len(self.history) >= 8:
                    self.history.pop(next(iter(self.history)))
                self.history[ident] = cached
            with self.lock:
                live = dict(self.live.get(ident, {}))
            body = cached[2]
            if live.get("output") and live.get("status") == "active":
                body += "\n\nCodex\n" + live["output"]
            if live.get("status") == "needsDesktop":
                body += "\n\n此操作需要电脑权限，卡片未授权。请在电脑继续。"
            queued_count = self._pending_queue_count(ident)
            if queued_count:
                body += f"\n\n待处理语音：{queued_count} 条\n等待电脑处理，请在电脑确认队列。"
            content = paginate(body or "暂无消息")
            pages = len(content)
            page = pages - 1 if page < 0 else min(page, pages - 1)
            view.update(title=display_text(cached[1], 28), status=live.get("status", cached[3]),
                        body=content[page],
                        pages=pages, page=page)
        with self.lock:
            if self.draft:
                view["draft"] = {k: self.draft[k] for k in ("id", "thread_id", "state", "text")}
        # Timestamp after RPC work; preserve fractions so repeated syncs do not
        # reset the card clock to the beginning of each second.
        view["now"] = time.time()
        return view

    def asr_ready(self):
        return self.simplifier is not None and all(path.is_file() for path in voice_paths(self.root))

    def _expire_recording(self):
        if self.recording and time.monotonic() - self.recording["last"] > 20:
            self.recording["path"].unlink(missing_ok=True)
            self.recording = None

    def transport_disconnected(self):
        # Abandon incomplete PCM, but retain confirmations and action deduplication.
        # A send may have reached Codex even when its USB response was lost.
        with self.lock:
            if self.recording:
                self.recording["path"].unlink(missing_ok=True)
                self.recording = None

    def audio(self, ident, seq, chunk):
        if not chunk or len(chunk) > 4096 or len(chunk) % 2:
            raise ClientError("无效音频块")
        with self.lock:
            self._expire_recording()
            rec = self.recording
            if not rec or rec["id"] != ident:
                raise ClientError("录音已失效，请重新录音")
            digest = hashlib.sha256(chunk).digest()
            if seq == rec["seq"] - 1 and digest == rec["digest"]:
                return {"seq": seq}
            if seq != rec["seq"]:
                raise ClientError("音频顺序错误，请重新录音")
            if rec["size"] + len(chunk) > MAX_RECORD_BYTES:
                raise ClientError("录音最多45秒")
            with rec["path"].open("ab") as stream:
                stream.write(chunk)
            rec.update(seq=seq + 1, digest=digest, size=rec["size"]+len(chunk), last=time.monotonic())
            return {"seq": seq}

    def action(self, data):
        request = data.get("request_id", "")
        if not isinstance(request, str) or not 16 <= len(request) <= 64:
            raise ClientError("缺少请求标识")
        fingerprint = json.dumps(data, sort_keys=True)
        # Serialize all actions; retries must never send a prompt twice.
        with self.send_lock:
            if request in self.actions:
                previous, result = self.actions[request]
                if fingerprint != previous:
                    raise ClientError("重复请求内容不一致")
                if "error" in result:
                    raise ClientError(result["error"])
                return result
            try:
                result = self._action(data)
            except (ClientError, RpcError) as exc:
                self.actions[request] = (fingerprint, {"error": str(exc)})
                while len(self.actions) > 128:
                    self.actions.popitem(last=False)
                raise
            self.actions[request] = (fingerprint, result)
            while len(self.actions) > 128:
                self.actions.popitem(last=False)
            return result

    def _action(self, data):
        action = data.get("action")
        if action == "record_start":
            ident = data.get("thread_id", "")
            if not ident:
                raise ClientError("请先选择对话")
            self.rpc.call("thread/read", {"threadId": ident, "includeTurns": False})
            if not self.asr_ready():
                raise ClientError("请先在 Mac 安装离线语音模型")
            with self.lock:
                self._expire_recording()
                if self.recording or (self.draft and self.draft["state"] in ("transcribing", "sending", "sent", "uncertain")):
                    raise ClientError("请先完成或取消当前语音")
                record_id = secrets.token_hex(16)
                path = self.root / ("record-" + record_id + ".pcm")
                path.touch(mode=0o600)
                self.recording = {"id": record_id, "thread_id": ident, "path": path,
                                  "seq": 0, "digest": None, "size": 0, "last": time.monotonic()}
                self.draft = None
                return {"record_id": record_id}
        if action == "record_finish":
            with self.lock:
                rec = self.recording
                if not rec or rec["id"] != data.get("record_id"):
                    raise ClientError("录音已失效")
                if rec["seq"] != data.get("chunks") or rec["size"] < 6400:
                    raise ClientError("录音不完整或过短")
                self.draft = {"id": rec["id"], "thread_id": rec["thread_id"], "state": "transcribing", "text": ""}
                self.recording = None
                self.executor.submit(self._transcribe, rec)
                return {"draft_id": rec["id"]}
        if action == "cancel":
            with self.lock:
                if self.recording:
                    self.recording["path"].unlink(missing_ok=True)
                    self.recording = None
                self.draft = None
            return {"ok": True}
        if action == "send":
            with self.lock:
                draft = self.draft
                if not draft or draft["id"] != data.get("draft_id") or draft["state"] != "ready":
                    raise ClientError("请重新录音并确认")
                ident, text = draft["thread_id"], draft["text"]
            limits = self.refresh_limits(force=True)
            if self.account.get("type") != "chatgpt":
                raise ClientError("仅支持已登录的 ChatGPT 额度，不使用付费 API")
            if limits["blocked"] or any(limits[k]["remaining"] <= 0 for k in ("primary", "secondary")
                                        if limits[k]["remaining"] != -1):
                raise ClientError("额度已用完，请等待重置")
            if limits["primary"]["remaining"] == -1:
                raise ClientError("无法确认可用额度，暂不发送")
            thread = self.rpc.call("thread/read", {"threadId": ident, "includeTurns": False})["thread"]
            if thread.get("modelProvider") != "openai":
                raise ClientError("此对话使用其他提供商，暂不发送")
            if self._pending_queue_count(ident) or (thread.get("status") or {}).get("type") == "active":
                return self._queue_draft(draft)
            if ident not in self.resumed:
                try:
                    self.rpc.call("thread/resume", {"threadId": ident, "excludeTurns": True})
                except RpcError as exc:
                    if exc.active_writer:
                        return self._queue_draft(draft)
                    raise
                self.resumed.add(ident)
            with self.lock:
                draft["state"] = "sending"
                previous_live = self.live.get(ident)
                self.live[ident] = {"status": "active", "output": ""}
            try:
                result = self.rpc.call("turn/start", {"threadId": ident,
                    "input": [{"type": "text", "text": text, "text_elements": []}]})
            except RpcError as exc:
                if exc.rejected:
                    with self.lock:
                        draft["state"] = "ready"
                        if previous_live is None:
                            self.live.pop(ident, None)
                        else:
                            self.live[ident] = previous_live
                    if exc.active_writer:
                        self.resumed.discard(ident)
                        return self._queue_draft(draft)
                    raise
                # A timeout may have accepted the turn: never auto-retry it.
                with self.lock:
                    draft["state"] = "uncertain"
                    draft["text"] = "发送结果待确认，请在电脑检查，勿重复发送"
                raise
            with self.lock:
                draft["state"] = "sent"
                self.history.pop(ident, None)
            return {"ok": True, "thread_id": ident, "turn_id": result.get("turn", {}).get("id", "")}
        raise ClientError("未知操作")

    def _pending_queue_count(self, ident):
        with self.lock:
            tracked = set(self.queued.get(ident, ()))
        if not tracked:
            return 0
        try:
            pending = self.rpc.call("thread/queue/list", {"threadId": ident, "limit": 100})
        except RpcError:
            pass  # Keep unverified entries; queue acceptance is not execution.
        else:
            if not pending.get("nextCursor"):
                found = {item.get("id") for item in pending.get("data", [])}
                with self.lock:
                    current = self.queued.get(ident, set())
                    # Preserve entries added while this read was in progress.
                    current.difference_update(tracked - found)
                    if not current:
                        self.queued.pop(ident, None)
        with self.lock:
            return len(self.queued.get(ident, ()))

    def _queue_draft(self, draft):
        ident = draft["thread_id"]
        with self.lock:
            if sum(len(items) for items in self.queued.values()) >= MAX_QUEUED_MESSAGES:
                raise ClientError("待处理语音已达32条，草稿已保留，请先在电脑处理")
            draft["state"] = "sending"
        try:
            result = self.rpc.call("thread/queue/add", {
                "threadId": ident, "clientUserMessageId": "passport-" + draft["id"],
                "input": [{"type": "text", "text": draft["text"], "text_elements": []}],
            })
            queued = result.get("queuedSubmission", {}).get("id")
            if not isinstance(queued, str) or not queued:
                raise RpcError("排队结果待确认，请在电脑检查，勿重复发送")
        except RpcError as exc:
            with self.lock:
                draft["state"] = "ready" if exc.rejected else "uncertain"
                if not exc.rejected:
                    draft["text"] = "排队结果待确认，请在电脑检查，勿重复发送"
            if exc.rejected:
                raise ClientError("未能加入对话队列，草稿已保留，请在电脑继续") from exc
            raise
        with self.lock:
            draft["state"] = "sent"
            self.queued.setdefault(ident, set()).add(queued)
            self.history.pop(ident, None)
        return {"ok": True, "thread_id": ident, "queued": True}

    def _transcribe(self, rec):
        try:
            text = self.asr(rec["path"]).strip()
            if self.simplifier is None:
                raise ClientError("请先安装本机中文转换组件")
            text = self.simplifier.convert(text)
            if not text:
                raise ClientError("没有识别到语音，请重新录音")
            if len(text) > MAX_DRAFT_CHARS:
                raise ClientError("识别内容过长，请分段说话")
            text = display_text(text, MAX_DRAFT_CHARS)
            with self.lock:
                if self.draft and self.draft["id"] == rec["id"]:
                    self.draft.update(state="ready", text=text)
        except Exception as exc:
            with self.lock:
                if self.draft and self.draft["id"] == rec["id"]:
                    self.draft.update(state="failed", text=str(exc) if isinstance(exc, ClientError) else "语音识别失败，请检查 Mac 模型后重新录音")
        finally:
            rec["path"].unlink(missing_ok=True)

    def transcribe(self, pcm):
        engine, model = voice_paths(self.root)
        wav = pcm.with_suffix(".wav")
        output = pcm.with_suffix(".text")
        try:
            with wave.open(str(wav), "wb") as stream:
                stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000)
                stream.writeframes(pcm.read_bytes())
            subprocess.run([str(engine), "-m", str(model),
                            "-f", str(wav), "-l", "zh", "-otxt", "-of", str(output),
                            "-nt", "-np", "-t", "4"],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            return Path(str(output) + ".txt").read_text(encoding="utf-8")
        finally:
            wav.unlink(missing_ok=True)
            Path(str(output) + ".txt").unlink(missing_ok=True)

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
        with self.lock:
            if self.recording:
                self.recording["path"].unlink(missing_ok=True)
        self.rpc.close()
