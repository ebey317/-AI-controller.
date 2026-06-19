#!/usr/bin/env python3
"""
Xbox Wireless Controller USB-to-evdev Bridge
Bypasses broken xone kernel driver by reading raw GIP protocol packets
directly from USB and translating them to evdev events via uinput.

No root required — uses USBDEVFS_DISCONNECT_CLAIM ioctl to detach kernel driver.

GIP Protocol Flow:
  1. Controller sends ANNOUNCE (0x02) automatically on USB connect
  2. Host sends IDENTIFY request (0x04) → controller responds with capabilities
  3. Host sends POWER mode (0x05) → controller powers on
  4. Host sends rumble stop (0x09) → controller starts sending INPUT (0x20)
  5. Controller sends INPUT packets with button/axis/trigger data

GIP Packet Format:
  byte 0: command
  byte 1: options (bits 0-3 = client_id, bit 5 = internal, bit 4 = ack, bit 6-7 = chunk)
  byte 2: sequence (must be > 0)
  byte 3+: packet_length as varint (7 bits per byte, MSB=continuation)
  [if chunk flag: chunk_offset as varint]
  payload data

Input packet (cmd=0x20) payload:
  offset 0-1: buttons (u16 LE)
  offset 2-3: trigger_left (u16 LE, 0-1023)
  offset 4-5: trigger_right (u16 LE, 0-1023)
  offset 6-7: stick_left_x (u16 LE, centered 0)
  offset 8-9: stick_left_y (u16 LE, centered 0)
  offset 10-11: stick_right_x (u16 LE, centered 0)
  offset 12-13: stick_right_y (u16 LE, centered 0)

Button bits:
  2=Menu, 3=View, 4=A, 5=B, 6=X, 7=Y
  8=DPad_U, 9=DPad_D, 10=DPad_L, 11=DPad_R
  12=Bumper_L, 13=Bumper_R, 14=Stick_L, 15=Stick_R
"""

import os
import fcntl
import ctypes
import struct
import select
import time
import sys
import signal
import errno

# ============================================================
# USB ioctl definitions (64-bit Linux)
# ============================================================

def _IOC(dir_, type_, nr, size):
    return (dir_ << 30) | (size << 16) | (type_ << 8) | nr

USBDEVFS_DISCONNECT_CLAIM = _IOC(2, 0x55, 27, 264)
USBDEVFS_RELEASEINTERFACE = _IOC(2, 0x55, 16, 4)
USBDEVFS_SUBMITURB = _IOC(2, 0x55, 10, 56)  # sizeof(usbdevfs_urb) on 64-bit
USBDEVFS_REAPURBNDELAY = _IOC(1, 0x55, 13, 8)  # void* = 8 bytes
USBDEVFS_DISCARDURB = _IOC(0, 0x55, 11, 0)
USBDEVFS_RESET = 0x5514  # _IO('U', 20)
USBDEVFS_RESETEP = _IOC(2, 0x55, 3, 4)  # _IOR('U', 3, unsigned int)

