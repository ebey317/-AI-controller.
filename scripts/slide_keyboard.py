#!/usr/bin/env python3
"""
slide_keyboard.py — Floating, centered on-screen keyboard.

Replaces Onboard (its accessibility "scanner" mode never moved off the
backtick key — confirmed broken independent of the controller, 2026-06-16).

No scanner, no highlight-and-select. Every key is a real GTK button:
click it (controller A + L-stick-as-mouse, or a real mouse) and it sends
that keystroke straight to whatever window currently has focus, via
xdotool. The keyboard window itself never takes focus
(set_accept_focus(False)), so the target window stays focused throughout.

Trigger: Guide button (AntiMicroX sends F14) pops it up centered on screen,
styled to match the controller-legend HUD (same dark/orange theme, rounded
panel) so it reads as part of the same floating-overlay family instead of
a separate full-width dock. Press F14 again to pop it back down.
"""
import os
import signal
import subprocess
import sys

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib

# Shared with ptt_pynput.py: PRO = plain text, BUBBLY = cursive + emoji
PTT_MODE_FILE = os.path.expanduser("~/.config/ptt_mode")
VOICE_FILE = os.path.expanduser("~/.config/ai_controller_voice")

ROWS_LOWER = [
    ["`", "esc", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "bksp"],
    ["tab", "q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "[", "]", "\\"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'", "enter"],
    ["shift", "z", "x", "c", "v", "b", "n", "m", ",", ".", "/", "shift"],
    ["left", "down", "up", "right", "space", "⇧tab"],
]
ROWS_UPPER = [
    ["~", "esc", "!", "@", "#", "$", "%", "^", "&", "*", "(", ")", "_", "+", "bksp"],
    ["tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "{", "}", "|"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L", ":", '"', "enter"],
    ["shift", "Z", "X", "C", "V", "B", "N", "M", "<", ">", "?", "shift"],
    ["left", "down", "up", "right", "space", "⇧tab"],
]

# keys that send a named X11 key (xdotool key ...) instead of a literal char
SPECIAL = {
    "esc": "Escape", "bksp": "BackSpace", "tab": "Tab", "enter": "Return",
    "space": "space", "left": "Left", "right": "Right", "up": "Up", "down": "Down",
    "⇧tab": "shift+Tab",
}
LABELS = {
    "esc": "Esc", "bksp": "⌫", "tab": "Tab ⇥", "enter": "Enter ↵",
    "space": "Space", "left": "←", "right": "→", "up": "↑", "down": "↓",
    "shift": "⇧", "⇧tab": "⇧Tab\n(cycle)",
}

# Same dark/orange family as controller-legend.py's HUD, so the two read as
# one floating-overlay system instead of unrelated widgets.
def _modifier_state():
    """Return (ctrl, alt) from live X11 keyboard state — queried at click time, no listener."""
    try:
        try:
            keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
        except Exception:
            keymap = Gdk.Keymap.get_default()
        mask = keymap.get_modifier_state()
        return (bool(mask & Gdk.ModifierType.CONTROL_MASK),
                bool(mask & Gdk.ModifierType.MOD1_MASK))
    except Exception:
        return False, False


HUD_ORANGE = "#FF6A00"

CSS = b"""
window { background-color: transparent; }
#panel {
    background-color: rgba(13,13,18,0.94);
    border: 2px solid #FF6A00;
    border-radius: 16px;
}
button {
    background-image: none;
    background-color: #23232b;
    color: #e8e8e8;
    border: 1px solid #3a3a44;
    border-radius: 6px;
    font-family: monospace;
    font-size: 13px;
    min-width: 34px;
    min-height: 34px;
    padding: 4px;
}
button:hover { background-color: #2f2f3a; }
button.special { background-color: #1a2226; color: #FF6A00; border-color: #4a3318; }
button.mode { background-color: #2a1a0a; color: #FF6A00; border-color: #FF6A00; font-weight: bold; padding: 2px 10px; }
button.mode-active { background-color: #FF6A00; color: #0d0d12; border-color: #FF6A00; font-weight: bold; padding: 2px 10px; }
#voice-shelf { background-color: rgba(255,106,0,0.08); border-left: 1px solid #FF6A00; border-radius: 0 12px 12px 0; padding: 6px; }
.shelf-title { color: #FF6A00; font-weight: bold; font-size: 11px; margin-bottom: 4px; }
button.voice { background-color: #1a1a22; color: #e8e8e8; border-color: #3a3a44; font-size: 12px; min-height: 28px; }
button.voice:hover { background-color: #2a2a34; }
button.voice-active { background-color: #FF6A00; color: #0d0d12; border-color: #FF6A00; font-size: 12px; font-weight: bold; min-height: 28px; }
button.voice-locked { background-color: #15151a; color: #666670; border-color: #2a2a30; font-size: 12px; min-height: 28px; }
"""


