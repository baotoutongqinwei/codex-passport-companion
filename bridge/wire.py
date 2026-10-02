"""Bounded CPv1 framing shared by USB and authenticated BLE; no network listener."""
import json
import struct
import time
import zlib
from urllib.parse import parse_qs, urlsplit

from rpc import RpcError
from service import ClientError, display_text

HEADER = struct.Struct("<4sIHHI")
MAX_PATH, MAX_BODY = 1536, 8192


def encode(ident, status, path="", body=b""):
    path = path.encode("utf-8")
    if len(path) > MAX_PATH or len(body) > MAX_BODY or (status and path):
        raise ValueError("frame too large or invalid response path")
    frame = HEADER.pack(b"CPv1", ident, status, len(path), len(body)) + path + body
    return frame + struct.pack("<I", zlib.crc32(frame))


class Decoder:
    def __init__(self):
        self.buffer = bytearray()
        self.updated = 0.0

    def feed(self, data):
        # A stalled partial frame must not consume a subsequent request forever.
        now = time.monotonic()
        if now - self.updated > 10:
            self.buffer.clear()
        self.updated = now
        frames = []
        for byte in data:
            self.buffer.append(byte)
            while self.buffer and self.buffer[:4] != b"CPv1"[:min(4, len(self.buffer))]:
                del self.buffer[0]
            if len(self.buffer) < HEADER.size:
                continue
            _, ident, status, path_size, body_size = HEADER.unpack_from(self.buffer)
            if path_size > MAX_PATH or body_size > MAX_BODY or (status and path_size):
                self.buffer.clear()
                continue
            size = HEADER.size + path_size + body_size + 4
            if len(self.buffer) < size:
                continue
            packet = bytes(self.buffer)
            self.buffer.clear()
            if zlib.crc32(packet[:-4]) != struct.unpack_from("<I", packet, size-4)[0]:
                continue
            try:
                path = packet[16:16+path_size].decode("utf-8")
            except UnicodeDecodeError:
                continue
            frames.append((ident, status, path, packet[16+path_size:-4]))
        return frames


STEPS = (7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,
         60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,
         337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,
         1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,
         4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,
         13899,15289,16818,18500,20350,22385,24623,27086,29794,32767)
ADJUST = (-1,-1,-1,-1,2,4,6,8)


def decode_adpcm(data):
    if len(data) < 7:
        raise ClientError("音频压缩块不完整")
    count, predictor, index, reserved = struct.unpack_from("<HhBB", data)
    if not 1 <= count <= 2048 or index > 88 or reserved or len(data) != 6+(count+1)//2:
        raise ClientError("音频压缩块无效")
    samples = []
    for n in range(count):
        code = (data[6+n//2] >> (4*(n%2))) & 15
        step = STEPS[index]
        delta = (step >> 3) + (step if code & 4 else 0) + (step >> 1 if code & 2 else 0) + (step >> 2 if code & 1 else 0)
        predictor = max(-32768, min(32767, predictor + (-delta if code & 8 else delta)))
        index = max(0, min(88, index + ADJUST[code & 7]))
        samples.append(predictor)
    return struct.pack(f"<{count}h", *samples)


def dispatch(service, frame):
    ident, status, path, data = frame
    if status:  # Responses and stale boot chatter never become actions.
        return None
    try:
        if len(data) > 4096:
            raise ClientError("请求过大")
        url = urlsplit(path)
        if url.scheme or url.netloc or url.fragment:
            raise ClientError("请求路径无效")
        query = parse_qs(url.query, max_num_fields=4)
        value = lambda key, default="": query.get(key, [default])[0]
        if url.path == "/v1/state" and not data:
            result = service.state(value("thread"), value("cursor"), int(value("page", "-1")))
        elif url.path == "/v1/device":
            result = service.device_report(json.loads(data))
        elif url.path == "/v1/action":
            action = json.loads(data)
            if not isinstance(action, dict):
                raise ClientError("请求格式错误")
            result = service.action(action)
        elif url.path.startswith(("/v1/audio/", "/v1/audio-adpcm/")):
            pcm = decode_adpcm(data) if url.path.startswith("/v1/audio-adpcm/") else data
            result = service.audio(url.path.rsplit("/", 1)[-1], int(value("seq", "-1")), pcm)
        else:
            raise ClientError("未知请求")
        status = 200
    except (ValueError, RpcError) as exc:
        status, result = 409, {"error": display_text(exc, 100)}
    body = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()
    if len(body) > MAX_BODY:
        status, body = 500, b'{"error":"response too large"}'
    return encode(ident, status, body=body)
