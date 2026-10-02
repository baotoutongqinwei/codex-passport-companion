"""Local physical transports. BLE requires authenticated pairing on the card."""
import asyncio
import json
import struct
import threading
import time

from service import ClientError
from wire import Decoder, dispatch

SERVICE = "6e40f001-b5a3-f393-e0a9-e50e24dcca9e"
RX = "6e40f002-b5a3-f393-e0a9-e50e24dcca9e"
TX = "6e40f003-b5a3-f393-e0a9-e50e24dcca9e"
INFO = "6e40f004-b5a3-f393-e0a9-e50e24dcca9e"


def usb_devices():
    from serial.tools import list_ports
    return [p for p in list_ports.comports() if p.vid == 0x303A and p.pid == 0x1001]


def exchange_status(frame, response, report):
    # Metadata on state polls only; no per-audio-chunk I/O or second PCM decode.
    if response is None or not frame[2].startswith("/v1/state"):
        return
    status = struct.unpack_from("<H", response, 8)[0]
    if status == 200:
        report("ready", "已连接，时间、额度与对话状态同步成功")
    else:
        error = json.loads(response[16:-4]).get("error", "")
        if "rate limit" in error.lower() or "额度" in error:
            report("service_error", "卡片已连接，Codex 额度暂不可读；正在定期重试，请检查桌面账户与网络")
        else:
            report("service_error", "卡片已连接，Codex 状态暂不可读；请检查桌面账户、网络及版本")


def usb_loop(device, service, stop=None, report=lambda *_: None):
    stop = stop or threading.Event()
    decoder = Decoder()
    while not stop.is_set():
        # A fixed-size read waits for its timeout on each frame's short tail.
        # Read only queued bytes, or wait for the first byte while idle.
        for frame in decoder.feed(device.read(min(512, device.in_waiting or 1))):
            response = dispatch(service, frame)
            exchange_status(frame, response, report)
            if response is None:
                continue
            view = memoryview(response)
            deadline = time.monotonic()+5
            while view:
                if time.monotonic() > deadline:
                    raise ConnectionError("USB 写入超时")
                written = device.write(view)
                if not written:
                    raise ConnectionError("USB 连接已中断")
                view = view[written:]


def serve_usb(service, port=None, stop=None, report=lambda *_: None):
    import serial
    candidates = [p for p in usb_devices() if port is None or p.device == port]
    if len(candidates) != 1:
        raise ClientError("未找到唯一卡片，请连接 USB 数据线并用 --port 指定串口")
    identity = candidates[0].serial_number
    if not identity:
        raise ClientError("无法确认卡片 USB 序列号，请重新连接数据线")
    stop = stop or threading.Event()
    waiting = False
    while not stop.is_set():
        # USB re-enumeration may change the port. Never switch to another card.
        candidates = [p for p in usb_devices() if p.serial_number == identity]
        if len(candidates) > 1:
            raise ClientError("检测到重复 USB 标识，请只连接一张卡片")
        if not candidates:
            if not waiting:
                report("waiting", "USB 已断开，正在等待原卡片；请检查数据线和卡片电源")
                print("USB 已断开，等待同一张卡片重新连接；Ctrl+C 停止", flush=True)
            waiting = True
            stop.wait(1)
            continue
        device = serial.Serial(port=None, baudrate=115200, timeout=0.2, write_timeout=5)
        # Set control lines before opening to avoid intentionally resetting the card.
        device.dtr = device.rts = False
        device.port = candidates[0].device
        try:
            with device:
                report("connected", "USB 已连接；拔插后会自动连接原卡片")
                print(f"USB 已连接：{device.port}；支持自动重连；Ctrl+C 停止", flush=True)
                waiting = False
                usb_loop(device, service, stop, report)
        except (serial.SerialException, ConnectionError):
            service.transport_disconnected()
            if not waiting:
                report("waiting", "USB 通信中断，正在重连；中断录音需重录，草稿已保留")
                print("USB 通信中断，等待同一张卡片恢复；不会自动重发操作", flush=True)
            waiting = True
            stop.wait(1)


def bluetooth_error(exc):
    """Only stable, actionable text; OS errors can contain device identifiers."""
    reason = getattr(getattr(exc, "reason", None), "name", "")
    messages = {
        "POWERED_OFF": "Mac 蓝牙已关闭，请在系统设置中打开蓝牙后重试",
        "DENIED_BY_USER": "未获蓝牙权限，请在系统设置 → 隐私与安全性 → 蓝牙中允许本程序，然后重新打开",
        "DENIED_BY_SYSTEM": "系统策略禁止蓝牙访问，请联系电脑管理员允许本程序使用蓝牙",
        "DENIED_BY_UNKNOWN": "蓝牙权限不可用，请检查系统设置或联系电脑管理员",
        "NO_BLUETOOTH": "这台电脑没有可用的蓝牙适配器，请改用 USB",
        "NO_BLE_CENTRAL_ROLE": "蓝牙适配器不支持连接卡片，请改用 USB",
    }
    return messages.get(reason)


async def scan_ble():
    from bleak import BleakScanner
    from bleak.exc import BleakError
    try:
        devices = await BleakScanner.discover(timeout=8, service_uuids=[SERVICE], return_adv=True)
    except BleakError as exc:
        raise ClientError(bluetooth_error(exc) or "蓝牙扫描失败，请检查蓝牙开关及本程序的蓝牙权限后重试") from exc
    return [(device, adv) for device, adv in devices.values() if SERVICE in [x.lower() for x in adv.service_uuids]]


