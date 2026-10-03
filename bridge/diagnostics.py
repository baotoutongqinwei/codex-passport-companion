"""Bounded, in-memory card diagnostics. Never retain conversation or audio payloads."""
from collections import deque
from datetime import datetime
import secrets
import threading
import time


COMMANDS = {
    "device": "设备概况",
    "battery": "电池与温度",
    "memory": "内存与任务",
    "version": "固件身份",
}


class Diagnostics:
    def __init__(self):
        self.lock = threading.RLock()
        self.events = deque(maxlen=160)
        self.pending = None
        self.completed = deque(maxlen=16)
        self.revision = 0
        self.last_periodic = {}
        self.add("系统", "诊断控制台已就绪")

    def add(self, category, message):
        with self.lock:
            line = f"{datetime.now().strftime('%H:%M:%S')}  {category}  {message}"
            self.events.append(line)
            self.revision += 1

    def trace(self, route, status, error=""):
        now = time.monotonic()
        if route == "audio" and status == 200:
            return  # Audio chunks are frequent and contain private speech.
        if route in ("state", "device", "battery") and status == 200:
            with self.lock:
                if now - self.last_periodic.get(route, -1e9) < 30:
                    return
                self.last_periodic[route] = now
        detail = f" · {error[:100]}" if status != 200 and error else ""
        self.add("通信" if status == 200 else "错误", f"卡片 {route} → Mac：{status}{detail}")

    def queue(self, name):
        if name not in COMMANDS:
            raise ValueError("未知卡片诊断命令")
        with self.lock:
            self._expire()
            if self.pending:
                raise ValueError("上一条诊断命令尚未返回")
            self.pending = {"id": secrets.token_hex(8), "name": name, "at": time.monotonic()}
            self.add("命令", f"等待卡片执行：{COMMANDS[name]}")
            return self.pending["id"]

    def _expire(self):
        if self.pending and time.monotonic() - self.pending["at"] > 30:
            self.add("错误", f"{COMMANDS[self.pending['name']]} 超时；检查连接和卡片固件版本")
            self.pending = None

    def offer(self):
        with self.lock:
            self._expire()
            return {key: self.pending[key] for key in ("id", "name")} if self.pending else None

    def complete(self, value):
        if not isinstance(value, dict):
            raise ValueError("诊断结果格式错误")
        ident, name, result = (value.get(key) for key in ("id", "name", "text"))
        if not isinstance(ident, str) or not isinstance(name, str) or not isinstance(result, str):
            raise ValueError("诊断结果格式错误")
        if len(result.encode("utf-8")) > 768 or any(ord(char) < 32 and char not in "\n\t" for char in result):
            raise ValueError("诊断结果过长或含无效字符")
        with self.lock:
            if ident in self.completed:
                return {"ok": True}
            self._expire()
            if not self.pending or (ident, name) != (self.pending["id"], self.pending["name"]):
                raise ValueError("诊断命令已过期或不匹配")
            self.completed.append(ident)
            self.pending = None
            self.add("卡片", f"{COMMANDS[name]}：{result.strip() or '--'}")
        return {"ok": True}

    def snapshot(self):
        with self.lock:
            self._expire()
            return {"lines": tuple(self.events), "pending": bool(self.pending), "revision": self.revision}
