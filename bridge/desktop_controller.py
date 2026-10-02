"""Window-independent lifecycle. Transport reconnect never creates a new service."""
import threading

from local_data import InstanceLock, voice_paths, install_model, use_model
from rpc import Codex, RpcError, codex_binary
from service import Companion, ClientError
from transports import run


class DesktopController:
    def __init__(self, root):
        self.root = root
        self.lock = threading.RLock()
        self.owner = InstanceLock()
        self.service = None
        self.worker = None
        self.stop = threading.Event()
        self.closing = False
        self.closed = False
        self.view = {"codex": "等待自检", "account": "等待自检", "voice": "等待自检",
                     "connection": "尚未连接", "state": "idle", "busy": False,
                     "state_success": 0, "reconnects": 0,
                     "detail": "先自检，再选择与卡片固件一致的连接方式。"}

    def update(self, **values):
        with self.lock:
            self.view.update(values)

    def snapshot(self):
        with self.lock:
            result = dict(self.view)
        result["voice"] = self.voice_status() if not result.get("model_busy") else result["voice"]
        result["pending"] = self.pending()
        return result

    def voice_status(self):
        engine, model = voice_paths(self.root)
        if not engine.is_file():
            return "引擎缺失，请重新下载完整应用"
        if not model.is_file():
            return "未安装 · 可下载约 142 MB 或选择已有模型"
        return "本机识别 · 简体中文 · 无额外费用"

    def pending(self):
        service = self.service
        if not service:
            return False
        with service.lock:
            draft = (service.draft or {}).get("state", "")
            return bool(service.recording or draft in ("ready", "transcribing", "sending", "uncertain")
                        or any(service.queued.values()))

    def _ready(self):
        # Keeping the RPC process and service preserves dedupe and draft state.
        codex_binary()
        self.update(codex="已找到 Codex")
        if self.service is None:
            self.owner.acquire()
            rpc = Codex()
            service = Companion(rpc, self.root)
            rpc.notify = service.notify
            try:
                rpc.start()
            except Exception:
                service.close()
                self.owner.release()
                raise
            self.service = service
        account = self.service.rpc.call("account/read").get("account") or {}
        if account.get("type") != "chatgpt":
            self.update(account="请先在 Codex 桌面应用中登录 ChatGPT 账户")
            raise ClientError("登录后重新自检；本程序不使用 API Key 或付费识别接口")
        self.update(account="ChatGPT 账户已登录")
        try:
            self.service.refresh_limits(force=True)
        except RpcError:
            self.update(account="已登录 · 额度暂不可读")
            # A transient quota backend failure must not shut down reconnection.
        self.update(codex="Codex 服务可用")

    def _launch(self, job):
        with self.lock:
            if self.closing or (self.worker and self.worker.is_alive()):
                return False
            self.stop.clear()
            self.view["busy"] = True
            def execute():
                try:
                    job()
                except (ClientError, ValueError) as exc:
                    self.update(state="error", detail=str(exc))
                except RpcError:
                    self.update(state="error", detail="Codex 服务暂不可用，请检查桌面登录状态和网络后重试；保留中的草稿不会自动发送")
                except Exception:
                    self.update(state="error", detail="操作未完成，请检查设备、磁盘空间和系统权限后重试")
                finally:
                    self.update(busy=False, model_busy=False)
            self.worker = threading.Thread(target=execute, daemon=True)
            self.worker.start()
            return True

    def doctor(self):
        def check():
            self.update(state="checking", detail="正在检查 Codex 登录和本机语音组件…")
            self._ready()
            self.update(state="idle", detail="自检完成。连接后会验证卡片协议；语音模型可以按需安装。")
        return self._launch(check)

    def connect(self, mode):
        def report(state, message):
            with self.lock:
                if state == "ready":
                    self.view["state_success"] += 1
                if state == "reconnecting":
                    self.view["reconnects"] += 1
            self.update(state=state, connection=message, detail=message)
        def connect():
            self._ready()
            try:
                run(self.service, mode, stop=self.stop, report=report)
            finally:
                self.service.transport_disconnected()
            self.update(state="idle", connection="连接已暂停", detail="草稿保留在本次程序中；点击连接可继续。")
        return self._launch(connect)

    def pause(self):
        self.stop.set()
        self.update(detail="正在停止连接，等待当前操作完成…")

    def model(self, existing=None):
        def install():
            self.update(model_busy=True, voice="正在校验模型…", state="checking")
            if existing:
                use_model(self.root, existing)
            else:
                install_model(self.root, lambda text: self.update(voice=text), self.stop.is_set)
            self.update(state="idle", detail="模型已通过 SHA-256 校验，离线识别可用。")
        return self._launch(install)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.stop.set()
        def finish():
            try:
                if self.worker:
                    self.worker.join()
                if self.service:
                    self.service.close()
            finally:
                self.owner.release()
                self.closed = True
        threading.Thread(target=finish, daemon=True).start()
