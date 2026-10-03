"""Bounded USB clock sync for the standalone offline card firmware."""
import time

from firmware import usb_devices


def _reply(port, expected, timeout=0.7):
    deadline = time.monotonic() + timeout
    line = bytearray()
    while time.monotonic() < deadline:
        for byte in port.read(min(128, port.in_waiting or 1)):
            if byte == 10:
                if expected in line:
                    return True
                line.clear()
            elif byte != 13:
                if len(line) < 160:
                    line.append(byte)
                else:
                    line.clear()
    return False


def sync_clock(identity, wait_seconds=0):
    """Sync only a card that explicitly identifies as offline firmware.

    ``identity`` is the card's USB serial number, not a mutable port path.
    Returns False for an absent/older/other-mode card without changing it.
    """
    import serial

    deadline = time.monotonic() + wait_seconds
    while True:
        matches = [device for device in usb_devices() if device["serial"] == identity]
        if len(matches) == 1:
            try:
                port = serial.Serial(port=None, baudrate=115200, timeout=.1,
                                     write_timeout=.5, exclusive=True)
                port.dtr = port.rts = False
                port.port = matches[0]["port"]
                with port:
                    port.reset_input_buffer()
                    port.write(b"CPCLK1?\n")
                    if not _reply(port, b"CPCLK1:OFFLINE"):
                        if time.monotonic() >= deadline:
                            return False
                        time.sleep(.3)
                        continue
                    epoch_ms = int(time.time() * 1000)
                    if not 1700000000000 <= epoch_ms < 4102444800000:
                        return False
                    port.write(f"CPCLK1:{epoch_ms:013d}\n".encode("ascii"))
                    if _reply(port, b"CPCLK1:OK"):
                        return True
            except (OSError, serial.SerialException):
                pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(.3)
