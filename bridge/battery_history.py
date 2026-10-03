"""Import durable card battery readings through any supported connection."""
import csv
from datetime import datetime, timedelta, timezone
import fcntl
import os
from pathlib import Path
import re
import time

from firmware import usb_devices

BEGIN = re.compile(rb"CPBAT1:BEGIN,([0-9]{1,10}),([0-9]{1,3})$")
DATA = re.compile(rb"CPBAT1:D,([0-9]{1,10}),([0-9]{1,10}),([0-9]{1,10}),(-?[0-9]{1,3}),(-?[0-9]{1,5})$")
END = re.compile(rb"CPBAT1:END,([0-9]{1,10})$")
FIELDS = ("recorded_utc", "recorded_utc8", "imported_utc", "card_serial", "log_id", "sequence",
          "uptime_s", "battery_pct", "battery_mv")
UTC8 = timezone(timedelta(hours=8))


def receive_battery(root, data):
    """Validate and persist one replay-safe batch before acknowledging it."""
    if not isinstance(data, dict):
        raise ValueError("电量记录格式错误")
    identity, log_id, samples = data.get("card_serial"), data.get("log_id"), data.get("samples")
    healthy = data.get("storage_ok")
    if (not isinstance(identity, str) or not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", identity) or
            type(log_id) is not int or not 1 <= log_id <= 0xffffffff or
            not isinstance(samples, list) or len(samples) > 16 or type(healthy) is not bool):
        raise ValueError("电量记录头无效")
    rows, previous = [], 0
    for sample in samples:
        if not isinstance(sample, list) or len(sample) != 5 or any(type(v) is not int for v in sample):
            raise ValueError("电量记录行格式错误")
        seq, utc_s, uptime_s, percent, voltage_mv = sample
        if (not previous < seq <= 0xffffffff or not 0 <= uptime_s <= 0xffffffff or
                not -1 <= percent <= 100 or not (voltage_mv == -1 or 2500 <= voltage_mv <= 5500) or
                not (utc_s == 0 or 1700000000 <= utc_s < 4102444800)):
            raise ValueError("电量记录数值无效")
        rows.append(tuple(sample)); previous = seq
    added = 0
    if rows:
        try:
            _path, added = save_battery(root, identity, (log_id, rows))
        except OSError as exc:
            raise ValueError("电量记录未保存，请检查本机磁盘和权限") from exc
    summary = battery_summary(rows) if rows else ""
    if not healthy:
        summary += " · 卡片日志存储失败，请检查设备页"
    return ({"ok": True, "log_id": log_id, "ack": previous, "now": time.time()}, summary, added)


def battery_summary(samples):
    """Display gauge values and a bounded trend, without claiming charge current."""
    if not samples:
        return "尚无电量读数"
    newest = samples[-1]
    if newest[3] < 0:
        return "最近一次电量计读取失败；请结合 CSV 中的电压和前后记录"
    if not newest[1]:
        percent = f"{newest[3]}%"
        voltage = f" · {newest[4]} mV" if newest[4] > 0 else ""
        return f"最近记录 {percent}{voltage} · 时间未校准"
    valid = [row for row in samples if row[1] and row[3] >= 0]
    last = valid[-1]
    when = datetime.fromtimestamp(last[1], UTC8).strftime("%m-%d %H:%M")
    voltage = f" · {last[4]} mV" if last[4] > 0 else ""
    message = f"{when}  {last[3]}%{voltage}"
    recent = [row for row in valid if 0 <= last[1]-row[1] <= 3600]
    if len(recent) > 1 and last[1]-recent[0][1] >= 900 and all(
            newer[3] <= older[3] for older, newer in zip(recent, recent[1:])):
        message += f" · 近 {round((last[1]-recent[0][1])/60)} 分下降 {recent[0][3]-last[3]}%"
    return message


def _line(port, deadline):
    line = bytearray()
    while time.monotonic() < deadline:
        for byte in port.read(1):
            if byte == 10:
                result = bytes(line).strip()
                line.clear()
                marker = result.find(b"CPBAT1:")
                if marker >= 0:
                    return result[marker:]
            elif byte != 13:
                if len(line) < 160:
                    line.append(byte)
                else:
                    line.clear()
    return None


def fetch_battery(identity):
    """Return (log_id, rows) only for the exact card and complete export."""
    import serial
    matches = [device for device in usb_devices() if device["serial"] == identity]
    if len(matches) != 1:
        return None
    try:
        port = serial.Serial(port=None, baudrate=115200, timeout=.1,
                             write_timeout=.5, exclusive=True)
        port.dtr = port.rts = False
        port.port = matches[0]["port"]
        with port:
            port.reset_input_buffer()
            port.write(b"CPBAT1?\n")
            begin = _line(port, time.monotonic()+1.5)
            if begin == b"CPBAT1:ERR":
                raise ValueError("卡片电量记录不可用；请查看卡片设备页")
            match = BEGIN.fullmatch(begin or b"")
            if not match:
                if begin:
                    raise ValueError("卡片电量记录头格式错误")
                return None
            log_id, count = map(int, match.groups())
            if not log_id or count > 192:
                raise ValueError("电量记录头无效")
            rows, previous = [], 0
            deadline = time.monotonic()+20
            while len(rows) < count:
                match = DATA.fullmatch(_line(port, deadline) or b"")
                if not match:
                    raise ValueError("电量记录不完整或格式错误")
                seq, utc_s, uptime_s, percent, voltage_mv = map(int, match.groups())
                if (seq <= previous or not -1 <= percent <= 100 or
                        not (voltage_mv == -1 or 2500 <= voltage_mv <= 5500) or
                        not (utc_s == 0 or 1700000000 <= utc_s < 4102444800)):
                    raise ValueError("电量记录数值无效")
                rows.append((seq, utc_s, uptime_s, percent, voltage_mv))
                previous = seq
            match = END.fullmatch(_line(port, deadline) or b"")
            if not match or int(match[1]) != log_id:
                raise ValueError("电量记录结束标记缺失")
            return log_id, rows
    except (OSError, serial.SerialException):
        return None


def save_battery(root, identity, exported):
    """Append only unseen card samples to a private, user-readable CSV."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / "battery-history.csv"
    log_id, samples = exported
    imported = datetime.now(timezone.utc).isoformat(timespec="seconds")
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(handle, "r+", newline="") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        os.fchmod(stream.fileno(), 0o600)
        empty = os.fstat(stream.fileno()).st_size == 0
        reader = csv.DictReader(stream)
        if reader.fieldnames and tuple(reader.fieldnames) != FIELDS:
            raise ValueError("已有电量 CSV 格式不匹配，未覆盖原文件")
        seen = {(row["card_serial"], row["log_id"], row["sequence"]) for row in reader}
        fresh = []
        for seq, utc_s, uptime_s, percent, voltage_mv in samples:
            key = (identity, str(log_id), str(seq))
            if key in seen:
                continue
            recorded = datetime.fromtimestamp(utc_s, timezone.utc).isoformat(timespec="seconds") if utc_s else ""
            local = datetime.fromtimestamp(utc_s, UTC8).isoformat(timespec="seconds") if utc_s else ""
            fresh.append((recorded, local, imported, identity, log_id, seq, uptime_s, percent, voltage_mv))
        if not fresh:
            return path, 0
        stream.seek(0, os.SEEK_END)
        writer = csv.writer(stream)
        if empty:
            writer.writerow(FIELDS)
        writer.writerows(fresh)
        stream.flush()
        os.fsync(stream.fileno())
    return path, len(fresh)
