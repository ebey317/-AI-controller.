#!/usr/bin/env python3
"""Reliable controller paste: read clipboard, type it into the focused window."""
import os
import subprocess
import sys
from datetime import datetime

os.environ.setdefault("DISPLAY", ":0")

LOG_FILE = os.path.expanduser("/tmp/controller_paste.log")


def log(msg: str) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {msg}\n")


def get_clipboard() -> str:
    """Read the X11 clipboard without tkinter or xclip."""
    try:
        from Xlib import X, display
    except ImportError:
        log("python-xlib not available")
        return ""

    try:
        d = display.Display()
        root = d.screen().root
        # Invisible 1x1 window to receive the selection.
        win = root.create_window(
            0, 0, 1, 1, 0,
            X.CopyFromParent,
            X.InputOutput,
            X.CopyFromParent,
            background_pixel=0,
            event_mask=X.NoEventMask,
        )
        win.map()

        clipboard = d.get_atom("CLIPBOARD")
        targets = ["UTF8_STRING", "STRING"]
        for target_name in targets:
            target = d.get_atom(target_name)
            win.convert_selection(clipboard, target, target, X.CurrentTime)
            d.flush()

            # Wait up to 1 second for a SelectionNotify event.
            import time
            deadline = datetime.now().timestamp() + 1.0
            text = None
            while datetime.now().timestamp() < deadline:
                if d.pending_events() > 0:
                    ev = d.next_event()
                    if ev.type == X.SelectionNotify:
                        if ev.property != X.NONE:
                            prop = win.get_property(ev.property, X.AnyPropertyType, 0, 100000)
                            if prop:
                                raw = prop.value
                                if isinstance(raw, bytes):
                                    text = raw.decode("utf-8", errors="replace")
                                elif isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], int):
                                    text = bytes(raw).decode("utf-8", errors="replace")
                                else:
                                    text = str(raw)
                        break
                time.sleep(0.01)
            if text is not None:
                return text
        return ""
    except Exception as exc:
        log(f"clipboard read error: {exc}")
        return ""


def main() -> int:
    log("paste triggered")
    text = get_clipboard()
    log(f"clipboard length={len(text)} first80={text[:80]!r}")
    if not text:
        log("empty clipboard, exiting")
        return 0
    # Only paste the first chunk; avoid dumping huge clipboards.
    text = text[:4000]
    # Replace tabs with spaces so we don't accidentally submit forms.
    text = text.replace("\t", " ")
    try:
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--", text],
            check=True,
            env=os.environ,
        )
        log(f"typed {len(text)} chars")
    except Exception as exc:
        log(f"ERROR: {exc}")
        subprocess.run(
            ["notify-send", "-u", "low", "Paste failed", str(exc)],
            env=os.environ,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
