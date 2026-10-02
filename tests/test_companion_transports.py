"""Exercise actual firmware codecs against host transport and fake Codex, offline."""
import asyncio
import ctypes as C
import json
import math
import os
from pathlib import Path
import random
import select
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
from wire import Decoder, encode, dispatch, decode_adpcm
from transports import usb_loop, serve_usb, ble_session, RX, TX, INFO
from service import Companion, ClientError
from test_companion_bridge import FakeRpc


class Parser(C.Structure):
    _fields_ = [("bytes", C.c_ubyte*9748), ("used", C.c_size_t), ("expected", C.c_size_t)]


class Frame(C.Structure):
    _fields_ = [("ident", C.c_uint32), ("status", C.c_uint16), ("path_size", C.c_uint16),
                ("body_size", C.c_uint32), ("path", C.c_void_p), ("body", C.c_void_p)]


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        lib = Path(cls.build.name)/"codec.so"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                        str(ROOT/"main/companion_wire.c"), str(ROOT/"main/companion_adpcm.c"), "-o", str(lib)], check=True)
        cls.lib = C.CDLL(str(lib))
        cls.lib.cp_wire_encode.argtypes = [C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint16,C.c_char_p,C.c_void_p,C.c_size_t]
        cls.lib.cp_wire_encode.restype = C.c_size_t
        cls.lib.cp_wire_feed.argtypes = [C.POINTER(Parser),C.c_ubyte,C.POINTER(Frame)]
        cls.lib.cp_wire_feed.restype = C.c_bool
        cls.lib.cp_adpcm_encode.argtypes = [C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t]
        cls.lib.cp_adpcm_encode.restype = C.c_size_t

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.rpc = FakeRpc()
        self.service = Companion(self.rpc,self.temp.name,asr=lambda _: "检查代码")

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def cdecode(self, packet):
        parser, frame, frames = Parser(), Frame(), []
        for byte in packet:
            if self.lib.cp_wire_feed(C.byref(parser), byte, C.byref(frame)):
                frames.append((frame.ident, frame.status, C.string_at(frame.path,frame.path_size).decode(),
                               C.string_at(frame.body,frame.body_size)))
        self.assertLessEqual(parser.used,9748)
        return frames

    def test_bidirectional_wire_and_bounds(self):
        for size in (0,1,256,4096,8192):
            payload = random.Random(size).randbytes(size)
            for status,path in ((0,"/v1/state?thread=中文"),(200,"")):
                py = encode(0x12345678,status,path,payload)
                out = C.create_string_buffer(9748)
                n = self.lib.cp_wire_encode(out,len(out),0x12345678,status,path.encode(),payload,len(payload))
                self.assertEqual(out.raw[:n],py)
                self.assertEqual(self.cdecode(py),[(0x12345678,status,path,payload)])
                decoder, frames = Decoder(), []
                for i in range(0,len(py),7): frames += decoder.feed(py[i:i+7])
                self.assertEqual(frames,[(0x12345678,status,path,payload)])
        out=C.create_string_buffer(32)
        self.assertEqual(self.lib.cp_wire_encode(out,32,1,0,b"/"*1537,None,0),0)
        self.assertEqual(self.lib.cp_wire_encode(out,32,1,200,b"path",None,0),0)

    def test_corruption_noise_and_timeout(self):
        good=encode(99,200,body=b'{}')
        corrupt=bytearray(good); corrupt[-1]^=1
        badsize=struct.pack("<4sIHHI",b"CPv1",1,0,65535,0)
        stream=b"ESP-ROM:boot\r\nCCP"+corrupt+badsize+good
        self.assertEqual(self.cdecode(stream),[(99,200,"",b'{}')])
        self.assertEqual(Decoder().feed(stream),[(99,200,"",b'{}')])
        decoder=Decoder(); decoder.feed(encode(1,0,"/v1/state")[:18]); decoder.updated=0
        self.assertEqual(decoder.feed(good),[(99,200,"",b'{}')])
        noise=random.Random(1).randbytes(100000)
        self.assertEqual(self.cdecode(noise+good),[(99,200,"",b'{}')])

    def test_adpcm_c_encoder_python_decoder(self):
        for count in (1,31,1024,2048):
            samples=[int(12000*math.sin(i*2*math.pi*440/16000)) for i in range(count)]
            pcm=struct.pack(f"<{count}h",*samples); out=C.create_string_buffer(1030)
            n=self.lib.cp_adpcm_encode(pcm,count,out,len(out))
            self.assertEqual(n,6+(count+1)//2)
            decoded=struct.unpack(f"<{count}h",decode_adpcm(out.raw[:n]))
            error=sum((a-b)**2 for a,b in zip(samples,decoded))/count
            self.assertLess(math.sqrt(error),900)
            self.assertEqual(self.lib.cp_adpcm_encode(pcm,count,out,n-1),0)
        for bad in (b"",b"\0"*7,struct.pack("<HhBB",1,0,89,0)+b"\0"):
            with self.assertRaises(ClientError): decode_adpcm(bad)

    def test_dispatch_state_action_idempotence_and_errors(self):
        reply=Decoder().feed(dispatch(self.service,(8,0,"/v1/state?thread=thread-a",b"")))[0]
        self.assertEqual(reply[1],200); self.assertEqual(json.loads(reply[3])["id"],"thread-a")
        self.service.draft={"id":"draft-a","thread_id":"thread-a","state":"ready","text":"检查代码"}
        data=json.dumps({"action":"send","request_id":"usb-request-00000001","draft_id":"draft-a"}).encode()
        for _ in range(2): self.assertEqual(Decoder().feed(dispatch(self.service,(9,0,"/v1/action",data)))[0][1],200)
        self.assertEqual(sum(method=="turn/start" for method,_ in self.rpc.calls),1)
        for path,data in (("/v1/action",b"[]"),("/unknown",b""),("/v1/state?page=x",b"")):
            self.assertEqual(Decoder().feed(dispatch(self.service,(1,0,path,data)))[0][1],409)
        self.assertIsNone(dispatch(self.service,(1,200,"",b"{}")))

    def test_usb_real_pty_fragmented_roundtrip(self):
        import fcntl
        import pty
        import termios
        import tty
        master,slave=pty.openpty(); tty.setraw(slave)
        stop=threading.Event()
        class Device:
            @property
            def in_waiting(self):
                return struct.unpack('I',fcntl.ioctl(master,termios.FIONREAD,struct.pack('I',0)))[0]
            def read(self,size): return os.read(master,size) if select.select([master],[],[],0.1)[0] else b""
            def write(self,data): return os.write(master,data[:23])
        errors=[]
        def worker():
            try: usb_loop(Device(),self.service,stop)
            except Exception as exc: errors.append(exc)
        thread=threading.Thread(target=worker); thread.start()
        try:
            request=encode(4,0,"/v1/state?thread=thread-a")
            for i in range(0,len(request),3): os.write(slave,request[i:i+3])
            decoder=Decoder(); frames=[]
            for _ in range(100):
                if select.select([slave],[],[],0.1)[0]: frames += decoder.feed(os.read(slave,71))
                if frames: break
            self.assertEqual(frames[0][:3],(4,200,""))
            self.assertEqual(json.loads(frames[0][3])["id"],"thread-a")
        finally:
            stop.set(); thread.join(2); os.close(master); os.close(slave)
        self.assertFalse(thread.is_alive()); self.assertFalse(errors)

    def test_usb_audio_ack_does_not_wait_for_serial_read_timeout(self):
        # pyserial read(n) waits for n bytes or timeout. The card waits for an
        # ACK before sending another chunk, so padding cannot fill a short tail.
        for size in (1024,2048):
            with self.subTest(chunk_bytes=size):
                stop=threading.Event(); self_test=self
                self.service.asr_ready=lambda: True
                rec=self.service.action(dict(action='record_start',
                    request_id=f'audio-latency-{size:08d}',thread_id='thread-a'))
                ident=rec['record_id']
                packets=[encode(seq+1,0,f'/v1/audio/{ident}?seq={seq}',b'\0'*size)
                         for seq in range(20)]
                class Device:
                    pending=bytearray(packets[0])
                    acknowledgements=0
                    timeout_waits=0
                    @property
                    def in_waiting(self): return len(self.pending)
                    def read(self,count):
                        self_test.assertGreater(count,0); self_test.assertLessEqual(count,512)
                        if count>len(self.pending): self.timeout_waits+=1
                        data=bytes(self.pending[:count]); del self.pending[:count]
                        return data
                    def write(self,data):
                        reply=Decoder().feed(bytes(data))[0]
                        self_test.assertEqual(reply[:2],(self.acknowledgements+1,200))
                        self.acknowledgements+=1
                        if self.acknowledgements==len(packets): stop.set()
                        else: self.pending.extend(packets[self.acknowledgements])
                        return len(data)
                device=Device()
                try:
                    usb_loop(device,self.service,stop)
                    self.assertEqual(device.acknowledgements,20)
                    self.assertEqual(self.service.recording['size'],20*size)
                    self.assertEqual(device.timeout_waits,0,
                        'waiting 200 ms per ACK cannot sustain 32 kB/s microphone PCM')
                finally:
                    self.service.transport_disconnected()

    def test_ble_authenticated_fragmentation_and_disconnect(self):
        async def exercise():
            disconnected=asyncio.Event(); decoder=Decoder(); replies=[]
            class Client:
                mtu_size=128
                is_connected=True
                async def read_gatt_char(self,uuid):
                    self_test.assertEqual(uuid,INFO); return b"CPv1-IMA"
                async def start_notify(self,uuid,callback):
                    self_test.assertEqual(uuid,TX)
                    request=encode(71,0,"/v1/state?thread=thread-a")
                    for i in range(0,len(request),13): callback(None,request[i:i+13])
                async def write_gatt_char(self,uuid,data,response):
                    self_test.assertEqual(uuid,RX); self_test.assertTrue(response); self_test.assertLessEqual(len(data),125)
                    replies.extend(decoder.feed(data))
                    if replies: disconnected.set()
                async def stop_notify(self,uuid): self.stopped=True
            self_test=self; client=Client()
            with self.assertRaisesRegex(ClientError,"连接中断"):
                await ble_session(client,self.service,disconnected)
            self.assertEqual(replies[0][:2],(71,200)); self.assertTrue(client.stopped)
            async def incompatible(_): return b"wrong"
            client.read_gatt_char=incompatible
            with self.assertRaisesRegex(ClientError,"协议不匹配"):
                await ble_session(client,self.service,asyncio.Event())
        asyncio.run(exercise())

    def test_usb_reconnect_tracks_identity_and_rejects_other_card(self):
        def port(name, serial): return SimpleNamespace(device=name,serial_number=serial)
        old=port('/dev/card-a','card-a'); new=port('/dev/card-new','card-a')
        other=port('/dev/card-b','card-b')
        class SerialError(OSError): pass
        class Stop:
            stopped=False
            def is_set(self): return self.stopped
            def wait(self,_): return self.stopped
        stop=Stop(); opened=[]; closed=[]
        class Device:
            def __init__(self,**_): pass
            def __enter__(self):
                self_test.assertFalse(self.dtr); self_test.assertFalse(self.rts)
                opened.append(self.port); return self
            def __exit__(self,*_): closed.append(self.port)
        def connected(device,service,passed_stop,report):
            self.assertIs(service,self.service); self.assertIs(passed_stop,stop)
            if device.port==old.device: raise SerialError('Device not configured')
            stop.stopped=True
        self_test=self
        fake_serial=SimpleNamespace(Serial=Device,SerialException=SerialError)
        with patch.dict(sys.modules,{'serial':fake_serial}), \
             patch('transports.usb_devices',side_effect=[[old],[old],[other],[other,new]]), \
             patch('transports.usb_loop',side_effect=connected), patch('builtins.print'):
            serve_usb(self.service,old.device,stop)
        self.assertEqual(opened,[old.device,new.device]); self.assertEqual(closed,opened)

    def test_disconnect_clears_only_partial_audio_preserves_send_result(self):
        self.service.asr_ready=lambda: True
        rec=self.service.action(dict(action='record_start',request_id='record-request-000001',thread_id='thread-a'))
        path=self.service.recording['path']
        self.service.audio(rec['record_id'],0,b'\0\0'*100)
        self.service.transport_disconnected()
        self.assertIsNone(self.service.recording); self.assertFalse(path.exists())
        with self.assertRaises(ClientError): self.service.audio(rec['record_id'],1,b'\0\0')
        self.service.draft={'id':'draft-a','thread_id':'thread-a','state':'ready','text':'检查代码'}
        action=dict(action='send',request_id='send-request-00000001',draft_id='draft-a')
        result=self.service.action(action)
        self.service.transport_disconnected()
        self.assertEqual(self.service.action(action),result)
        self.assertEqual(sum(m=='turn/start' for m,_ in self.rpc.calls),1)
        self.assertEqual(self.service.draft['state'],'sent')

    def test_usb_lost_response_is_not_sent_twice_after_reconnect(self):
        self.service.draft={'id':'draft-a','thread_id':'thread-a','state':'ready','text':'检查代码'}
        data=json.dumps(dict(action='send',request_id='send-request-00000002',draft_id='draft-a')).encode()
        request=encode(2,0,'/v1/action',data)
        class First:
            in_waiting=len(request)
            def read(self,_): return request
            def write(self,_): raise ConnectionError('response lost')
        with self.assertRaises(ConnectionError): usb_loop(First(),self.service)
        self.service.transport_disconnected()
        stop=threading.Event(); response=[]
        class Second:
            in_waiting=len(request)
            def read(self,_): return request
            def write(self,data): response.append(bytes(data)); stop.set(); return len(data)
        usb_loop(Second(),self.service,stop)
        self.assertEqual(Decoder().feed(b''.join(response))[0][1],200)
        self.assertEqual(sum(m=='turn/start' for m,_ in self.rpc.calls),1)


if __name__ == "__main__": unittest.main()
