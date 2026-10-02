#!/usr/bin/env python3
"""Install the pinned offline speech engine. No paid services or API keys."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT/".local"
WHISPER_COMMIT = "48f628a84833905ee4a0658ee6d4a5c915ce1997"  # v1.8.7
MODEL_SHA256 = "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe"
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"


def run(*args):
    subprocess.run(args, check=True)


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(source.read()).hexdigest()


def main():
    # The recognition result is always normalized locally before card preview.
    run(sys.executable, "-m", "pip", "--isolated", "install", "--no-user",
        "--index-url", "https://pypi.org/simple", "opencc-python-reimplemented==0.1.7")
    for tool in ("git", "cmake", "curl"):
        if not shutil.which(tool):
            raise RuntimeError(f"Missing {tool}; activate the ESP-IDF environment first")
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    engine = LOCAL/"whisper.cpp"
    if not engine.exists():
        run("git", "clone", "--depth", "1", "--branch", "v1.8.7", "https://github.com/ggml-org/whisper.cpp.git", str(engine))
    commit = subprocess.check_output(["git", "-C", str(engine), "rev-parse", "HEAD"], text=True).strip()
    if commit != WHISPER_COMMIT:
        raise RuntimeError("Existing whisper.cpp revision differs; preserving it without replacement")
    run("cmake", "-S", str(engine), "-B", str(engine/"build"), "-DGGML_METAL=OFF", "-DWHISPER_BUILD_TESTS=OFF", "-DCMAKE_BUILD_TYPE=Release")
    run("cmake", "--build", str(engine/"build"), "--config", "Release", "-j", "4")
    model = LOCAL/"models/ggml-base.bin"
    model.parent.mkdir(exist_ok=True)
    if not model.exists():
        partial = model.with_suffix(".download")
        run("curl", "--fail", "--location", "--retry", "3", "--output", str(partial), MODEL_URL)
        if digest(partial) != MODEL_SHA256:
            raise RuntimeError("Downloaded model hash mismatch; model was not installed")
        partial.replace(model)
    if digest(model) != MODEL_SHA256:
        raise RuntimeError("Existing model hash mismatch; preserving it for investigation")
    print("Offline speech engine and multilingual base model: PASS")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
