#!/usr/bin/env python3
"""Codex Passport: local Wi-Fi/USB/BLE helper. No paid API fallback."""
import argparse
import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlsplit

from rpc import Codex, RpcError
from service import ClientError, Companion, display_text
from local_data import InstanceLock

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"


def load_config():
    return json.loads((LOCAL / "bridge.json").read_text())


def setup(host, port):
    address = ipaddress.ip_address(host)
    if not address.is_private or address.is_loopback:
        raise ClientError("请填写 Mac 的局域网 IP 地址")
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    if (LOCAL / "bridge.json").exists():
        raise ClientError("配置已存在，请保留配对信息；更换 IP 请先备份 .local/bridge.json 与证书")
    old_umask = os.umask(0o077)
    try:
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
                        "-sha256", "-nodes", "-days", "3650", "-subj", "/CN=Codex Passport",
                        "-addext", f"subjectAltName=IP:{address}",
                        "-keyout", str(LOCAL / "bridge-key.pem"), "-out", str(LOCAL / "bridge-cert.pem")],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        config = {"host": str(address), "port": port, "token": secrets.token_hex(32)}
        (LOCAL / "bridge.json").write_text(json.dumps(config, indent=2) + "\n")
    finally:
        os.umask(old_umask)
    print(f"已创建本机桥接配置：https://{address}:{port}；密钥仅保存在 .local/")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)
        self.connection.do_handshake()

    def log_message(self, *_):
        pass  # No audio, prompts, Wi-Fi credentials or tokens in access logs.

    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        if len(body) > 8192:
            status, body = 500, b'{"error":"response too large"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        expected = "Bearer " + self.server.token
        if not secrets.compare_digest(self.headers.get("Authorization", ""), expected):
            self.close_connection = True
            self.reply(401, {"error": "设备未配对，请用 USB 重新配置"})
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        try:
            url = urlsplit(self.path)
            if url.path != "/v1/state" or len(self.path) > 2048:
                raise ClientError("未知请求")
            query = parse_qs(url.query, max_num_fields=4)
            value = lambda key, default="": query.get(key, [default])[0]
            result = self.server.service.state(value("thread"), value("cursor"), int(value("page", "-1")))
            self.reply(200, result)
        except (ValueError, RpcError) as exc:
            self.reply(409, {"error": display_text(exc, 100)})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if not self.authorized():
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if self.headers.get("Transfer-Encoding") or not 0 <= length <= 4096:
                self.close_connection = True
                self.reply(413, {"error": "请求过大或长度无效"})
                return
            data = self.rfile.read(length)
            if len(data) != length:
                raise ClientError("请求不完整")
            url = urlsplit(self.path)
            if url.path == "/v1/action":
                parsed = json.loads(data)
                if not isinstance(parsed, dict):
                    raise ClientError("请求格式错误")
                result = self.server.service.action(parsed)
            elif url.path.startswith("/v1/audio/"):
                query = parse_qs(url.query, max_num_fields=1)
                seq = int(query.get("seq", ["-1"])[0])
                result = self.server.service.audio(url.path.split("/")[-1], seq, data)
            else:
                raise ClientError("未知请求")
            self.reply(200, result)
        except (ValueError, RpcError) as exc:
            self.reply(409, {"error": display_text(exc, 100)})
        except (BrokenPipeError, ConnectionResetError):
            pass


def create_server(service, token, host, port, cert, key):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def get_request(self):
            connection, address = super().get_request()
            # Handshake in the bounded-time worker, not the accept loop.
            return context.wrap_socket(connection, server_side=True, do_handshake_on_connect=False), address

    server = Server((host, port), Handler)
    server.service, server.token = service, token
    return server


def doctor():
    rpc = Codex()
    service = Companion(rpc, LOCAL)
    rpc.notify = service.notify
    try:
        rpc.start()
        state = service.state()
        print(json.dumps({"codex": "PASS", "visible_threads": len(state["threads"]),
                          "has_more_threads": bool(state["next"]), "quota": "PASS",
                          "offline_asr": "PASS" if service.asr_ready() else "NOT INSTALLED",
                          "tls_config": "PASS" if (LOCAL / "bridge.json").exists() else "NOT CONFIGURED"},
                         ensure_ascii=False, indent=2))
    finally:
        service.close()


