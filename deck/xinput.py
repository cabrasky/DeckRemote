"""Xbox 360 (XInput) virtual gamepad on the Deck's virtual UDC, driven through raw-gadget.

gadget.sh "up-xbox" loads usbip-vudc + raw_gadget and hands /dev/raw-gadget to the deck user.
This module then behaves like a wired Xbox 360 controller (045e:028e):
  * answers every control request on ep0 (descriptors, configuration, vendor requests),
  * sends 20-byte XInput input reports on the interrupt IN endpoint whenever the state changes,
  * reads 8-byte rumble packets from the interrupt OUT endpoint -> on_rumble(strong, weak).
Raw-gadget is used instead of FunctionFS because the controller's 17-byte vendor descriptor
(type 0x21) is required by Windows' XInput driver and FunctionFS refuses it.

Descriptor bytes follow GP2040-CE's XInput descriptors (MIT, Copyright (c) 2021 Jason Skuby).
The report layout and rumble packet follow the Linux xpad driver.
"""
import fcntl
import os
import struct
import threading
import time

# The pad is created on dummy_hcd's UDC (a local virtual USB port), claimed by usbip-host and
# exported by usbipd. usbip-vudc cannot be used here: it asks the gadget for its descriptors
# synchronously, which raw-gadget (userspace answers) cannot do.
UDC_DEVICE, UDC_DRIVER = "dummy_udc.0", "dummy_udc"

DEVICE_DESC = bytes([0x12, 0x01, 0x00, 0x02, 0xFF, 0xFF, 0xFF, 0x40, 0x5E, 0x04, 0x8E, 0x02,
                     0x14, 0x01, 0x01, 0x02, 0x03, 0x01])
CONFIG_DESC = bytes([
    0x09, 0x02, 0x31, 0x00, 0x01, 0x01, 0x00, 0xA0, 0xFA,                 # config, 1 interface, 500 mA
    0x09, 0x04, 0x00, 0x00, 0x02, 0xFF, 0x5D, 0x01, 0x00,                 # interface FF/5D/01
    0x11, 0x21, 0x00, 0x01, 0x01, 0x25, 0x81, 0x14, 0x00, 0x00, 0x00, 0x00, 0x13, 0x02, 0x08, 0x00, 0x00,
    0x07, 0x05, 0x81, 0x03, 0x20, 0x00, 0x01,                             # EP 0x81 IN interrupt 32
    0x07, 0x05, 0x02, 0x03, 0x20, 0x00, 0x08,                             # EP 0x02 OUT interrupt 32
])
EP_IN_DESC = bytes([0x07, 0x05, 0x81, 0x03, 0x20, 0x00, 0x01, 0x00, 0x00])   # padded to 9 bytes
EP_OUT_DESC = bytes([0x07, 0x05, 0x02, 0x03, 0x20, 0x00, 0x08, 0x00, 0x00])
STRINGS = {1: "©Microsoft Corporation", 2: "Controller", 3: "DECKREMOTE"}

# raw-gadget ioctls (include/uapi/linux/usb/raw_gadget.h)
def _ioc(direction, nr, size):
    return (direction << 30) | (size << 16) | (ord("U") << 8) | nr
RAW_INIT, RAW_RUN, RAW_EVENT_FETCH = _ioc(1, 0, 257), _ioc(0, 1, 0), _ioc(2, 2, 8)
RAW_EP0_WRITE, RAW_EP0_READ, RAW_EP_ENABLE = _ioc(1, 3, 8), _ioc(3, 4, 8), _ioc(1, 5, 9)
RAW_EP_WRITE, RAW_EP_READ, RAW_CONFIGURE = _ioc(1, 7, 8), _ioc(3, 8, 8), _ioc(0, 9, 0)
RAW_VBUS_DRAW, RAW_EP0_STALL = _ioc(1, 10, 4), _ioc(0, 12, 0)
EV_CONNECT, EV_CONTROL, EV_SUSPEND, EV_RESUME, EV_RESET, EV_DISCONNECT = 1, 2, 3, 4, 5, 6

