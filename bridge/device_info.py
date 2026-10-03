"""Bounded local device readings and conservative, same-mode version comparison."""
import math
import re

PROFILES = {"ble": "蓝牙", "usb": "USB", "wifi": "Wi-Fi", "offline": "离线工具"}
INTEGER_LIMITS = {
    "revision": (0, 999), "cores": (1, 4), "cpu_mhz": (1, 240),
    "flash_bytes": (1, 32*1024**2), "psram_bytes": (0, 32*1024**2),
    "display_width": (1, 1024), "display_height": (1, 1024),
    "uptime_s": (0, 2**40), "reset_reason": (0, 32),
    "heap_total": (1, 1024**2), "heap_free": (0, 1024**2),
    "heap_min": (0, 1024**2), "heap_largest": (0, 1024**2),
    "app_used": (1, 32*1024**2), "app_capacity": (1, 32*1024**2),
    "nvs_used": (0, 100000), "nvs_free": (0, 100000), "nvs_total": (1, 100000),
    "battery_pct": (0, 100), "battery_mv": (1500, 5500), "rssi_dbm": (-127, 20),
    "tasks": (1, 256), "network_stack_min": (0, 128*1024),
}


def normalize(data):
    if not isinstance(data, dict) or type(data.get("schema")) is not int or data["schema"] != 1:
        raise ValueError("设备监控协议不支持")
    if data.get("chip") != "ESP32-C3" or data.get("profile") not in ("ble", "usb"):
        raise ValueError("设备监控仅支持 ESP32-C3 的 USB／蓝牙直连")
    result = {"chip": data["chip"], "profile": data["profile"]}
    for key in ("firmware", "idf"):
        value = data.get(key)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9.+_-]{1,48}", value):
            result[key] = value
    value = data.get("elf_sha256")
    if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value):
        result["elf_sha256"] = value
    for key, (low, high) in INTEGER_LIMITS.items():
        value = data.get(key)
        if type(value) is int and low <= value <= high:
            result[key] = value
    value = data.get("die_c")
    if type(value) in (int, float) and math.isfinite(value) and -40 <= value <= 125:
        result["die_c"] = value
    # Reject contradictory measurements as a group; never manufacture a percentage.
    for total, parts in (("heap_total", ("heap_free", "heap_min", "heap_largest")),
                         ("app_capacity", ("app_used",)), ("nvs_total", ("nvs_used", "nvs_free"))):
        if total not in result or any(result.get(k, 0) > result[total] for k in parts):
            for key in (total, *parts):
                result.pop(key, None)
    if result.get("heap_largest", 0) > result.get("heap_free", 0):
        result.pop("heap_largest", None)
    return result


def version(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value or "")
    return tuple(map(int, match.groups())) if match else None


def compare(current, candidate):
    if not current:
        return "unknown", "当前版本未知；旧固件需先更新才能上报"
    if not candidate:
        return "unknown", "没有可比较的同模式固件，请选择本地文件"
    if not candidate.get("profile"):
        return "unknown", "所选固件未标记模式，不能判断升级"
    if current["profile"] != candidate["profile"]:
        return "mode", "所选固件为另一种连接模式，属于模式切换"
    if current.get("elf_sha256") and current["elf_sha256"] == candidate.get("elf_sha256"):
        return "same", "与可用固件一致，无需升级"
    before, after = version(current.get("firmware")), version(candidate.get("version"))
    if before is None or after is None:
        return "unknown", "版本格式无法可靠排序，请核对构建信息"
    if after > before:
        return "upgrade", f"可升级：{current['firmware']} → {candidate['version']}"
    if after < before:
        return "newer", "卡片版本更高；所选固件属于降级"
    if current.get("elf_sha256") and candidate.get("elf_sha256"):
        return "different", "版本号相同但构建不同，请手动核对"
    return "unknown", "版本号相同，缺少构建标识，无法确认一致"


def size(value):
    if value is None:
        return "--"
    return f"{value/1024**2:.2f} MiB" if value >= 1024**2 else f"{value/1024:.1f} KiB"


def presentation(data, age, connected, recording=False):
    d = data or {}
    fresh = connected and age is not None and age <= 15 and not recording
    if recording:
        status = "录音／发送时暂停采样，显示上次数据"
    elif not connected:
        status = "未连接 · 数据不会继续刷新" if not d else "连接已断开 · 以下为上次数据"
    elif age is None:
        status = "等待卡片上报；旧固件需先更新，正常约每 5 秒刷新"
    elif fresh:
        status = f"实时监控 · {int(age)} 秒前更新 · 约每 5 秒刷新"
    else:
        status = f"数据已暂停刷新 · {int(age)} 秒前采样"
    free, total = d.get("heap_free"), d.get("heap_total")
    used = total-free if free is not None and total is not None else None
    app, capacity = d.get("app_used"), d.get("app_capacity")
    seconds = d.get("uptime_s")
    reset = {1: "上电", 2: "外部复位", 3: "软件重启", 4: "异常重启", 5: "中断看门狗",
             6: "任务看门狗", 7: "其他看门狗", 8: "深度睡眠唤醒", 9: "欠压复位", 10: "SDIO 复位"}
    revision = d.get("revision")
    hardware = "--" if revision is None else f"ESP32-C3 v{revision//100}.{revision%100} · {d.get('cores', '--')} 核 · 配置 {d.get('cpu_mhz', '--')} MHz"
    return {
        "fresh": fresh, "status": status,
        "version": f"当前固件 {d.get('firmware', '--')} · {PROFILES.get(d.get('profile'), '未识别模式')}",
        "heap": f"{size(used)} / {size(total)}", "heap_percent": used*100/total if used is not None else 0,
        "heap_note": f"空闲 {size(free)} · 最小 {size(d.get('heap_min'))}\n最大连续空闲 {size(d.get('heap_largest'))}",
        "app": f"{size(app)} / {size(capacity)}", "app_percent": app*100/capacity if app is not None and capacity else 0,
        "app_note": f"应用分区占用 · Flash 总容量 {size(d.get('flash_bytes'))}\n不是个人文件存储空间",
        "battery": f"{d['battery_pct']}%" if 'battery_pct' in d else "--",
        "voltage": f"{d['battery_mv']/1000:.3f} V" if 'battery_mv' in d else "电压不可用",
        "temperature": f"{d['die_c']:.1f} °C" if 'die_c' in d else "--",
        "uptime": f"{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}" if seconds is not None else "--",
        "hardware": hardware,
        "peripherals": f"{d.get('display_width', '--')} × {d.get('display_height', '--')} · ST7789 / ES8311 / CW2017",
        "memory_spec": ("SRAM 400 KB · RTC 8 KB · " + ("无 PSRAM" if d.get("psram_bytes") == 0
                        else "PSRAM " + size(d.get("psram_bytes")))) if d.get("chip") == "ESP32-C3" else "--",
        "radio": "USB · 信号强度不适用" if d.get("profile") == "usb" else
                 f"蓝牙 RSSI {d['rssi_dbm']} dBm" if 'rssi_dbm' in d else "信号强度不可用",
        "nvs": f"已用 {d.get('nvs_used', '--')} / 总计 {d.get('nvs_total', '--')} 条目 · 空闲 {d.get('nvs_free', '--')}",
        "tasks": f"{d.get('tasks', '--')} 个任务 · 通信任务最小栈余量 {size(d.get('network_stack_min'))}",
        "reset": reset.get(d.get('reset_reason'), '未知'),
        "build": f"IDF {d.get('idf', '--')} · ELF {d.get('elf_sha256', '--')[:16]}",
    }
