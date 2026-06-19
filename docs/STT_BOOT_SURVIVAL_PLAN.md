# Boot Survival Plan: Will STT Work Tomorrow?
## Analysis Date: 2026-06-18

## VERDICT: No. STT will be dead on reboot. Five dependencies will break.

---

## The 5 Boot-Time Failure Points

### 1. UDEV RULES KILL THE HEADSET MIC (CRITICAL)
Two udev rules are fighting each other:
- `/etc/udev/rules.d/50-xbox-controller-no-headset.rules` — disables the headset USB interface on add (`ATTR{authorized}="0"`)
- `/etc/udev/rules.d/51-xbox-headset-unbind.rules` — auto-unbinds the headset interface on add

BOTH of these destroy the controller headset audio interface at boot. The mic (`alsa_input.usb-Microsoft_Controller_...-00.mono-fallback`) will NOT exist after reboot. STT will record silence → Whisper hallucinates "Thank you" → broken.

This is the same ENOSPC prevention strategy from earlier sessions, but it means STT can NEVER survive a cold boot without manual intervention. You'd need to run the headset reload script (`/tmp/fix_headset_audio2.sh`) every single time.

**Fix needed**: Remove or modify these udev rules so the headset interface survives boot. Accept the ENOSPC flood risk, or find a way to load the module without the flood (may require driver fork — `github.com/dlundqvist/xone` has fixes).

### 2. .Xmodmap vs SWITCHER KEYCODE CONFLICT (CRITICAL)
- `.Xmodmap` maps: `keycode 191 = F13`
- `controller-profile-switcher.sh` maps: `keycode 202 = F13`
- Live system shows: `keycode 202 = F13` (correct, from switcher), `keycode 191 = XF86Tools` (stale, from .Xmodmap)