# SDL GameController button index -> (byte, bit) in the XInput report
#   byte 2: up down left right start back LS RS   byte 3: LB RB guide - A B X Y
SDL_TO_XINPUT = {11: (2, 0x01), 12: (2, 0x02), 13: (2, 0x04), 14: (2, 0x08), 6: (2, 0x10), 4: (2, 0x20),
                 7: (2, 0x40), 8: (2, 0x80), 9: (3, 0x01), 10: (3, 0x02),
                 0: (3, 0x10), 1: (3, 0x20), 2: (3, 0x40), 3: (3, 0x80)}


def report(buttons_sdl, axes_sdl):
    """20-byte XInput report. buttons_sdl: {sdl_button: 0/1}, axes_sdl: 6 SDL axis values."""
    b = bytearray(20)
    b[0], b[1] = 0x00, 0x14
    for idx, pressed in buttons_sdl.items():
        if pressed and idx in SDL_TO_XINPUT:
            byte, bit = SDL_TO_XINPUT[idx]
            b[byte] |= bit
    lx, ly, rx, ry, lt, rt = axes_sdl
    b[4] = max(0, lt) * 255 // 32767
    b[5] = max(0, rt) * 255 // 32767
    inv = lambda v: max(-32768, min(32767, -v))  # XInput Y is up-positive, SDL Y is down-positive
    struct.pack_into("<hhhh", b, 6, lx, inv(ly), rx, inv(ry))
    return bytes(b)


NEUTRAL = report({}, (0, 0, 0, 0, 0, 0))


def _string_desc(index):
    if index == 0:
        return bytes([4, 3, 0x09, 0x04])
    text = STRINGS.get(index)
    if text is None:
        return None
    data = text.encode("utf-16-le")
    return bytes([2 + len(data), 3]) + data


