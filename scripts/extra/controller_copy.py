#!/usr/bin/env python3
"""Reliable controller copy: send the right copy shortcut for the focused app."""
import os
import subprocess
import sys
from datetime import datetime

os.environ.setdefault("DISPLAY", ":0")

LOG_FILE = os.path.expanduser("/tmp/controller_copy.log")

TERMINAL_CLASSES = {
    "gnome-terminal", "x-terminal-emulator", "konsole", "alacritty",
    "kitty", "terminator", "tilix", "st", "termite", "lxterminal",
    "qterminal", "hyper", "wezterm", "guake", "yakuake", "tilda",
    "mate-terminal", "xfce4-terminal",
}


def log(msg: str) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {msg}\n")


def get_active_window_class() -> str:
    try:
        out = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowclassname"],
            capture_output=True,
            text=True,
            env=os.environ,
            timeout=5,
        )
        return out.stdout.strip().lower()
    except Exception as exc:
        log(f"window class error: {exc}")
        return ""


def main() -> int:
    log("copy triggered")
    cls = get_active_window_class()
    log(f"window class: {cls!r}")

    if cls in TERMINAL_CLASSES or "terminal" in cls:
        shortcut = "ctrl+shift+c"
    else:
        shortcut = "ctrl+c"

    log(f"sending {shortcut}")
    try:
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", shortcut],
            check=True,
            env=os.environ,
        )
        log("sent")
    except Exception as exc:
        log(f"ERROR: {exc}")
        subprocess.run(
            ["notify-send", "-u", "low", "Copy failed", str(exc)],
            env=os.environ,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