class DisconnectClaim(ctypes.Structure):
    _fields_ = [
        ("interface", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("driver", ctypes.c_char * 256),
    ]

class usbdevfs_urb(ctypes.Structure):
    _fields_ = [
        ("urbtype", ctypes.c_ubyte),      # 1=interrupt, 2=control, 3=bulk, 4=iso
        ("endpoint", ctypes.c_ubyte),     # endpoint address (0x82 for IN, 0x02 for OUT)
        ("status", ctypes.c_int),         # completion status
        ("flags", ctypes.c_uint),         # URB flags
        ("buffer", ctypes.c_void_p),      # pointer to data buffer
        ("buffer_length", ctypes.c_int),  # expected length
        ("actual_length", ctypes.c_int),  # actual transferred length
        ("start_frame", ctypes.c_int),    # iso only
        ("number_of_packets_or_iso", ctypes.c_int),
        ("error_count", ctypes.c_uint),   # iso only
        ("signr", ctypes.c_uint),         # signal to send on completion
        ("usercontext", ctypes.c_void_p), # user context pointer
    ]

# ============================================================
# GIP Protocol Constants
# ============================================================

GIP_CMD_ACKNOWLEDGE = 0x01
GIP_CMD_ANNOUNCE = 0x02
GIP_CMD_STATUS = 0x03
GIP_CMD_IDENTIFY = 0x04
GIP_CMD_POWER = 0x05
GIP_CMD_AUTHENTICATE = 0x06
GIP_CMD_VIRTUAL_KEY = 0x07
GIP_CMD_AUDIO_CONTROL = 0x08
GIP_CMD_RUMBLE = 0x09
GIP_CMD_LED = 0x0a
GIP_CMD_HID_REPORT = 0x0b
GIP_CMD_FIRMWARE = 0x0c
GIP_CMD_SERIAL_NUMBER = 0x1e
GIP_CMD_INPUT = 0x20

GIP_OPT_ACKNOWLEDGE = 0x10
GIP_OPT_INTERNAL = 0x20
GIP_OPT_CHUNK_START = 0x40
GIP_OPT_CHUNK = 0x80

# Button masks (from gamepad.c)
BTN_MENU   = 1 << 2   # Start button
BTN_VIEW   = 1 << 3   # Select/Back button
BTN_A      = 1 << 4
BTN_B      = 1 << 5
BTN_X      = 1 << 6
BTN_Y      = 1 << 7
BTN_DPAD_U = 1 << 8
BTN_DPAD_D = 1 << 9
BTN_DPAD_L = 1 << 10
BTN_DPAD_R = 1 << 11
BTN_BUMP_L = 1 << 12   # Left bumper
BTN_BUMP_R = 1 << 13   # Right bumper
BTN_STK_L  = 1 << 14   # Left stick click
BTN_STK_R  = 1 << 15   # Right stick click

# uinput constants
EV_KEY = 0x01
EV_ABS = 0x03
EV_SYN = 0x00
SYN_REPORT = 0x00

ABS_X = 0x00
ABS_Y = 0x01
ABS_Z = 0x02     # Left trigger
ABS_RX = 0x03
ABS_RY = 0x04
ABS_RZ = 0x05    # Right trigger
ABS_HAT0X = 0x10
ABS_HAT0Y = 0x11

# ioctl numbers (calculated from kernel headers)
UI_DEV_SETUP = 0x405c5503    # _IOW('U', 3, uinput_setup=92)
UI_ABS_SETUP = 0x401c5504    # _IOW('U', 4, uinput_abs_setup=28)
UI_DEV_CREATE = 0x5501       # _IO('U', 1)
UI_DEV_DESTROY = 0x5502      # _IO('U', 2)
UI_SET_EVBIT = 0x40045564    # _IOW('U', 100, int)
UI_SET_KEYBIT = 0x40045565   # _IOW('U', 101, int)
UI_SET_ABSBIT = 0x40045567   # _IOW('U', 103, int)

class input_id(ctypes.Structure):
    _fields_ = [
        ("bustype", ctypes.c_ushort),
        ("vendor", ctypes.c_ushort),
        ("product", ctypes.c_ushort),
        ("version", ctypes.c_ushort),
    ]

class uinput_setup(ctypes.Structure):
    _fields_ = [
        ("id", input_id),
        ("name", ctypes.c_char * 80),
        ("ff_effects_max", ctypes.c_uint),
    ]

class input_absinfo(ctypes.Structure):
    _fields_ = [
        ("value", ctypes.c_int),
        ("minimum", ctypes.c_int),
        ("maximum", ctypes.c_int),
        ("fuzz", ctypes.c_int),
        ("flat", ctypes.c_int),
        ("resolution", ctypes.c_int),
    ]

class uinput_abs_setup(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_uint),
        ("absinfo", input_absinfo),
    ]

# ============================================================
# USB Bridge
# ============================================================

