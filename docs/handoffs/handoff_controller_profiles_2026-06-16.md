# Handoff: Full controller profiles + keyboard swap — 2026-06-16

**Status:** Deployed and verified live. Mic (F13) and keyboard-toggle (F14) both confirmed working after the change.

---

## 1. Onboard's scanner — root cause found, NOT fixed (replaced instead)

Read Onboard's actual source (`/usr/lib/python3/dist-packages/Onboard/Scanner.py`).
Its Directed-scan mode hard-drops all keyboard events unless a non-blacklisted
device is explicitly selected, and `"Virtual core XTEST keyboard"` — the device
every software-emulated keypress (xdotool, AntiMicroX) routes through — is on
that blacklist. Structural, not a config bug. Confirmed live: `xdotool key Right`
never moved the scan highlight off the backtick key.

**Fix:** stopped trying to fix Onboard. F14 (Guide button) now toggles
`~/scripts/slide_keyboard.py` (a plain GTK click-to-type keyboard, already built
in an earlier session, now wired live) instead of launching `/usr/bin/onboard`.

## 2. `ptt_pynput.py` — `toggle_keyboard()` rewritten

- Backup before edit: `~/scripts/ptt_pynput.py.bak-pre-slidekb-20260616`.
- Old: `pgrep onboard` / SIGTERM / relaunch onboard every press.
- New: `pgrep slide_keyboard.py` / SIGUSR1 (the toggle signal the script already
  implements) if running, else lazy-launch with `--show`. No new hotkey listener
  added — same F14 dispatch in `on_press()`, only the function body changed.
- `systemctl --user restart ptt-pynput.service` applied it.

**Verified live, this session:**
- F14 → `slide_keyboard.py` launches and is visible on screen (screenshot taken).
- F13 → synthetic press/release correctly logged `Recording...` →
  `Silence detected (mic off?) — skipped` (expected, no real mic input from a
  synthetic test). Real operator dictation also went through cleanly minutes
  earlier in the same log (unrelated message about Hermes/MCP config).

**Not yet built:** the bigger Xbox/Windows-OSK-style D-pad focus-navigation
keyboard (grid highlight moves with D-pad, A selects, Done commits buffered
text) that was scoped in detail earlier this session — `slide_keyboard.py`
today is still click-to-type only (stick-as-mouse + A-click), not D-pad-navigable.
Full implementation plan exists in conversation history (GTK focus mechanism,
focus-capture/restore-then-type sequencing, POPUP-vs-TOPLEVEL focus risk) but
was not written to disk as its own doc — re-derive from this session if picked
back up, or ask Claude to re-run the Plan agent.

## 3. Two new full controller profiles (the actual ask: "two full profiles, not combined")

Repo: `~/projects/ai-controller-profile/profiles/`

- **`kodi-full.amgp`** — dedicated, 3-set Kodi remote profile. Every binding is
  Kodi's real documented default keymap key (kodi.wiki), nothing invented.
  - Set 1 (default): D-pad nav, A=Select, B=Back, X=Info, Y=Context menu,
    LB/RB=Channel±, Start=Play/Pause, Back/View=Stop, L3=Mute, R3=Fullscreen.
  - Set 2 (hold LT to flip in, LT again to flip back): Codec info, Toggle
    watched, Player debug, Eject, Record, Power/shutdown menu.
  - Set 3 (Guide cycles in/out): full 0–9 number pad for direct channel/time entry.
  - RT = F13 (dictation) preserved in every set.
- **`desktop-full.amgp`** — exact clone of the live `ai-desktop.amgp` (mouse,
  clicks, browser-back, paste; LT-toggle Ctrl-layer for copy/cut/select-all/undo;
  Guide-driven on-screen-keyboard-nav layer), saved as its own standalone file.
- `profiles/iptv.amgp` reverted to its original generic (non-Kodi-specific) scheme
  — kept separate from `kodi-full.amgp` per explicit instruction not to combine them.

**Deployed live:**
- `kodi-full.amgp` → `~/.config/antimicrox/ai-iptv.amgp`
- `desktop-full.amgp` → `~/.config/antimicrox/ai-desktop.amgp`
- Prior live files backed up to `~/.config/antimicrox/backup-20260616/`.
- `antimicrox-autoload.service` restarted to pick up the change.
- All four involved XML files passed `xml.dom.minidom` parse validation.

## 4. Git / GitHub

- `~/projects/ai-controller-profile` had **no GitHub remote at all** before this
  session (local commits only, 4 of them, plus a pile of staged-but-uncommitted
  work from an earlier session that got swept into this commit too).
- Committed everything (`fc1a0b7`, then `f0c78ff` for a `.gitignore`/pycache cleanup).
- Created **new private repo** `https://github.com/ebey317/ai-controller-profile`
  via `gh repo create` (operator's authenticated `gh` login) and pushed `master`.
- This is now the durable backup or this is now reachable if rebuilding from
  GitHub is ever needed.

## Files touched this session

| File | State |
|---|---|
| `~/scripts/ptt_pynput.py` | Edited (`toggle_keyboard()`), live, verified |
| `~/scripts/ptt_pynput.py.bak-pre-slidekb-20260616` | Pre-edit backup |
| `~/projects/ai-controller-profile/profiles/kodi-full.amgp` | New |
| `~/projects/ai-controller-profile/profiles/desktop-full.amgp` | New |
| `~/projects/ai-controller-profile/profiles/iptv.amgp` | Reverted to original |
| `~/.config/antimicrox/ai-iptv.amgp` | Replaced with kodi-full content, live |
| `~/.config/antimicrox/ai-desktop.amgp` | Replaced with desktop-full content, live |
| `~/.config/antimicrox/backup-20260616/` | Pre-deploy backups of both live files |
| GitHub `ebey317/ai-controller-profile` | New private repo, pushed |