The switcher runs AFTER .Xmodmap at boot and overwrites keycode 202. This currently works because the service starts after the session. BUT: if the service fails to start (see #3), only .Xmodmap's keycode 191 mapping would apply, and ptt_pynput may not detect F13 on the correct keycode.

**Fix needed**: Update `.Xmodmap` to `keycode 202 = F13` to match the switcher. Belt and suspenders.

### 3. ANTIMICROX BOOT RACE (MODERATE RISK)
`antimicrox-autoload.service` has `Restart=always` and `RestartSec=2`, which is good. But:
- If the controller USB isn't fully enumerated when the service starts (GIP handshake takes 3-5s), AntiMicroX may launch with no controller → SDL fails to open joystick → profile loads but no device attached
- The switcher script's `controller_present()` checks `/dev/input/js0` — if the controller isn't ready, it waits and loads the profile when js0 appears. This is correct.
- BUT: the 3.5.1 profile-wipe race (pitfall #58) can still strike — AntiMicroX loads the profile, then 12ms later a second init pass wipes all mappings to [NO KEY]. This is a bug in 3.5.1 with no fix (3.6.1 crashes on this kernel).

**Mitigation**: The switcher script's 1-second sleep + restart loop usually recovers from the wipe race on the second iteration, but not always. No reliable fix exists without upgrading AntiMicroX (which requires a newer kernel/Qt6).

### 4. PTT-PYNPUT XAUTHORITY RACE (LOW-MODERATE RISK)
`ptt-pynput.service` has `After=graphical-session.target` and `Environment=XAUTHORITY=%h/.Xauthority`. If the graphical session isn't fully up when systemd fires, pynput gets `Invalid MIT-MAGIC-COOKIE-1` and crashes. The service has `Restart=on-failure` with `RestartSec=3`, so it should recover — but it may take several restart cycles.

**Mitigation**: Already handled by `Restart=on-failure`. Should self-heal within 10-15 seconds of desktop being ready.

### 5. VOICE-BRACE STARTUP ORDER (LOW RISK)
`ptt-pynput.service` has `Wants=voice-bridge.service` but `Wants=` is weak — it doesn't wait for voice-bridge to be ready, just tries to start it. If voice-bridge takes >3s to bind port 8002, the first few RT presses will fail silently. ptt-pynput won't crash (it just gets connection refused), but dictation won't work until voice-bridge is up.

**Mitigation**: voice-bridge is a simple Python HTTP server, should start in <1s. Low risk.

---

## The Core Dilemma: ENOSPC vs STT

You cannot have BOTH:
- **Headset mic for STT** requires `xone_gip_headset` loaded and the USB interface authorized
- **GIP bus stability** requires the headset interface disabled/blacklisted (prevents ENOSPC flood → kernel oops → trigger death)

The udev rules currently choose stability (disable headset at boot). That's why STT works NOW (you manually loaded the module) but will break on reboot.

**Three paths forward:**

### Path A: Accept the ENOSPC Risk (STT-first)
Remove the headset-disabling udev rules. Let `xone_gip_headset` load at boot. STT works from boot. Risk: ENOSPC flood every ~63s, which over hours can destabilize the GIP bus and kill triggers (requiring USB replug).

Mitigation: Run a cron job that reloads `xone_gip_headset` every 2 hours before the buffer fully backs up. Requires sudo cron — write a root cron job.

### Path B: Use Motherboard Mic (Stability-first)
Keep the udev rules. Route STT to `alsa_input.pci-0000_28_00.4.analog-stereo` (motherboard audio jack). You'd need a physical mic plugged into the front panel audio jack. No ENOSPC risk, no controller dependency for STT input.

### Path C: Hybrid — USB Mic or Headset Dongle
Use a dedicated USB mic (not the controller) for STT input. No GIP dependency at all. Controller stays stable. This is the most reliable option but requires hardware.

---

## What Needs To Change For Path A (Recommended)

### Files to modify:
1. **DELETE** `/etc/udev/rules.d/50-xbox-controller-no-headset.rules` (disables headset interface)
2. **DELETE** `/etc/udev/rules.d/51-xbox-headset-unbind.rules` (auto-unbinds headset)
3. **UPDATE** `~/.Xmodmap` — change `keycode 191` to `keycode 202` (match switcher)
4. **CREATE** root cron job — reload `xone_gip_headset` every 2 hours
5. **KEEP** `/etc/udev/rules.d/50-xbox-controller-stable.rules` (USB autosuspend disable)
6. **KEEP** `/etc/udev/rules.d/50-xbox-led.rules` (LED on)

### What stays the same (already boot-safe):
- `antimicrox-autoload.service` — enabled, auto-starts, restarts on failure ✓
- `ptt-pynput.service` — enabled, auto-starts, restarts on failure ✓
- `voice-bridge.service` — enabled, starts with ptt-pynput ✓
- `controller-profile-switcher.sh` — launched by service, maps F13 to keycode 202 ✓
- `ai-desktop.amgp` — profile file, RT→F13 (0x100003c) ✓
- `ptt_pynput.py` — uses controller headset mic source ✓
- `controller_paste.py` — exists at expected path ✓
- xone DKMS module — auto-builds on kernel update ✓
- xone modules auto-load via USB device match (no modules-load.d needed) ✓

### Remaining unfixable risks (accept and monitor):
- AntiMicroX 3.5.1 profile-wipe race — no fix on this kernel. Switcher loop usually recovers.
- GIP boot-time EBUSY race — xone_wired can hit -16 on boot, killing triggers permanently. Only fix is physical replug after boot. Cannot prevent.
- ENOSPC flood will return over hours — cron reload mitigates but doesn't eliminate.

---

## Profile Gaps vs Desired Layout

Your desired layout (the table you pasted) has differences from the current .amgp:

| Button | Desired | Current .amgp | Status |
|--------|---------|---------------|--------|
| A | Left-Click | mousebutton code=1 ✓ | OK |
| B | Backspace/Escape | keyboard 0x1000000 (Esc) | Partial — no Backspace |
| X | Delete | keyboard 0x43 (letter 'c') | WRONG — should be Delete (0x1000003) |
| Y | Super key | NOT MAPPED | MISSING |
| View (⧉) | Toggle onboard | keyboard 0x20 (Space) | WRONG — should launch onboard |
| Menu (☰) | Tab | keyboard 0x1000004 (Enter) | WRONG — should be Tab (0x1000001) |
| RT | STT (F13) | 0x100003c ✓ | OK |
| LT | Hold Ctrl | 0x1000001 (Tab) | WRONG — should be Ctrl (0x1000021) |
| RB | Right-Click | mousebutton code=3 ✓ | OK |
| LB | Hold Shift | keyboard 0x20 (Space) | WRONG — should be Shift (0x1000020) |
| LS click | Spacebar | keyboard 0x1000000 (Esc) | WRONG — should be Space (0x20) |
| RS click | Enter | mousebutton code=3 (right-click) | WRONG — should be Enter (0x1000004) |
| D-Pad | Arrow keys | 0x6100000f / 0x1000010 / 0x1000011 / 0x6100000e | Need verification |
| Guide | Super+Tab | button 9: 0x1000004 (Enter) | WRONG — should be Super+Tab |
| Button 4 (paste) | — | EXECUTE controller_paste.py | Not in desired layout |
| Button 19 | — | keyboard 0x43 | Unknown — not in desired layout |

**The current profile does NOT match your desired layout.** The profile would need to be rewritten to match. That's a separate task from the boot-survival fixes above.

---

## Summary: What To Do (Plan Only)

### Phase 1: Boot Survival (do first)
1. Delete the two headset-disabling udev rules (needs sudo)
2. Fix .Xmodmap keycode 191 → 202
3. Create root cron job to reload xone_gip_headset every 2h (needs sudo)
4. Test: reboot, verify STT works within 30s of desktop being ready

### Phase 2: Profile Rewrite (do second, separate session)
1. Rewrite ai-desktop.amgp from the desired layout table
2. Verify each hex code against amgp-keycode-reference.md
3. Test every button mapping individually
4. Save new golden snapshot to git + desktop

### Phase 3: Monitoring (ongoing)
1. Watch dmesg for ENOSPC floods after boot
2. If triggers die after hours of use, USB replug
3. If kernel oops occurs, reboot (no software recovery)