class XInputDevice:
    def __init__(self, bind, on_rumble=None, log=None):
        self.bind = bind                  # callable that runs "gadget.sh bind" (starts usbipd)
        self.on_rumble = on_rumble or (lambda strong, weak: None)
        self.log = log or (lambda *a: None)
        self.state = NEUTRAL
        self.cond = threading.Condition()
        self.configured = False
        self.exported = False   # True once usbip-host owns the pad (requests then come from the PC)
        self.running = True
        self.fd = None
        self.ep_in = self.ep_out = None

    # ---- raw-gadget helpers
    def _ioctl(self, req, buf):
        return fcntl.ioctl(self.fd, req, buf, True)

    def _ep0_write(self, data):
        buf = bytearray(struct.pack("<HHI", 0, 0, len(data)) + data)
        self._ioctl(RAW_EP0_WRITE, buf)

    def _ep0_read(self, length):
        buf = bytearray(struct.pack("<HHI", 0, 0, length) + bytes(length))
        self._ioctl(RAW_EP0_READ, buf)
        return bytes(buf[8:8 + length])

    def _stall(self):
        try:
            fcntl.ioctl(self.fd, RAW_EP0_STALL)
        except OSError:
            pass

    # ---- lifecycle
    def start(self):
        self.fd = os.open("/dev/raw-gadget", os.O_RDWR)
        init = bytearray(257)
        init[0:len(UDC_DRIVER)] = UDC_DRIVER.encode()
        init[128:128 + len(UDC_DEVICE)] = UDC_DEVICE.encode()
        init[256] = 3  # USB_SPEED_HIGH
        self._ioctl(RAW_INIT, init)
        fcntl.ioctl(self.fd, RAW_RUN)
        threading.Thread(target=self._ep0_loop, daemon=True).start()
        time.sleep(0.5)          # let the local enumeration finish (its SET_CONFIGURATION is refused)
        self.bind()
        self.exported = True

    def update(self, rep):
        with self.cond:
            if rep != self.state:
                self.state = rep
                self.cond.notify()

    def stop(self):
        self.running = False
        with self.cond:
            self.cond.notify()
        self.on_rumble(0, 0)
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass

    # ---- control endpoint
    def _ep0_loop(self):
        while self.running:
            buf = bytearray(struct.pack("<II", 0, 8) + bytes(8))
            try:
                self._ioctl(RAW_EVENT_FETCH, buf)
            except OSError as e:
                if self.running:
                    self.log(f"event fetch failed: {e}")
                time.sleep(0.05)
                continue
            etype, length = struct.unpack_from("<II", buf)
            if etype == EV_CONTROL:
                rt, rq, val, idx, wlen = struct.unpack_from("<BBHHH", buf, 8)
                try:
                    self._control(rt, rq, val, idx, wlen)
                except OSError as e:
                    self.log(f"control {rt:#04x}/{rq:#04x} failed: {e}")
            else:
                self.log(f"event {etype}")
                if etype in (EV_RESET, EV_DISCONNECT, EV_SUSPEND):
                    self.on_rumble(0, 0)

    def _control(self, rt, rq, val, idx, wlen):
        if rt == 0x80 and rq == 0x06:  # GET_DESCRIPTOR
            kind, index = val >> 8, val & 0xFF
            data = {1: DEVICE_DESC, 2: CONFIG_DESC}.get(kind)
            if kind == 3:
                data = _string_desc(index)
            if data is None:
                self.log(f"GET_DESCRIPTOR {val:#06x} -> stall")
                return self._stall()
            return self._ep0_write(data[:wlen])
        if rt == 0x00 and rq == 0x09:  # SET_CONFIGURATION
            self.log(f"SET_CONFIGURATION {val}")
            if not self.exported:
                # The Deck's own USB stack enumerates the pad before usbip-host takes it.
                # Refusing its configuration keeps xpad (and Steam) from seeing a ghost pad.
                return self._stall()
            if val and not self.configured:
                self.ep_in = fcntl.ioctl(self.fd, RAW_EP_ENABLE, bytearray(EP_IN_DESC), True)
                self.ep_out = fcntl.ioctl(self.fd, RAW_EP_ENABLE, bytearray(EP_OUT_DESC), True)
                fcntl.ioctl(self.fd, RAW_VBUS_DRAW, bytearray(struct.pack("<I", 250)), True)
                fcntl.ioctl(self.fd, RAW_CONFIGURE)
                self.configured = True
                threading.Thread(target=self._in_loop, daemon=True).start()
                threading.Thread(target=self._out_loop, daemon=True).start()
            return self._ep0_read(0)
        if rt == 0x80 and rq == 0x00:  # GET_STATUS (device)
            return self._ep0_write(bytes([0, 0])[:wlen])
        if rt == 0x01 and rq == 0x0B:  # SET_INTERFACE
            return self._ep0_read(0)
        if rt & 0x80:
            if rt == 0xC1 and rq == 0x01 and val == 0x0100:
                # XInput capabilities: every control present, both motors
                caps = bytes([0x00, 0x14, 0xFF, 0xF7, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                              0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                self.log("vendor IN caps request")
                return self._ep0_write(caps[:wlen])
            self.log(f"IN request {rt:#04x}/{rq:#04x} value={val:#06x} index={idx:#06x} len={wlen} -> stall")
            return self._stall()
        self.log(f"OUT request {rt:#04x}/{rq:#04x} value={val:#06x} index={idx:#06x} len={wlen}")
        self._ep0_read(wlen)

    # ---- interrupt endpoints
    def _ep_write(self, ep, data):
        buf = bytearray(struct.pack("<HHI", ep, 0, len(data)) + data)
        self._ioctl(RAW_EP_WRITE, buf)

    def _ep_read(self, ep, length):
        buf = bytearray(struct.pack("<HHI", ep, 0, length) + bytes(length))
        n = self._ioctl(RAW_EP_READ, buf)
        return bytes(buf[8:8 + n])

    def _in_loop(self):
        last, last_sent = None, 0.0
        while self.running:
            with self.cond:
                self.cond.wait_for(lambda: not self.running or self.state != last, timeout=0.1)
                rep = self.state
            if not self.running:
                break
            if rep == last and time.monotonic() - last_sent < 0.5:
                continue
            try:
                self._ep_write(self.ep_in, rep)
                last, last_sent = rep, time.monotonic()
            except OSError:
                time.sleep(0.05)

    def _out_loop(self):
        while self.running:
            try:
                pkt = self._ep_read(self.ep_out, 32)
            except OSError:
                time.sleep(0.05)
                continue
            if len(pkt) >= 5 and pkt[0] == 0x00 and pkt[1] == 0x08:
                self.log(f"rumble strong={pkt[3]} weak={pkt[4]}")
                self.on_rumble(pkt[3], pkt[4])
            elif pkt:
                self.log("OUT " + pkt.hex())
