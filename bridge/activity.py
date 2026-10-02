"""Bounded card-local unread state and quiet, deduplicated task notifications."""
from collections import OrderedDict, deque
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time

DEFAULT_ALERTS = {"enabled": True, "sound": False, "quiet": True,
                  "start": "22:00", "end": "08:00"}


def validate_alerts(value):
    if not isinstance(value, dict):
        raise ValueError("提醒设置格式错误")
    result = {**DEFAULT_ALERTS, **{k: v for k, v in value.items() if k in DEFAULT_ALERTS}}
    if any(type(result[k]) is not bool for k in ("enabled", "sound", "quiet")):
        raise ValueError("提醒开关格式错误")
    for key in ("start", "end"):
        if not isinstance(result[key], str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", result[key]):
            raise ValueError("免打扰时间请填写 24 小时制 HH:MM")
    return result


def load_alerts(root):
    try:
        return validate_alerts(json.loads((Path(root) / "alerts.json").read_text()))
    except (OSError, ValueError):
        return dict(DEFAULT_ALERTS)


def save_alerts(root, value):
    settings = validate_alerts(value)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = root / "alerts.json.tmp"
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(settings, stream)
        temporary.replace(root / "alerts.json")
    finally:
        temporary.unlink(missing_ok=True)
    return settings


def quiet_now(settings, epoch):
    if not settings["quiet"]:
        return False
    minute = (int(epoch) // 60 + 8 * 60) % 1440
    def minutes(key):
        hour, value = map(int, settings[key].split(":"))
        return hour * 60 + value
    start, end = minutes("start"), minutes("end")
    # Equal endpoints mean an all-day quiet period.
    return start <= minute < end if start < end else minute >= start or minute < end


def thread_status(thread):
    status = thread.get("status") or {}
    if set(status.get("activeFlags") or ()) & {"waitingOnApproval", "waitingOnUserInput"}:
        return "needsDesktop"
    kind = status.get("type", "unknown")
    if kind == "systemError":
        return "error"
    turns = thread.get("turns") or []
    last = turns[-1] if turns else {}
    if kind in ("idle", "notLoaded", "unknown"):
        if last.get("status") == "failed":
            return "error"
        if kind == "notLoaded" and last.get("status") == "inProgress":
            return "unknown"  # Stored history is not proof that a task is still running.
        return "idle" if kind == "notLoaded" else kind
    return kind


def reply_revision(thread):
    if "_revision" in thread:
        return thread["_revision"]
    for turn in reversed(thread.get("turns") or []):
        for item in reversed(turn.get("items") or []):
            if item.get("type") == "agentMessage" and item.get("text"):
                payload = [turn.get("id"), item.get("id"), item["text"]]
                return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:32]
    return ""


class Activity:
    """Called under Companion.lock. No conversation text is persisted to disk."""
    def __init__(self, settings):
        self.settings = settings
        self.entries = OrderedDict()
        self.pending = deque(maxlen=8)
        self.events = OrderedDict()
        self.last_alert = -float("inf")
        self.suppress_until = 0

    def sound_allowed(self, epoch=None):
        return self.settings["sound"] and not quiet_now(self.settings, time.time() if epoch is None else epoch)

    def observe(self, ident, thread, title, status, *, suppressed=False, now=None):
        now = time.time() if now is None else now
        revision = reply_revision(thread)
        turns = thread.get("turns") or []
        last = turns[-1] if turns else {}
        completed = str(last.get("id") or "") if last.get("status") == "completed" else ""
        previous = self.entries.get(ident)
        unread = bool(previous and (previous["unread"] or (revision and revision != previous["revision"])))
        entry = {"revision": revision, "unread": unread, "status": status, "completed": completed}
        self.entries[ident] = entry
        self.entries.move_to_end(ident)
        while len(self.entries) > 32:
            self.entries.popitem(last=False)
        kind = ""
        # First observation establishes a baseline, not a burst of historical alerts.
        if previous:
            if status in ("needsDesktop", "error") and status != previous["status"]:
                kind = "attention"
            elif completed and completed != previous["completed"] and status == "idle":
                kind = "completed"
        ended = last.get("completedAt")
        occurred = ended if isinstance(ended, (int, float)) else now
        event = (ident, kind, str(last.get("id") or revision), status)
        fresh = event not in self.events
        if kind:
            self.events[event] = None
            while len(self.events) > 128:
                self.events.popitem(last=False)
        if kind and fresh and not suppressed and occurred > self.suppress_until and self.settings["enabled"] and not quiet_now(self.settings, now):
            self.pending.append({"id": secrets.token_hex(8), "thread_id": ident, "title": title,
                                 "kind": kind, "created": now})
        return entry

    def mark_read(self, ident, revision):
        entry = self.entries.get(ident)
        if entry and revision and revision == entry["revision"]:
            entry["unread"] = False

    def suppress(self):
        self.pending.clear()
        self.suppress_until = time.time()

    def notice(self, *, suppressed=False, now=None, monotonic=None):
        now = time.time() if now is None else now
        monotonic = time.monotonic() if monotonic is None else monotonic
        if suppressed or not self.settings["enabled"] or quiet_now(self.settings, now):
            self.pending.clear()
            return {}
        while self.pending and now - self.pending[0]["created"] > 90:
            self.pending.popleft()
        if not self.pending or monotonic - self.last_alert < 30:
            return {}
        self.last_alert = monotonic
        alert = self.pending.popleft()
        # Delivered once. A lost notification never causes an automatic replay.
        return {k: v for k, v in alert.items() if k != "created"} | {"sound": self.sound_allowed(now)}
