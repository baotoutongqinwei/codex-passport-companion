"""Private application data and optional, hash-checked local speech model."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import ssl
import tempfile
import urllib.request

MODEL_HASH = "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe"
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"


def data_root():
    if os.environ.get("PASSPORT_DATA_DIR"):
        return Path(os.environ["PASSPORT_DATA_DIR"]).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path.home() / "Library/Application Support/CodexPassport"
    return Path(__file__).resolve().parents[1] / ".local"


def voice_paths(root):
    root = Path(root)
    engine = (Path(sys._MEIPASS) / "voice/bin/whisper-cli" if getattr(sys, "frozen", False)
              else root / "whisper.cpp/build/bin/whisper-cli")
    model = root / "models/ggml-base.bin"
    try:
        value = json.loads((root / "voice.json").read_text()).get("model")
        if isinstance(value, str) and Path(value).is_absolute():
            model = Path(value)
    except (OSError, ValueError, AttributeError):
        pass
    return engine, model


def check_model(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024*1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != MODEL_HASH:
        raise ValueError("模型校验失败，请选择原始 ggml-base.bin 或重新下载")


def use_model(root, path):
    path = Path(path).resolve()
    check_model(path)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode="w", dir=root, delete=False) as out:
        temp = Path(out.name)
        json.dump({"model": str(path)}, out)
    try:
        os.replace(temp, root / "voice.json")
    finally:
        temp.unlink(missing_ok=True)


def install_model(root, report=lambda *_: None, cancelled=lambda: False):
    """Explicit user action only. Never replace a working model with a partial file."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = root / "models/ggml-base.bin"
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    if destination.is_file():
        try:
            use_model(root, destination)
            return
        except ValueError:
            pass
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as out:
        temp = Path(out.name)
        try:
            # Frozen Python must not depend on certificates in the build Mac's
            # Python.framework. Use the OS-provided trust bundle, without bypasses.
            context = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
            with urllib.request.urlopen(MODEL_URL, timeout=20, context=context) as response:
                total = 0
                while True:
                    if cancelled():
                        raise ValueError("下载已取消，下次可重新安装")
                    chunk = response.read(1024*1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > 160*1024*1024:
                        raise ValueError("模型下载大小异常，已停止")
                    out.write(chunk)
                    report(f"正在下载免费离线模型：{total // (1024*1024)} MB / 约 142 MB")
            out.flush()
            check_model(temp)
            os.replace(temp, destination)
            use_model(root, destination)
        finally:
            temp.unlink(missing_ok=True)


class InstanceLock:
    """One device owner per user, across GUI/CLI and different data directories."""
    def __init__(self, path=None):
        self.path = Path(path) if path else Path.home() / "Library/Application Support/CodexPassport/bridge.lock"
        self.file = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.file = self.path.open("a")
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.release()
            raise ValueError("另一份配套程序正在运行，请先退出它，避免同时连接卡片") from None

    def release(self):
        if self.file:
            self.file.close()
            self.file = None