def send(key, ctrl=False, alt=False):
    if key == "shift":
        return
    if ctrl or alt:
        prefix = ("ctrl+" if ctrl else "") + ("alt+" if alt else "")
        if key in SPECIAL:
            subprocess.run(["xdotool", "key", prefix + SPECIAL[key]], check=False)
        else:
            subprocess.run(["xdotool", "key", prefix + key.lower()], check=False)
    elif key in SPECIAL:
        subprocess.run(["xdotool", "key", "--clearmodifiers", SPECIAL[key]], check=False)
    else:
        subprocess.run(["xdotool", "type", "--clearmodifiers", key], check=False)


class SlideKeyboard(Gtk.Window):
    # Wider to fit the key grid plus a right-hand voice-profile shelf.
    WIDTH = 1080
    HEIGHT = 300
    POP_OFFSET = 36  # px it rises from on pop-in, for the "pop" feel

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)  # NEVER steal focus from the target window
        self.set_app_paintable(True)

        # RGBA visual so the window background can be fully transparent —
        # without this the rounded #panel corners would show square behind
        # them (same pattern as controller-legend.py / hud_keyboard_gui.py).
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.shift_on = False

        # Outer styled panel (the rounded orange-bordered box) wraps the key
        # grid, matching the legend HUD's visual language.
        self.panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.panel.set_name("panel")
        self.panel.set_margin_start(10)
        self.panel.set_margin_end(10)
        self.panel.set_margin_top(10)
        self.panel.set_margin_bottom(10)
        self.add(self.panel)

        # LEFT COLUMN: mode bar across the top + key grid below it.
        self.left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.panel.pack_start(self.left_col, True, True, 0)

        # Mode bar: buttons left-to-right, ending at PRO.
        self.mode_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.mode_bar.set_margin_start(8)
        self.mode_bar.set_margin_end(8)
        self.mode_bar.set_margin_top(6)
        self.mode_bar.set_spacing(6)
        self.left_col.pack_start(self.mode_bar, False, False, 0)

        self._mode_buttons = []
        for mode in ("bubbly", "casual", "bold", "big", "pro"):
            labels = {
                "bubbly": "✨",
                "casual": "☕ CASUAL",
                "bold": "BOLD",
                "big": "BIG",
                "pro": "PRO",
            }
            btn = Gtk.Button(label=labels[mode])
            btn.get_style_context().add_class("mode")
            btn.connect("clicked", self._on_mode_set, mode)
            self.mode_bar.pack_start(btn, False, False, 0)
            self._mode_buttons.append((mode, btn))
        self._refresh_mode_buttons()

        self.grid = Gtk.Grid(column_spacing=4, row_spacing=4)
        self.grid.set_margin_start(8)
        self.grid.set_margin_end(8)
        self.grid.set_margin_top(6)
        self.grid.set_margin_bottom(8)
        self.left_col.pack_start(self.grid, True, True, 0)
        self._build_keys()

        # RIGHT COLUMN: voice-profile shelf from PRO down to the bottom.
        self.voice_shelf = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.voice_shelf.set_name("voice-shelf")
        self.voice_shelf.set_margin_top(6)
        self.voice_shelf.set_margin_bottom(8)
        self.voice_shelf.set_margin_end(8)
        self.panel.pack_start(self.voice_shelf, False, False, 0)

        shelf_title = Gtk.Label(label="VOICE PROFILES")
        shelf_title.get_style_context().add_class("shelf-title")
        self.voice_shelf.pack_start(shelf_title, False, False, 0)

        self._voice_buttons = []
        voices = [
            ("joe", "Joe", False),
            ("aria", "Aria", False),
            ("morgan", "Morgan 🔒", True),
            ("lexi", "Lexi 🔒", True),
        ]
        for voice, label, locked in voices:
            btn = Gtk.Button(label=label)
            if locked:
                btn.get_style_context().add_class("voice-locked")
                btn.set_sensitive(False)
                btn.set_tooltip_text("Unlock in the AI Controller store")
            else:
                btn.get_style_context().add_class("voice")
                btn.connect("clicked", self._on_voice_set, voice)
            self.voice_shelf.pack_start(btn, False, False, 0)
            self._voice_buttons.append((voice, btn, locked))
        self._refresh_voice_buttons()

        self.sw = screen.get_width()
        self.sh = screen.get_height()
        self.center_x = (self.sw - self.WIDTH) // 2
        self.center_y = (self.sh - self.HEIGHT) // 2
        self.hidden_y = self.center_y + self.POP_OFFSET

        # Gtk.WindowType.POPUP windows are override-redirect — the window
        # manager never sizes them, so set_default_size() before realization
        # is a no-op (this is why the window showed up as a stray 10x10 box
        # at 10,10). Force the size with resize(), then show_all() once to
        # realize it, then move off-screen (opacity 0) and park centered.
        # Toggling pops it in/out via combined move + fade, no further
        # show()/hide() calls, which sidesteps any more realize-timing
        # surprises.
        self.resize(self.WIDTH, self.HEIGHT)
        self.show_all()
        self.move(self.center_x, self.hidden_y)
        self.set_opacity(0.0)
        self.visible_state = False
        self._anim_id = None

    def _load_ptt_mode(self) -> str:
        try:
            with open(PTT_MODE_FILE, "r", encoding="utf-8") as f:
                mode = f.read().strip().lower()
                if mode in ("pro", "bubbly", "casual", "bold", "big"):
                    return mode
        except Exception:
            pass
        return "pro"

    def _save_ptt_mode(self, mode: str) -> None:
        os.makedirs(os.path.dirname(PTT_MODE_FILE), exist_ok=True)
        with open(PTT_MODE_FILE, "w", encoding="utf-8") as f:
            f.write(mode)

    def _refresh_mode_buttons(self):
        current = self._load_ptt_mode()
        for mode, btn in self._mode_buttons:
            if mode == current:
                btn.get_style_context().add_class("mode-active")
                btn.get_style_context().remove_class("mode")
            else:
                btn.get_style_context().add_class("mode")
                btn.get_style_context().remove_class("mode-active")

    def _on_mode_set(self, _widget, mode):
        self._save_ptt_mode(mode)
        self._refresh_mode_buttons()

    def _load_voice(self) -> str:
        try:
            with open(VOICE_FILE, "r", encoding="utf-8") as f:
                v = f.read().strip().lower()
                if v in ("joe", "aria"):
                    return v
        except Exception:
            pass
        return "joe"

    def _save_voice(self, voice: str) -> None:
        os.makedirs(os.path.dirname(VOICE_FILE), exist_ok=True)
        with open(VOICE_FILE, "w", encoding="utf-8") as f:
            f.write(voice)

    def _refresh_voice_buttons(self):
        current = self._load_voice()
        for voice, btn, locked in self._voice_buttons:
            if locked:
                continue
            if voice == current:
                btn.get_style_context().add_class("voice-active")
                btn.get_style_context().remove_class("voice")
            else:
                btn.get_style_context().add_class("voice")
                btn.get_style_context().remove_class("voice-active")

    def _on_voice_set(self, _widget, voice):
        self._save_voice(voice)
        self._refresh_voice_buttons()
        # Announce the switch
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen([sys.executable, os.path.join(script_dir, "voice_toggle.py"), "--speak", f"Switched to {voice}."],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _build_keys(self):
        for child in self.grid.get_children():
            self.grid.remove(child)
        rows = ROWS_UPPER if self.shift_on else ROWS_LOWER
        for r, row in enumerate(rows):
            for c, key in enumerate(row):
                label = LABELS.get(key, key)
                btn = Gtk.Button(label=label)
                if key in SPECIAL or key == "shift":
                    btn.get_style_context().add_class("special")
                width = 2 if key in ("space",) else 1
                btn.connect("clicked", self._on_key, key)
                self.grid.attach(btn, c, r, width, 1)
        self.grid.show_all()

    def _on_key(self, _widget, key):
        if key == "shift":
            self.shift_on = not self.shift_on
            self._build_keys()
            return
        ctrl, alt = _modifier_state()
        send(key, ctrl=ctrl, alt=alt)
        if self.shift_on:
            self.shift_on = False
            self._build_keys()

    def toggle(self):
        GLib.idle_add(self._toggle_main_thread)

    def _toggle_main_thread(self):
        opening = not self.visible_state
        target_y = self.center_y if opening else self.hidden_y
        target_op = 1.0 if opening else 0.0
        self._animate_to(target_y, target_op)
        self.visible_state = opening
        return False

    def _animate_to(self, target_y, target_opacity):
        if self._anim_id:
            GLib.source_remove(self._anim_id)
        steps = {"n": 0}

        def step():
            steps["n"] += 1
            _, cur_y = self.get_position()
            dy = target_y - cur_y
            cur_op = self.get_opacity()
            dop = target_opacity - cur_op
            done = abs(dy) < 4 and abs(dop) < 0.05
            if done or steps["n"] > 20:
                self.move(self.center_x, target_y)
                self.set_opacity(target_opacity)
                self._anim_id = None
                return False
            self.move(self.center_x, int(cur_y + dy * 0.45))
            self.set_opacity(max(0.0, min(1.0, cur_op + dop * 0.45)))
            return True

        self._anim_id = GLib.timeout_add(15, step)


PIDFILE = "/tmp/slide_keyboard.pid"

if __name__ == "__main__":
    win = SlideKeyboard()
    win.connect("destroy", Gtk.main_quit)
    # Own our PID file so external togglers always know which process to signal.
    try:
        with open(PIDFILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    # ptt_pynput.py owns the F14 listener (it already runs persistently) and
    # toggles us via SIGUSR1 — avoids two competing F14 listeners.
    signal.signal(signal.SIGUSR1, lambda *_: win.toggle())
    if "--show" in sys.argv:
        GLib.idle_add(win.toggle)
    Gtk.main()
