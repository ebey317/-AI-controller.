#!/usr/bin/env python3
"""Raw controller input test - monitors /dev/input/event6 for 8 seconds."""
import evdev
from evdev import ecodes
import select
import time
import sys

dev = evdev.InputDevice('/dev/input/event6')
print(f'Device: {dev.name}')
print('Monitoring for 8 seconds... PRESS RT NOW')
print()

deadline = time.time() + 8
events_seen = []
while time.time() < deadline:
    r, _, _ = select.select([dev], [], [], 0.5)
    if r:
        for event in dev.read():
            if event.type == ecodes.EV_ABS:
                ax = ecodes.ABS.get(event.code, f'ABS_{event.code}')
                events_seen.append(f'ABS {ax}({event.code}) = {event.value}')
            elif event.type == ecodes.EV_KEY:
                key = ecodes.KEY.get(event.code, ecodes.BTN.get(event.code, f'KEY_{event.code}'))
                events_seen.append(f'KEY {key}({event.code}) = {event.value}')

print()
if events_seen:
    print(f'Total events: {len(events_seen)}')
    for e in events_seen:
        print(e)
else:
    print('NO EVENTS DETECTED - controller may be disconnected')