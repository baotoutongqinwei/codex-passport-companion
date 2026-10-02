"""Window-independent lifecycle. Transport reconnect never creates a new service."""
import threading
import time

from local_data import InstanceLock, voice_paths, install_model, use_model
from rpc import Codex, RpcError, codex_binary
from service import Companion, ClientError
from transports import run
from activity import load_alerts, save_alerts
from firmware import inspect_firmware, usb_devices, flash_firmware, bundled_firmware
from device_info import compare, presentation


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
        self.firmware_worker = None
        self.firmware = None
        self.firmware_catalog = bundled_firmware()
        self.alert_settings = load_alerts(root)
        self.view = {"codex": "等待自检", "account": "等待自检", "voice": "等待自检",
                     "connection": "尚未连接", "state": "idle", "busy": False,
                     "state_success": 0, "reconnects": 0,
                     "firmware_busy": False, "flashing": False, "flash_progress": 0,
                     "flash_detail": "通过 USB 数据线烧录；蓝牙无线连接不能刷机。",
                     "firmware_info": "请选择内置版本或本地合并 .bin 固件。", "usb_devices": [],
                     "detail": "先自检，再选择与卡片固件一致的连接方式。"}

    def update(self, **values):
        with self.lock:
            self.view.update(values)

    def snapshot(self):
        with self.lock:
            result = dict(self.view)
        result["voice"] = self.voice_status() if not result.get("model_busy") else result["voice"]
        result["pending"] = self.pending()
        device, age, recording = None, None, False
        if self.service:
            with self.service.lock:
                device = getattr(self.service, "device", None)
                at = getattr(self.service, "device_at", None)
                age = max(0, time.monotonic()-at) if at is not None else None
                recording = bool(self.service.recording or self.service.draft)
        connected = result["state"] in ("connected", "ready", "service_error")
        result["device"] = presentation(device, age, connected, recording)
        with self.lock:
            selected = self.firmware
        if selected:
            candidate = {"profile": selected.get("profile"), "version": selected["descriptor"]["version"],
                         "elf_sha256": selected["descriptor"]["embedded_elf_sha256"]}
            source = "所选固件"
        else:
            candidate = next((row for row in self.firmware_catalog if device and row["profile"] == device["profile"]), None)
            source = "内置固件"
        kind, message = compare(device, candidate)
        result["upgrade"] = {"kind": kind, "message": message, "source": source,
                             "version": candidate.get("version", "--") if candidate else "--",
                             "profile": candidate.get("profile") if candidate else None}
        if kind == "upgrade" and result["device"]["fresh"]:
            result["detail"] += f" · 固件可升级至 {candidate['version']}，请打开设备信息页。"
        return result

    def set_alerts(self, settings):
        settings = save_alerts(self.root, settings)
        with self.lock:
            self.alert_settings = settings
            if self.service:
                with self.service.lock:
                    self.service.activity.settings = settings
                    self.service.activity.suppress()
        self.update(detail="提醒设置已保存，免打扰使用 UTC+8；录音期间不播放声音。")

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
            if self.owner.file is None:
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
            with self.lock:
                service.activity.settings = self.alert_settings
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
            if self.closing or self.view["firmware_busy"] or (self.worker and self.worker.is_alive()):
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
            if state == "connected" and self.service:
                with self.service.lock:
                    self.service.device = None
                    self.service.device_at = None
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
        if self.view["flashing"]:
            return
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

    def _firmware_job(self, job):
        with self.lock:
            if self.closing or self.view["firmware_busy"]:
                return False
            self.view["firmware_busy"] = True
            def execute():
                try:
                    job()
                except (OSError, ValueError) as exc:
                    self.update(flash_detail=str(exc), detail=str(exc), state="error")
                except Exception:
                    self.update(flash_detail="操作未完成，请查看烧录记录，检查 USB 数据线和设备状态。", state="error")
                finally:
                    self.update(firmware_busy=False, flashing=False)
            self.firmware_worker = threading.Thread(target=execute, daemon=True)
            self.firmware_worker.start()
            return True

    def scan_usb(self):
        def scan():
            devices = usb_devices()
            self.update(usb_devices=devices, flash_detail="请选择要烧录的卡片。" if devices else
                        "未发现卡片：请开机，并使用 USB 数据线连接 Mac 后重新扫描。")
        return self._firmware_job(scan)

    def select_firmware(self, path, expected_hash=None, profile=None):
        def select():
            with self.lock:
                self.firmware = None
            self.update(firmware_info="正在校验固件…", flash_progress=0)
            firmware = inspect_firmware(path)
            if expected_hash and firmware["sha256"] != expected_hash:
                raise ValueError("内置固件校验失败，请重新下载完整应用")
            if profile and firmware.get("profile") and profile != firmware["profile"]:
                raise ValueError("固件模式与目录不匹配")
            firmware["profile"] = firmware.get("profile") or profile
            with self.lock:
                self.firmware = firmware
            descriptor = firmware["descriptor"]
            self.update(firmware_info=f"{descriptor['version']} · {firmware['size']/1048576:.2f} MB\n"
                        f"ESP32-C3 / 8 MB · SHA-256 {firmware['sha256'][:16]}…",
                        flash_detail="固件校验通过。请选择 USB 卡片并确认配置保留方式。")
        return self._firmware_job(select)

    def flash(self, expected_hash, device, preserve):
        # The caller binds the confirmation to a specific byte snapshot and USB
        # identity. Never permit an unrelated selection to replace it afterward.
        def perform():
            with self.lock:
                firmware = self.firmware
            if not firmware or firmware["sha256"] != expected_hash:
                raise ValueError("固件选择发生变化，请重新确认")
            if self.pending():
                raise ValueError("请先完成录音、处理草稿并在 Codex 确认队列，再烧录")
            self.update(flashing=True, flash_progress=0, flash_detail="正在安全暂停卡片连接…")
            self.stop.set()
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=40)
                if self.worker.is_alive():
                    raise ValueError("连接仍在处理请求，尚未烧录；请等待暂停完成后重试")
            if self.pending():
                raise ValueError("暂停时发现待处理草稿或队列，尚未烧录；请先处理后重试")
            if self.owner.file is None:
                self.owner.acquire()
            def progress(value, message):
                self.update(flash_progress=value, flash_detail=message, detail=message, state="flashing")
            flash_firmware(firmware, device, preserve, self.root, progress)
            self.update(state="idle", connection="烧录完成，等待重新连接", flash_profile=firmware.get("profile"))
        return self._firmware_job(perform)

    def close(self):
        if self.closing or self.view["firmware_busy"]:
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
