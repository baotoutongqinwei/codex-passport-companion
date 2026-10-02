"""Small concurrent JSON-RPC client for the installed Codex app-server."""
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading


class RpcError(RuntimeError):
    def __init__(self, message, *, rejected=False, code=None):
        super().__init__(message)
        self.rejected = rejected
        self.code = code

    @property
    def active_writer(self):
        return self.rejected and bool(re.search(
            r"\bthread(?:\s+\S+)?\s+already has an active writer\b", str(self), re.IGNORECASE))


def codex_binary():
    override = os.environ.get("PASSPORT_CODEX_BIN")
    candidates = [override] if override else [
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
        shutil.which("codex"),
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return path
    raise RpcError("未找到 Codex，请安装并登录桌面 App")


class Codex:
    def __init__(self, notify=lambda *_: None):
        self.notify = notify
        self.pending = {}
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.sequence = 0
        self.process = None

    def start(self):
        # Never persist account credentials or inherit API-key fallbacks.
        env = os.environ.copy()
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY"):
            env.pop(key, None)
        self.process = subprocess.Popen(
            [codex_binary(), "app-server"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, env=env,
        )
        threading.Thread(target=self._read, daemon=True).start()
        self.call("initialize", {
            "clientInfo": {"name": "codex_passport", "version": "0.1.0"},
            "capabilities": {"experimentalApi": True},
        })
        self._write({"method": "initialized"})

    def _write(self, data):
        with self.write_lock:
            if not self.process or self.process.poll() is not None:
                raise RpcError("Codex 连接已断开，请重启桥接程序")
            try:
                self.process.stdin.write(json.dumps(data, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise RpcError("Codex 连接已断开") from exc

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if "method" in message:
                    if "id" in message:
                        # Device never grants tool permissions automatically.
                        method = message["method"]
                        if method in ("item/commandExecution/requestApproval",
                                      "item/fileChange/requestApproval"):
                            self._write({"id": message["id"], "result": {"decision": "decline"}})
                        elif method == "item/tool/requestUserInput":
                            self._write({"id": message["id"], "result": {"answers": {}}})
                        else:
                            self._write({"id": message["id"], "error": {
                                "code": -32601, "message": "Handle this request in the desktop app"}})
                        self.notify("passport/needsDesktop", message.get("params", {}))
                    else:
                        self.notify(message["method"], message.get("params", {}))
                elif "id" in message:
                    with self.lock:
                        waiter = self.pending.get(message["id"])
                    if waiter:
                        waiter.put(message)
        finally:
            with self.lock:
                for waiter in self.pending.values():
                    waiter.put({"error": {"message": "Codex 服务已断开"}, "transport_error": True})

    def call(self, method, params=None, timeout=25):
        waiter = queue.Queue()
        with self.lock:
            self.sequence += 1
            ident = self.sequence
            self.pending[ident] = waiter
        try:
            self._write({"id": ident, "method": method, "params": params or {}})
            try:
                response = waiter.get(timeout=timeout)
            except queue.Empty as exc:
                raise RpcError(f"Codex 请求超时：{method}") from exc
            if "error" in response:
                error = response["error"]
                raise RpcError(str(error.get("message", "Codex 请求失败")),
                               rejected=not response.get("transport_error", False), code=error.get("code"))
            return response.get("result", {})
        finally:
            with self.lock:
                self.pending.pop(ident, None)

    def close(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
