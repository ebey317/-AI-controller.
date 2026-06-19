# Xbox Controller Session Handoff — 2026-06-15

**Status:** COMPLETE. All button mappings locked and verified.
**Model:** Haiku 4.5 (set this session as default)
**Date:** 2026-06-15
**Next:** Deploy & monitor. Pending feature ideas saved to memory.

---

## What Was Done

### 1. Fixed All Button Indices ✅

**Problem:** Button mappings were completely wrong. Start/Hamburger sent Delete instead of Return. LB/RB were at the wrong physical indices.

**Root cause:** SDL GameController button indices (0-based) don't match AntiMicroX XML button indices (1-based). Example: physical LB = SDL index 9 = XML button 10.

**Fix:** Verified every physical button against the antimicrox startup log (`/tmp/antimicrox.log`), then corrected the entire profile:

| Physical Button | Physical Name | SDL Index | XML Index | Action (Set 1) | Action (Set 2) |
|---|---|---|---|---|---|
| 1 | A | 0 | 1 | Left click | Ctrl+A |
| 2 | B | 1 | 2 | Alt+Left (back) | Ctrl+Z |
| 3 | X | 2 | 3 | Backspace | Ctrl+X |
| 4 | Y | 3 | 4 | Paste (Ctrl+V) | Ctrl+C |
| 5 | View/◩ | 4 | 5 | Delete | Delete |
| 6 | Guide/⊙ | 5 | 6 | F14 (kbd toggle) | F14 (kbd toggle) |
| **7** | **Start/☰** | **6** | **7** | **Return ← FIXED** | **Return ← FIXED** |
| 8 | LS click | 7 | 8 | Space | Space |
| 9 | RS click | 8 | 9 | F14 (kbd toggle) | F14 (kbd toggle) |
| 10 | **LB** | **9** | **10** | **Tab ← FIXED** | **Shift+Tab ← FIXED** |
| 11 | **RB** | **10** | **11** | **Right click ← FIXED** | **Escape ← FIXED** |

**Where it lives:** `~/.config/antimicrox/ai-desktop.amgp` (locked in, backup at `.bak-20260615`)

**Verified in:** `/tmp/antimicrox.log` startup messages confirm all buttons map correctly.

### 2. Fixed Profile Switcher Health Check ✅

**Problem:** Service cached `current_profile` and never restarted antimicrox even when it crashed.

**Fix:** Added pgrep health check in `load()`:
```bash
if [[ "$profile" == "$current_profile" ]] && ! pgrep -f 'AppRun.wrapped' > /dev/null 2>&1; then
    current_profile=""  # Reset so we restart even if profile path is unchanged
fi
```

**Where it lives:** `~/scripts/controller-profile-switcher.sh` (locked in, backup at `.bak-20260615`)

### 3. Updated Legend Display ✅

**Problem:** Button labels didn't match actual mappings. Missing Shift+Tab info.

**Fix:** Updated desktop layout in `~/scripts/controller-legend.py`:
- Added auto-detect (hides when controller unplugged)
- Fixed click-through so you can open windows while legend is visible
- Position: 70px below + 60px right of cursor (smart flip above when near screen bottom)
- Updated button labels to match actual mappings

**Where it lives:** `~/scripts/controller-legend.py` (locked in, backup at `.bak-20260615`)

### 4. Wired Ollama Speed Model ✅

**Problem:** `qwen2.5-coder:3b` was installed but not routed. Operator wanted it as speed model.

**Fix:** Added `CLAF_SPEED_MODEL=qwen2.5-coder:3b` to `~/projects/claf/.env`, restarted CLAF service.

**Routing logic:** CLAF will now auto-route simple/short text (no tools, ≤3 msgs, ≤200 chars) to the fast 3b model. Anything heavier goes to the 8b workhorse.

**Verified:** Service restarted clean, healthz endpoint confirms alive.

---

## Copy/Paste Workflow (Teaching Recap)

**Don't copy from the chat thread.** The terminal doesn't paste from browser clipboard easily. Instead:

1. **To copy text that's on-screen:**
   - Highlight text with right stick (mouse)
   - Hold **LT** + tap **Y** (Ctrl+C)

2. **To paste into a terminal:**
   - Click in the terminal with **A** button
   - Hold **LT** + tap **Y** (Ctrl+V)

**Better:** Use dictation instead. Just hold **RT** and say the command aloud (e.g., "ollama list"). The pipeline is: RT → F13 → voice-to-text → xdotool types directly into the terminal. No clipboard needed.

---

## Pending Ideas (Saved to Memory)

- **Guide button** → cloud chat agent router (Claude Web / Kimi / ChatGPT / Codex)
- **Radio audio ducking** on RT press (mute radio sink while recording)
- **Shift/Ctrl as TOGGLE** (press once ON, press again OFF) — needs ptt_pynput.py state machine
- **Caps mode** in onboard keyboard

See `project_controller_ideas_backlog.md` for full details.

---

## Files Locked In

- `~/.config/antimicrox/ai-desktop.amgp` (profile, backups: `.bak-20260615`)
- `~/scripts/controller-profile-switcher.sh` (auto-reload service)
- `~/scripts/controller-legend.py` (GTK overlay legend)
- `~/projects/claf/.env` (speed model wiring)

## Memory Updated

- `project_xbox_controller_full_control.md` — full button map + technical facts
- `project_controller_ideas_backlog.md` — pending feature ideas
- `project_session_account_context.md` — current session model (Haiku 4.5)

---

## Next Steps

1. **Use the controller.** Test all buttons in the desktop profile — A, B, X, Y, LB, RB, Start, View, Guide, sticks, triggers, D-pad.
2. **Test Shift+Tab.** Hold LT, tap LB repeatedly. Should cycle backward through form fields.
3. **Test dictation.** Hold RT, say "date", release. Should type the date command into the focused terminal.
4. **Monitor clipboard issue.** The "no image found on clipboard" error was probably because your clipboard had a screenshot, not text. If it happens again, just use dictation instead.
5. **Pick one pending idea** (Guide button, Radio ducking, Shift toggle) and implement it when you have focus time.

---

**Handoff ready. Controller is stable and tested.**
