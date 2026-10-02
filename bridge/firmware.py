"""Validated, configuration-preserving USB updates for the standard Passport layout."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_firmware import FLASH_SIZE, parse_partition_table
from archive_firmware import application_descriptor

PROFILE_NAMES = {"ble": "蓝牙版", "usb": "USB 版", "offline": "离线工具版", "wifi": "Wi-Fi 版（需另行配网）"}
LAYOUT = [(1, 2, 0x9000, 0x6000, "nvs"), (1, 1, 0xf000, 0x1000, "phy_init"),
          (0, 0, 0x10000, 0x7f0000, "factory")]


def inspect_firmware(path):
    """Keep the bytes checked for the confirmation; never reopen a changed selection."""
    from esptool.bin_image import ESP32C3FirmwareImage
    with Path(path).open("rb") as source:
        data = source.read(FLASH_SIZE + 1)
    if not 0x11000 <= len(data) <= FLASH_SIZE:
        raise ValueError("请选择不超过 8 MB、从 0x0 刷写的完整合并固件")
    try:
        table = data[0x8000:0x8c00]
        partitions, md5 = parse_partition_table(table)
        if not md5 or [(p.kind, p.subtype, p.offset, p.size, p.label) for p in partitions] != LAYOUT:
            raise ValueError("仅支持本项目标准分区的完整固件；自定义分区请使用开发工具")
        images = []
        for offset, end in ((0, 0x8000), (0x10000, len(data))):
            # esptool's parser alone does not reject a bad checksum or SHA digest.
            with contextlib.redirect_stdout(io.StringIO()):
                image = ESP32C3FirmwareImage(io.BytesIO(data[offset:end]))
            if (image.chip_id != 5 or not image.append_digest or
                    image.checksum != image.calculate_checksum() or image.stored_digest != image.calc_digest or
                    image.flash_size_freq >> 4 != 3):
                raise ValueError("芯片、8 MB Flash 或固件校验不匹配")
            length = image.data_length + 32
            if offset + length > end:
                raise ValueError("固件不完整")
            images.append((offset, data[offset:offset+length]))
        images.insert(1, (0x8000, table))
        cursor = 0
        for offset, payload in images:
            if any(byte != 0xff for byte in data[cursor:offset]):
                raise ValueError("固件包含额外配置或分区数据，不能通过此入口烧录")
            cursor = offset + len(payload)
        if any(byte != 0xff for byte in data[cursor:]):
            raise ValueError("固件包含未识别的尾部数据")
        descriptor = application_descriptor(images[-1][1])
        import re
        modes = set(re.findall(rb"CPFW1:(ble|usb|wifi|offline)\x00", images[-1][1]))
        if len(modes) > 1:
            raise ValueError("固件模式标识冲突")
        profile = next(iter(modes)).decode() if modes else None
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("固件校验失败；请选择完整的 ESP32-C3 合并 .bin 文件") from exc
    return {"name": Path(path).name, "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data), "descriptor": descriptor, "profile": profile, "data": data, "images": images}


def bundled_firmware():
    base = (Path(sys._MEIPASS) / "firmware" if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[1] / "build/desktop-firmware")
    try:
        rows = json.loads((base / "catalog.json").read_text())
        return [{**row, "path": base / (row["profile"] + ".bin")} for row in rows
                if row.get("profile") in PROFILE_NAMES]
    except (OSError, ValueError, TypeError):
        return []


def usb_devices():
    from serial.tools import list_ports
    return [{"port": p.device, "serial": p.serial_number, "location": p.location,
             "vid": p.vid, "pid": p.pid} for p in list_ports.comports()
            if (p.vid, p.pid) == (0x303a, 0x1001) and p.serial_number]


def check_device(device):
    if device not in usb_devices():
        raise ValueError("所选卡片已拔出或端口身份改变，请重新扫描并选择")


def tool_command(args):
    if getattr(sys, "frozen", False):
        return [sys.executable, "--firmware-tool", *args]
    return [sys.executable, str(Path(__file__).resolve()), "--firmware-tool", *args]


def run_tool(args, log, report, timeout=180):
    """Run the bundled tool in isolation, with bounded output and a watchdog."""
    environment = dict(os.environ, PYTHONUNBUFFERED="1", PYINSTALLER_RESET_ENVIRONMENT="1")
    process = subprocess.Popen(tool_command(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, errors="replace", env=environment)
    lines = queue.Queue(maxsize=512)
    def read():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    output, deadline = [], time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() > deadline:
                raise ValueError("烧录工具响应超时。请保持 USB 连接，检查记录后重新烧录")
            try:
                line = lines.get(timeout=.2)
            except queue.Empty:
                continue
            if line is None:
                break
            log.write(line); log.flush()
            output.append(line)
            if len(output) > 512: output.pop(0)
            progress = re.search(r"Writing at 0x([0-9a-f]+).*\((\d+) %\)", line)
            if progress and int(progress[1], 16) >= 0x10000:
                report(10 + int(progress[2]) * .85, "正在写入固件，请保持 USB 连接…")
        result = process.wait(timeout=max(.1, deadline-time.monotonic()))
        if result != 0:
            detail = next((line.strip() for line in reversed(output) if "error" in line.lower()), "")
            raise ValueError("烧录未完成，请检查数据线与卡片开机状态后重试。" + ("\n"+detail[:180] if detail else ""))
        return "".join(output)
    finally:
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        process.stdout.close()


def flash_firmware(firmware, device, preserve, root, report):
    """Called only after the UI's explicit, exact-device confirmation."""
    check_device(device)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    log_path = root / "firmware-last.log"
    with tempfile.TemporaryDirectory(prefix="passport-flash-") as temporary, log_path.open("w") as log:
        os.chmod(log_path, 0o600)
        work = Path(temporary)
        full = work / "full.bin"
        full.write_bytes(firmware["data"])
        checked = inspect_firmware(full)
        if checked["sha256"] != firmware["sha256"]:
            raise ValueError("固件发生变化，请重新选择")
        log.write(f"Firmware SHA-256: {checked['sha256']}\nPreserve configuration: {preserve}\n")
        common = ["--chip", "esp32c3", "--port", device["port"], "--baud", "460800",
                  "--connect-attempts", "3", "--after", "hard_reset"]
        report(2, "正在确认 ESP32-C3 和 8 MB Flash…")
        probe = run_tool([*common, "flash_id"], log, report)
        if "Detected flash size: 8MB" not in probe:
            raise ValueError("未确认设备拥有 8 MB Flash，未写入；请检查所选设备")
        if preserve:
            report(5, "正在核对分区，保留已有配对和配置…")
            table = work / "device-partition.bin"
            run_tool([*common, "read_flash", "0x8000", "0xc00", str(table)], log, report)
            if table.read_bytes() != checked["images"][1][1]:
                raise ValueError("设备分区与固件不一致，未写入。首次安装可取消“保留配置”后重新确认")
        check_device(device)
        args = [*common, "write_flash", "--flash_mode", "keep", "--flash_freq", "keep",
                "--flash_size", "keep"]
        if preserve:
            for offset, payload in checked["images"]:
                part = work / f"{offset:x}.bin"
                part.write_bytes(payload)
                args += [hex(offset), str(part)]
        else:
            args += ["0x0", str(full)]
        report(10, "正在写入并校验，请勿拔线或关闭卡片…")
        output = run_tool(args, log, report)
        expected = 3 if preserve else 1
        if output.count("Hash of data verified.") != expected:
            raise ValueError("工具未返回完整的写后校验结果，请查看烧录记录")
        report(100, "烧录并校验成功，卡片已重启。请按对应模式重新连接。")
    return log_path


def tool_main():
    # Windowed frozen Python may set stdout/stderr to None. Reattach only in
    # this explicitly selected CLI child, before loading esptool.
    sys.stdout = os.fdopen(os.dup(1), "w", buffering=1)
    sys.stderr = os.fdopen(os.dup(2), "w", buffering=1)
    import esptool
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    esptool._main()


if __name__ == "__main__" and sys.argv[1:2] == ["--firmware-tool"]:
    tool_main()
