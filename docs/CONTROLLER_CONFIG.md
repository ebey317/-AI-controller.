# Xbox Controller Configuration — Elijah Desktop

**Device:** Microsoft Xbox Series Controller  
**USB ID:** `045e:0b12`  
**Live evdev node:** `/dev/input/event6`  
**Active AntiMicroX profile:** `/home/elijah/.config/antimicrox/ai-desktop.amgp`  

## Button Map — General (Desktop / Browser / Typing)

| Control | Action | Mechanism |
|---------|--------|-----------|
| RT (Right Trigger) hold | Start voice dictation | F13 → `ptt_pynput.py` |
| RT release | Stop dictation + type result | F13 release |
| R3 (Right Stick click) tap | Enter / Return | `0x1000004` |
| R3 (Right Stick click) hold ~1.2s | Toggle on-screen keyboard | F14 → `ptt_pynput.py` |
| LS (Left Stick click) | Space | `0x20` |
| A | Left mouse click | mousebutton |
| B | Back / Escape | `0x1000001` |
| X | Backspace | `0x1000008` |
| Y | Paste | `0x1000056` (Ctrl+V) |
| Left Stick | Move mouse cursor | stick → cursor |
| D-Pad / Right Stick scroll | Browser/typing navigation | scroll |

## Services (user systemd)

```
antimicrox-autoload    -> /home/elijah/scripts/controller-profile-switcher.sh
ptt-pynput             -> /home/elijah/scripts/ptt_pynput.py
voice-bridge           -> /home/elijah/projects/claf/scripts/voice_bridge.py (if present)
browser-focus-controller
```

## Key files

- `/home/elijah/.config/antimicrox/ai-desktop.amgp` — active profile
- `/home/elijah/.config/antimicrox/ai-desktop.amgp.bak-r3-1200ms` — latest backup
- `/home/elijah/scripts/controller-profile-switcher.sh` — profile auto-loader
- `/home/elijah/scripts/ptt_pynput.py` — F13/F14 listener + dictation/keyboard
- `/home/elijah/scripts/slide_keyboard.py` — on-screen keyboard toggle

## How to restart after edits

```bash
systemctl --user daemon-reload
systemctl --user restart antimicrox-autoload ptt-pynput
```

## Note

As of 2026-06-17 the window-focus profile switcher is locked to always load `ai-desktop.amgp`, so this single profile works across desktop, browser, and typing contexts.