class LinkLost(ClientError):
    pass


class Stopped(Exception):
    pass


async def cancellable(operation, stop, timeout):
    """Cancel scans/pairing promptly, but never cancel an in-flight dispatch."""
    task = asyncio.ensure_future(operation)
    deadline = time.monotonic() + timeout
    try:
        while not task.done():
            if stop.is_set():
                raise Stopped()
            if time.monotonic() >= deadline:
                raise asyncio.TimeoutError()
            await asyncio.wait({task}, timeout=0.1)
        return await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def retry_delay(stop, seconds):
    deadline = time.monotonic() + seconds
    while not stop.is_set() and time.monotonic() < deadline:
        await asyncio.sleep(min(0.1, max(0, deadline-time.monotonic())))


async def ble_session(client, service, disconnected, stop=None, report=lambda *_: None):
    stop = stop or threading.Event()
    queue = asyncio.Queue(maxsize=4)
    decoder = Decoder()
    overflow = False

    def receive(_sender, data):
        nonlocal overflow
        for frame in decoder.feed(data):
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                overflow = True
                disconnected.set()

    # On macOS, accessing this protected characteristic opens the OS PIN dialog.
    protocol = await cancellable(client.read_gatt_char(INFO), stop, 120)
    if bytes(protocol) != b"CPv1-IMA":
        raise ClientError("卡片协议不匹配，请选择对应固件")
    await cancellable(client.start_notify(TX, receive), stop, 10)
    report("connected", "蓝牙已连接；临时断线会自动重连原卡片")
    try:
        while not disconnected.is_set() and not stop.is_set():
            try:
                frame = await asyncio.wait_for(queue.get(), 0.3)
            except asyncio.TimeoutError:
                continue
            response = await asyncio.to_thread(dispatch, service, frame)
            exchange_status(frame, response, report)
            if response is None:
                continue
            chunk = max(1, min(180, client.mtu_size-3))
            for offset in range(0, len(response), chunk):
                if disconnected.is_set():
                    raise LinkLost("蓝牙连接中断；正在重连，发送结果不确定时请在电脑确认")
                await asyncio.wait_for(client.write_gatt_char(RX, response[offset:offset+chunk], response=True), 10)
        if stop.is_set():
            return
        if overflow:
            raise ClientError("蓝牙请求过多，已停止连接")
        raise LinkLost("蓝牙连接中断；正在重连，中断录音需重录，草稿已保留")
    finally:
        if client.is_connected:
            try:
                await asyncio.wait_for(client.stop_notify(TX), 3)
            except Exception:
                pass


async def serve_ble(service, address=None, stop=None, report=lambda *_: None):
    from bleak import BleakClient
    from bleak.exc import BleakError
    stop = stop or threading.Event()
    identity = address.lower() if address else None
    delay, failures = 1, 0
    while not stop.is_set():
        connected = False
        def status(state, message):
            nonlocal connected, failures, delay
            if state == "connected":
                connected, failures, delay = True, 0, 1
            report(state, message)
        try:
            report("scanning", "正在查找原卡片" if identity else "正在查找卡片，请开机并使用蓝牙版固件")
            candidates = await cancellable(scan_ble(), stop, 12)
            if identity:
                candidates = [(d, a) for d, a in candidates if d.address.lower() == identity]
            if len(candidates) > 1:
                raise ClientError("发现多张卡片，请只开启目标卡片后重试，或用命令行 --address 指定设备")
            if not candidates:
                report("waiting", "未发现原卡片，自动查找中；请检查电源、距离及蓝牙版固件" if identity else
                       "未发现卡片，自动查找中；请检查电源、距离及蓝牙版固件")
            else:
                device, _ = candidates[0]
                identity = device.address.lower()
                disconnected = asyncio.Event()
                report("pairing", "正在连接；首次使用请在 Mac 输入卡片上的六位配对码")
                client = BleakClient(device, timeout=30, disconnected_callback=lambda _c: disconnected.set())
                try:
                    await cancellable(client.connect(), stop, 35)
                    await ble_session(client, service, disconnected, stop, status)
                finally:
                    service.transport_disconnected()
                    try:
                        await asyncio.wait_for(client.disconnect(), 5)
                    except Exception:
                        pass
                if stop.is_set():
                    return
        except Stopped:
            return
        except (BleakError, asyncio.TimeoutError, LinkLost) as exc:
            message = bluetooth_error(exc)
            if message:
                raise ClientError(message) from exc
            if not connected:
                failures += 1
            if failures >= 3:
                raise ClientError("连续三次连接或配对失败，已暂停；请检查六位配对码。若曾忽略设备，在卡片连接说明页长按中键清除配对后重试") from exc
            report("reconnecting", "蓝牙连接中断，正在重连原卡片；中断录音需重录，已有草稿保留")
        await retry_delay(stop, delay)
        delay = min(delay*2, 15)


def run(service, mode, address=None, stop=None, report=None):
    if report is None:
        last = None
        def report(_state, message):
            nonlocal last
            if message != last:
                print(message, flush=True)
                last = message
    try:
        if mode == "usb":
            serve_usb(service, address, stop, report)
        else:
            asyncio.run(serve_ble(service, address, stop, report))
    except ImportError as exc:
        raise ClientError("请先运行 tools/install_transport.sh 安装免费本地依赖") from exc
    except asyncio.TimeoutError as exc:
        raise ClientError("蓝牙超时，请检查系统蓝牙权限、卡片配对码和固件版本") from exc
