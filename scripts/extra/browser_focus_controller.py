#!/usr/bin/env python3
"""Controller → browser focus engine dispatcher.

Listens for semantic focus hotkeys (F15-F18) from the controller and routes them
to the Sensei focus engine running in the active Chrome tab via the bridge's
/extension/queue endpoint.

Assumes the Sensei side panel is open (it polls /extension/queue).
"""
import os
import subprocess
import sys
import time
import json
import urllib.request
import urllib.error
from pynput import keyboard

BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://127.0.0.1:8080")
SESSION_ID = os.environ.get("SENSEI_SESSION", "focus-engine")
FOCUS_ACTIONS = {
    keyboard.Key.f15: ("next", "window.__senseiFocus('next')"),
    keyboard.Key.f16: ("prev", "window.__senseiFocus('prev')"),
    keyboard.Key.f17: ("activate", "window.__senseiFocus('activate')"),
    keyboard.Key.f18: ("cancel", "window.__senseiFocus('cancel')"),
}

_last_key_time = 0.0
_DEBOUNCE_MS = 180


def _active_window_class():
    """Return WM_CLASS of active X11 window, or ''."""
    try:
        out = subprocess.check_output(
            ["xdotool", "getactivewindow", "getwindowclassname"],
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode().strip().lower()
    except Exception:
        return ""


def _is_browser_window():
    cls = _active_window_class()
    return cls in ("google-chrome", "chrome", "firefox", "librewolf", "brave-browser", "chromium")


def _send_focus_command(name, code):
    """Post a BROWSER_JS action to the Sensei bridge queue."""
    url = f"{BRIDGE_URL}/extension/queue"
    body = {
        "session_id": SESSION_ID,
        "actions": [
            {
                "kind": "BROWSER_JS",
                "target": code,
                "extras": {"source": "browser_focus_controller", "command": name},
            }
        ],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            err = exc.read().decode("utf-8")
        except Exception:
            err = "unknown HTTP error"
        return {"ok": False, "error": err}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def on_press(key):
    global _last_key_time
    if key not in FOCUS_ACTIONS:
        return
    now = time.time()
    if (now - _last_key_time) * 1000 < _DEBOUNCE_MS:
        return
    _last_key_time = now
    if not _is_browser_window():
        print(f"  Ignored {key.name} — active window is not a browser", flush=True)
        return
    name, code = FOCUS_ACTIONS[key]
    print(f"  Focus {name}...", flush=True)
    result = _send_focus_command(name, code)
    if not result.get("ok"):
        print(f"  Failed: {result.get('error')}", flush=True)


print("Browser focus controller")
print("F15=next  F16=prev  F17=activate  F18=cancel")
print("Ctrl+C to quit.\n")

with keyboard.Listener(on_press=on_press) as listener:
    try:
        listener.join()
    except KeyboardInterrupt:
        print("\nStopped.")