def configure(port):
    try:
        import serial
    except ImportError as exc:
        raise ClientError("请用已安装 pyserial 的 ESP-IDF Python 运行此命令") from exc
    config = load_config()
    ssid = input("2.4 GHz Wi-Fi 名称：").strip()
    password = getpass.getpass("Wi-Fi 密码（不会显示或写入文件）：")
    if not 1 <= len(ssid.encode()) <= 32 or not 8 <= len(password.encode()) <= 63:
        raise ClientError("Wi-Fi 名称须为1至32字节，密码须为8至63字节")
    data = {"cmd": "configure", "ssid": ssid, "password": password,
            "url": f'https://{config["host"]}:{config["port"]}', "token": config["token"],
            "cert": (LOCAL / "bridge-cert.pem").read_text(), "epoch": int(time.time())}
    with serial.Serial(port, 115200, timeout=0.5, write_timeout=5) as device:
        device.dtr = False; device.rts = False
        time.sleep(1)
        device.write((json.dumps(data) + "\n").encode())
        deadline = time.monotonic()+12
        while time.monotonic() < deadline:
            line = device.readline()
            if b'"configured":true' in line:
                print("配置已保存，设备将重启并通过 Wi-Fi 连接 Mac。")
                return
            if b'"configured":false' in line:
                raise ClientError("设备拒绝配置，请检查参数")
    raise ClientError("配置未确认。请确认设备运行 Codex 助手固件；未执行刷机")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("setup", help="生成局域网 TLS 配对配置")
    cmd.add_argument("--host", required=True)
    cmd.add_argument("--port", type=int, default=8765)
    commands.add_parser("doctor", help="只读检查 Codex、额度和本地依赖")
    commands.add_parser("serve", help="启动局域网桥接服务")
    cmd = commands.add_parser("usb", help="通过 USB 使用 Codex，无需网络端口")
    cmd.add_argument("--port")
    cmd = commands.add_parser("ble", help="通过加密蓝牙使用 Codex")
    cmd.add_argument("--address", help="ble-scan 显示的设备标识，macOS 使用 UUID")
    commands.add_parser("ble-scan", help="扫描 CodexCard 蓝牙固件")
    cmd = commands.add_parser("configure", help="通过 USB 配置已刷入助手固件的设备")
    cmd.add_argument("--port", required=True)
    args = parser.parse_args()
    try:
        if args.command == "setup":
            setup(args.host, args.port)
        elif args.command == "doctor":
            doctor()
        elif args.command == "configure":
            configure(args.port)
        elif args.command == "ble-scan":
            import asyncio
            from transports import scan_ble
            for device, _adv in asyncio.run(scan_ble()):
                print(f"{device.address}  {device.name or 'CodexCard'}")
        else:
            rpc = Codex()
            service = Companion(rpc, LOCAL)
            rpc.notify = service.notify
            server = None
            owner = InstanceLock()
            try:
                owner.acquire()
                rpc.start()
                service.refresh_limits(force=True)
                if args.command in ("usb", "ble"):
                    from transports import run
                    run(service, args.command, args.port if args.command == "usb" else args.address)
                    return 0
                config = load_config()
                server = create_server(service, config["token"], config["host"], config["port"],
                                       LOCAL/"bridge-cert.pem", LOCAL/"bridge-key.pem")
                print(f'Codex 助手已启动：https://{config["host"]}:{config["port"]}；Ctrl+C 停止', flush=True)
                server.serve_forever(poll_interval=0.3)
            finally:
                if server:
                    server.server_close()
                service.close()
                owner.release()
    except KeyboardInterrupt:
        pass
    except ImportError:
        print("请先运行 tools/install_transport.sh 安装 USB/蓝牙依赖", file=sys.stderr)
        return 1
    except (ValueError, RpcError, OSError, subprocess.SubprocessError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