class XboxUSBBridge:
    EP_IN = 0x82    # Interrupt IN (controller → host)
    EP_OUT = 0x02   # Interrupt OUT (host → controller)
    BUF_SIZE = 64

    def __init__(self):
        self.usb_fd = -1
        self.uinput_fd = -1
        self.running = False
        self.sequence = 1
        self.last_buttons = 0
        self.reconnect_count = 0
        self.packet_count = 0

    def find_controller(self):
        """Find Xbox controller USB device path"""
        for d in os.listdir('/sys/bus/usb/devices'):
            try:
                with open(f'/sys/bus/usb/devices/{d}/idVendor') as f:
                    vid = f.read().strip()
                if vid != '045e':
                    continue
                with open(f'/sys/bus/usb/devices/{d}/idProduct') as f:
                    pid = f.read().strip()
                if pid != '0b12':
                    continue
                with open(f'/sys/bus/usb/devices/{d}/busnum') as f:
                    bus = int(f.read().strip())
                with open(f'/sys/bus/usb/devices/{d}/devnum') as f:
                    devnum = int(f.read().strip())
                return f'/dev/bus/usb/{bus:03d}/{devnum:03d}'
            except (IOError, OSError):
                continue
        return None

    def open_usb(self):
        """Open USB device, reset it, and detach kernel driver"""
        path = self.find_controller()
        if not path:
            print("[!] Xbox controller not found")
            return False

        self.usb_fd = os.open(path, os.O_RDWR)
        print(f"[+] Opened USB device: {path} (fd={self.usb_fd})")

        # Reset USB device to force fresh GIP handshake
        try:
            fcntl.ioctl(self.usb_fd, USBDEVFS_RESET)
            print("[+] USB device reset — forcing fresh GIP handshake")
            time.sleep(0.5)
        except OSError as e:
            print(f"[-] USB reset failed: {e}")

        # Detach kernel driver from interfaces 0 (data) and 1 (audio)
        for iface in [0, 1]:
            dc = DisconnectClaim()
            dc.interface = iface
            dc.flags = 0
            dc.driver = b""
            try:
                fcntl.ioctl(self.usb_fd, USBDEVFS_DISCONNECT_CLAIM, dc)
                print(f"[+] Interface {iface}: kernel driver detached")
            except OSError as e:
                print(f"[-] Interface {iface} claim failed: {e}")
                os.close(self.usb_fd)
                return False

        return True

    def submit_read_urb(self, buf):
        """Submit an interrupt IN URB to read from the controller"""
        urb = usbdevfs_urb()
        urb.urbtype = 1  # INTERRUPT
        urb.endpoint = self.EP_IN
        urb.buffer = ctypes.cast(buf, ctypes.c_void_p)
        urb.buffer_length = self.BUF_SIZE
        try:
            fcntl.ioctl(self.usb_fd, USBDEVFS_SUBMITURB, urb)
        except OSError as e:
            print(f"[-] Submit read URB failed: {e}")
            return None
        return urb

    def send_gip(self, command, options, data=b''):
        """Send a GIP packet to the controller via OUT endpoint"""
        # Build GIP header
        seq = self.sequence
        self.sequence = (self.sequence % 255) + 1

        pkt_len = len(data)
        # Encode varint for packet_length
        varint = []
        val = pkt_len
        while val > 0x7f:
            varint.append((val & 0x7f) | 0x80)
            val >>= 7
        varint.append(val & 0x7f)

        header = bytes([command, options, seq] + varint)
        # Header must be even length
        if len(header) % 2 != 0:
            header += b'\x00'

        packet = header + data
        # Pad to 64 bytes (USB interrupt transfer size)
        if len(packet) < self.BUF_SIZE:
            packet += b'\x00' * (self.BUF_SIZE - len(packet))

        # Submit write URB
        buf = (ctypes.c_ubyte * self.BUF_SIZE)(*packet)
        urb = usbdevfs_urb()
        urb.urbtype = 1  # INTERRUPT
        urb.endpoint = self.EP_OUT
        urb.buffer = ctypes.cast(buf, ctypes.c_void_p)
        urb.buffer_length = self.BUF_SIZE

        try:
            fcntl.ioctl(self.usb_fd, USBDEVFS_SUBMITURB, urb)
            cmd_name = {
                GIP_CMD_IDENTIFY: "IDENTIFY",
                GIP_CMD_POWER: "POWER",
                GIP_CMD_RUMBLE: "RUMBLE",
                GIP_CMD_LED: "LED",
                GIP_CMD_ACKNOWLEDGE: "ACK",
            }.get(command, f"0x{command:02x}")
            print(f"[→] Sent GIP {cmd_name} (seq={seq}, {len(data)}B data)")
        except OSError as e:
            print(f"[-] Send GIP failed: {e}")
            return False
        return True

    def send_identify(self):
        """Send IDENTIFY request to trigger protocol handshake"""
        return self.send_gip(GIP_CMD_IDENTIFY, GIP_OPT_INTERNAL, b'')

    def send_power_on(self):
        """Send POWER mode command to wake controller"""
        return self.send_gip(GIP_CMD_POWER, GIP_OPT_INTERNAL, b'\x00')

    def send_rumble_stop(self):
        """Send rumble stop to initialize input (required by firmware)"""
        # struct gip_gamepad_pkt_rumble: unknown, motors, lt, rt, left, right, duration, delay, repeat
        rumble_data = bytes([0x00, 0x0f, 0x00, 0x00, 0x00, 0x00, 0xff, 0x00, 0xeb])
        return self.send_gip(GIP_CMD_RUMBLE, 0x00, rumble_data)

    def send_acknowledge(self, orig_cmd, orig_seq, orig_options, length=0):
        """Send ACKNOWLEDGE for a received packet"""
        # struct gip_pkt_acknowledge: unknown, command, options, length(u16), padding[2], remaining(u16)
        ack_data = struct.pack('<BBHHH', 0x00, orig_cmd, orig_options, length, 0) + b'\x00\x00'
        return self.send_gip(GIP_CMD_ACKNOWLEDGE, GIP_OPT_INTERNAL, ack_data)

    def parse_gip_header(self, data, offset=0):
        """Parse GIP packet header, return (command, options, sequence, packet_length, header_len)"""
        if len(data) - offset < 3:
            return None
        cmd = data[offset]
        opt = data[offset + 1]
        seq = data[offset + 2]

        # Decode varint for packet_length
        pkt_len = 0
        i = 3
        while offset + i < len(data):
            byte = data[offset + i]
            pkt_len |= (byte & 0x7f) << ((i - 3) * 7)
            i += 1
            if not (byte & 0x80):
                break

        hdr_len = i
        # If chunk flag set, skip chunk_offset varint too
        if opt & GIP_OPT_CHUNK:
            while offset + i < len(data):
                byte = data[offset + i]
                i += 1
                if not (byte & 0x80):
                    break
            hdr_len = i

        # Round up to even
        actual_hdr_len = hdr_len
        even_hdr_len = hdr_len + (hdr_len % 2)

        return cmd, opt, seq, pkt_len, even_hdr_len

    def handle_gip_packet(self, data):
        """Process incoming GIP packet(s) from controller"""
        offset = 0
        while offset < len(data):
            hdr = self.parse_gip_header(data, offset)
            if not hdr:
                break
            cmd, opt, seq, pkt_len, hdr_len = hdr
            payload = data[offset + hdr_len : offset + hdr_len + pkt_len]

            self.packet_count += 1

            if cmd == GIP_CMD_ANNOUNCE:
                print(f"[←] ANNOUNCE (seq={seq}, {pkt_len}B)")
                # Controller announced itself — request identification
                time.sleep(0.05)
                self.send_identify()

            elif cmd == GIP_CMD_STATUS:
                if pkt_len >= 1:
                    status = payload[0]
                    connected = bool(status & 0x80)
                    batt_type = (status >> 2) & 0x03
                    batt_lvl = status & 0x03
                    print(f"[←] STATUS (seq={seq}, connected={connected}, batt={batt_lvl})")
                # Acknowledge
                if opt & GIP_OPT_ACKNOWLEDGE:
                    self.send_acknowledge(cmd, seq, opt, pkt_len)

            elif cmd == GIP_CMD_IDENTIFY:
                print(f"[←] IDENTIFY response ({pkt_len}B)")
                # Controller identified — power it on and start input
                time.sleep(0.05)
                self.send_power_on()
                time.sleep(0.1)
                self.send_rumble_stop()
                # Send acknowledge if requested
                if opt & GIP_OPT_ACKNOWLEDGE:
                    self.send_acknowledge(cmd, seq, opt, pkt_len)

            elif cmd == GIP_CMD_INPUT:
                self.handle_input(payload)

            elif cmd == GIP_CMD_ACKNOWLEDGE:
                print(f"[←] ACK (seq={seq})")

            elif cmd == GIP_CMD_VIRTUAL_KEY:
                if pkt_len >= 2:
                    down = payload[0]
                    key = payload[1]
                    if key == 0x5b:  # Xbox/Guide button
                        self.emit_key(0x2f0 + 1, down)  # BTN_MODE
                        print(f"[←] GUIDE button {'down' if down else 'up'}")

            elif cmd == GIP_CMD_SERIAL_NUMBER:
                if pkt_len >= 16:
                    serial = payload[2:16].decode('ascii', errors='replace').rstrip('\x00')
                    print(f"[←] Serial: {serial}")

            else:
                name = {0x05: "POWER", 0x06: "AUTH", 0x07: "VKEY",
                       0x0a: "LED", 0x0b: "HID", 0x0c: "FW",
                       0x1e: "SERIAL", 0x60: "AUDIO"}.get(cmd, f"0x{cmd:02x}")
                if self.packet_count < 20 or self.packet_count % 100 == 0:
                    print(f"[←] {name} (seq={seq}, {pkt_len}B)")

            # Move to next packet in buffer
            offset += hdr_len + pkt_len

    def handle_input(self, data):
        """Parse GIP input packet and emit evdev events"""
        if len(data) < 14:
            return

        buttons, tl, tr, lx, ly, rx, ry = struct.unpack('<HHHHHHH', data[:14])

        # Emit button events
        button_map = [
            (BTN_A,      0x130),  # BTN_A
            (BTN_B,      0x131),  # BTN_B
            (BTN_X,      0x133),  # BTN_X
            (BTN_Y,      0x134),  # BTN_Y
            (BTN_BUMP_L, 0x136),  # BTN_TL
            (BTN_BUMP_R, 0x137),  # BTN_TR
            (BTN_STK_L,  0x13a),  # BTN_THUMBL
            (BTN_STK_R,  0x13b),  # BTN_THUMBR
            (BTN_MENU,   0x13c),  # BTN_START
            (BTN_VIEW,   0x13d),  # BTN_SELECT
        ]
        for mask, code in button_map:
            self.emit_key(code, bool(buttons & mask))

        # D-pad (HAT)
        dpad_x = 0
        dpad_y = 0
        if buttons & BTN_DPAD_R:
            dpad_x = 1
        elif buttons & BTN_DPAD_L:
            dpad_x = -1
        if buttons & BTN_DPAD_U:
            dpad_y = -1
        elif buttons & BTN_DPAD_D:
            dpad_y = 1
        self.emit_abs(ABS_HAT0X, dpad_x)
        self.emit_abs(ABS_HAT0Y, dpad_y)

        # Triggers (0-1023 → 0-1023)
        self.emit_abs(ABS_Z, tl)
        self.emit_abs(ABS_RZ, tr)

        # Sticks (u16 centered at 0 → signed -32768..32767)
        # GIP uses unsigned 16-bit with 0 as center
        # Convert: if value > 32767, subtract 65536 (two's complement)
        def to_signed(v):
            return v - 65536 if v > 32767 else v

        self.emit_abs(ABS_X, to_signed(lx))
        self.emit_abs(ABS_Y, to_signed(ly))
        self.emit_abs(ABS_RX, to_signed(rx))
        self.emit_abs(ABS_RY, to_signed(ry))

        # Sync
        self.sync()

    # ============================================================
    # uinput / evdev output
    # ============================================================

    def setup_uinput(self):
        """Create virtual input device using modern UI_DEV_SETUP ioctl"""
        self.uinput_fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
        print(f"[+] Opened uinput (fd={self.uinput_fd})")

        # Set up device info via UI_DEV_SETUP ioctl
        setup = uinput_setup()
        setup.name = b"Xbox Wireless Controller (USB Bridge)"
        setup.id.bustype = 0x03  # BUS_USB
        setup.id.vendor = 0x045e
        setup.id.product = 0x0b12
        setup.id.version = 0x0100
        setup.ff_effects_max = 0

        try:
            fcntl.ioctl(self.uinput_fd, UI_DEV_SETUP, setup)
        except OSError as e:
            print(f"[-] UI_DEV_SETUP failed: {e}")
            return False

        # Enable event types
        fcntl.ioctl(self.uinput_fd, UI_SET_EVBIT, EV_KEY)
        fcntl.ioctl(self.uinput_fd, UI_SET_EVBIT, EV_ABS)
        fcntl.ioctl(self.uinput_fd, UI_SET_EVBIT, EV_SYN)

        # Enable buttons
        for code in [0x130, 0x131, 0x133, 0x134, 0x136, 0x137,
                     0x13a, 0x13b, 0x13c, 0x13d, 0x2f1]:
            fcntl.ioctl(self.uinput_fd, UI_SET_KEYBIT, code)

        # Enable and configure axes via UI_ABS_SETUP
        abs_ranges = {
            ABS_X: (-32768, 32767, 16, 128),
            ABS_Y: (-32768, 32767, 16, 128),
            ABS_Z: (0, 1023, 0, 0),
            ABS_RX: (-32768, 32767, 16, 128),
            ABS_RY: (-32768, 32767, 16, 128),
            ABS_RZ: (0, 1023, 0, 0),
            ABS_HAT0X: (-1, 1, 0, 0),
            ABS_HAT0Y: (-1, 1, 0, 0),
        }
        for axis, (mn, mx, fuzz, flat) in abs_ranges.items():
            abs_setup = uinput_abs_setup()
            abs_setup.code = axis
            abs_setup.absinfo.value = 0
            abs_setup.absinfo.minimum = mn
            abs_setup.absinfo.maximum = mx
            abs_setup.absinfo.fuzz = fuzz
            abs_setup.absinfo.flat = flat
            abs_setup.absinfo.resolution = 0
            fcntl.ioctl(self.uinput_fd, UI_ABS_SETUP, abs_setup)

        # Create device
        fcntl.ioctl(self.uinput_fd, UI_DEV_CREATE)
        print("[+] uinput device created: /dev/input/event*")
        return True

    def emit_event(self, type_, code, value):
        """Write an evdev event"""
        # struct input_event: timeval(16B on 64-bit) + type(u16) + code(u16) + value(s32)
        # On 64-bit Linux: timeval = {long tv_sec, long tv_usec} = 16 bytes
        # Total: 16 + 2 + 2 + 4 = 24 bytes
        event = struct.pack('qqHHi', 0, 0, type_, code, value)
        try:
            os.write(self.uinput_fd, event)
        except OSError:
            pass

    def emit_key(self, code, value):
        self.emit_event(EV_KEY, code, int(value))

    def emit_abs(self, axis, value):
        self.emit_event(EV_ABS, axis, int(value))

    def sync(self):
        self.emit_event(EV_SYN, SYN_REPORT, 0)

    # ============================================================
    # Main loop
    # ============================================================

    def run(self):
        """Main bridge loop"""
        if not self.open_usb():
            return False
        if not self.setup_uinput():
            return False

        self.running = True
        print("\n[+] Xbox USB Bridge running. Press Ctrl+C to stop.")
        print("[+] Try pressing buttons / moving sticks on the controller...\n")

        # Submit initial read URB
        read_buf = (ctypes.c_ubyte * self.BUF_SIZE)()
        read_urb = self.submit_read_urb(read_buf)

        # Also try sending initialization commands immediately
        # (controller may have already announced; trigger re-handshake)
        print("[*] Sending GIP initialization sequence...")
        time.sleep(0.1)
        self.send_identify()
        time.sleep(0.2)
        self.send_power_on()
        time.sleep(0.1)
        self.send_rumble_stop()

        last_resubmit = time.time()

        while self.running:
            # Wait for USB data with 1-second timeout
            ready, _, _ = select.select([self.usb_fd], [], [], 1.0)
            if ready:
                # Reap completed URB
                reap_ptr = ctypes.c_void_p()
                try:
                    fcntl.ioctl(self.usb_fd, USBDEVFS_REAPURBNDELAY, reap_ptr)
                    length = read_urb.actual_length
                    status = read_urb.status
                    if status == 0 and length > 0:
                        data = bytes(read_buf[:length])
                        self.handle_gip_packet(data)
                    elif status != 0:
                        print(f"[-] URB status: {status}")
                except OSError as e:
                    if e.errno != errno.EAGAIN:
                        print(f"[-] Reap URB error: {e}")

                # Resubmit read URB
                read_urb.status = 0
                read_urb.actual_length = 0
                read_urb.buffer = ctypes.cast(read_buf, ctypes.c_void_p)
                read_urb.buffer_length = self.BUF_SIZE
                try:
                    fcntl.ioctl(self.usb_fd, USBDEVFS_SUBMITURB, read_urb)
                except OSError as e:
                    print(f"[-] Resubmit failed: {e}")
                    time.sleep(0.5)

        self.cleanup()
        return True

    def cleanup(self):
        """Release resources"""
        print("\n[*] Cleaning up...")

        # Destroy uinput device
        if self.uinput_fd >= 0:
            try:
                fcntl.ioctl(self.uinput_fd, UI_DEV_DESTROY)
                os.close(self.uinput_fd)
                print("[+] uinput device destroyed")
            except:
                pass

        # Release USB interfaces
        if self.usb_fd >= 0:
            try:
                fcntl.ioctl(self.usb_fd, USBDEVFS_RELEASEINTERFACE, 0)
                fcntl.ioctl(self.usb_fd, USBDEVFS_RELEASEINTERFACE, 1)
                os.close(self.usb_fd)
                print("[+] USB interfaces released")
            except:
                pass

        print(f"[*] Total packets received: {self.packet_count}")


def main():
    bridge = XboxUSBBridge()

    def signal_handler(sig, frame):
        bridge.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bridge.run()
    except Exception as e:
        print(f"\n[!] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        bridge.cleanup()


if __name__ == "__main__":
    main()