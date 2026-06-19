#!/usr/bin/env python3
"""Test reading from joystick API AND evdev simultaneously."""
import struct
import os
import select
import time

# Try joystick API first
print("=== Testing /dev/input/js0 (joystick API) ===")
try:
    js = os.open('/dev/input/js0', os.O_RDONLY | os.O_NONBLOCK)
    print(f"Opened /dev/input/js0 fd={js}")
    
    # Read joystick events for 8 seconds
    deadline = time.time() + 8
    js_events = []
    while time.time() < deadline:
        r, _, _ = select.select([js], [], [], 0.5)
        if r:
            try:
                data = os.read(js, 8)  # js_event is 8 bytes
                if len(data) == 8:
                    # struct js_event { unsigned int time; short value; unsigned char type; unsigned char number; }
                    t, val, etype, num = struct.unpack('IhBB', data)
                    js_events.append(f"time={t} val={val} type={etype:#x} num={num}")
            except BlockingIOError:
                pass
    os.close(js)
    
    if js_events:
        print(f"Joystick events: {len(js_events)}")
        for e in js_events:
            print(f"  {e}")
    else:
        print("NO joystick events in 8 seconds")
except Exception as e:
    print(f"Joystick API error: {e}")

print()

# Now try evdev
print("=== Testing /dev/input/event6 (evdev API) ===")
try:
    import evdev
    from evdev import ecodes
    dev = evdev.InputDevice('/dev/input/event6')
    print(f"Opened: {dev.name} fd={dev.fd}")
    
    deadline = time.time() + 8
    ev_events = []
    while time.time() < deadline:
        r, _, _ = select.select([dev], [], [], 0.5)
        if r:
            for event in dev.read():
                if event.type == ecodes.EV_ABS:
                    ax = ecodes.ABS.get(event.code, f'ABS_{event.code}')
                    ev_events.append(f'ABS {ax}({event.code}) = {event.value}')
                elif event.type == ecodes.EV_KEY:
                    key = ecodes.KEY.get(event.code, ecodes.BTN.get(event.code, f'KEY_{event.code}'))
                    ev_events.append(f'KEY {key}({event.code}) = {event.value}')
    
    if ev_events:
        print(f"Evdev events: {len(ev_events)}")
        for e in ev_events:
            print(f"  {e}")
    else:
        print("NO evdev events in 8 seconds")
except Exception as e:
    print(f"Evdev API error: {e}")