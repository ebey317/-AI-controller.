# AI CONTROLLER — COMPLETE STANDALONE CONFIGURATION
# Machine: Elijah (elijah-MS-7B86)
# Updated: 2026-06-18 — single source of truth (merged + verified against live profile)
# Status: Production — all services systemd-managed, survive reboot

> This is the ONE canonical config file. It supersedes the old
> `CONTROLLER_CONFIG.md` (2026-06-17), whose unique facts (USB ID, evdev node,
> restart commands) are folded in below.

## WHAT THIS IS

The complete configuration for Elijah's standalone AI workstation.
Every component is systemd-managed and boots itself. No manual intervention
required after power-on. Controller → talk → local AI answers out loud, offline.

## HARDWARE

- **Device:** Microsoft Xbox Series Controller
- **USB ID:** `045e:0b12`
- **evdev node:** dynamic (seen as `/dev/input/event2` / `event6`, `js0`) — the
  switcher watches `/dev/input/js0`; re-enumerates on replug.
- **Active AntiMicroX profile:** `~/.config/antimicrox/ai-desktop.amgp`

## ARCHITECTURE OVERVIEW

Elijah boots → systemd starts everything → user picks up controller → talks

Layer 1 (system services):
  - Ollama          → local LLM inference (no cloud)
  - Tailscale       → peer-to-peer network mesh
  - Network/Display → standard Linux boot

Layer 2 (user services, all enabled):
  - Hermes Gateway  → messaging platform integration
  - Hermes Agent    → auto-starts in tmux (REQUIRES tmux install)
  - CLAF            → agent framework proxy
  - Voice Bridge    → PTT → STT → LLM → speech
  - PTT/pynput      → push-to-talk key listener (F13 trigger)
  - Sensei Bridge   → Chrome MCP bridge
  - AntiMicroX      → controller-to-keyboard/mouse mapping
  - Controller Legend → floating HUD showing button assignments
  - Browser Focus   → window-focus profile dispatcher
  - CLAF Timer      → engagement loop every 2 minutes

Layer 3 (per-utterance, not a service):
  - hermes_tts_play.sh → mpv playback to headphones (called on-demand)
  - mpv               → audio player (per-utterance, fire-and-forget)

## CONTROLLER PROFILE — VERIFIED BUTTON MAP

Decoded directly from the live `~/.config/antimicrox/ai-desktop.amgp`
(verified 2026-06-18; AntiMicroX index → physical button → action):

| Physical | AntiMicroX index | Action | Code |
|----------|------------------|--------|------|
| A | button 1 | Left Click (mouse) | mousebutton 1 |
| B | button 2 | Backspace | `0x1000003` |
| X | button 3 | Delete | `0x1000007` |
| Y | button 4 | Super / Meta (Windows key) | `0x1000022` |
| View (⧉) | button 5 | Toggle slide on-screen keyboard | `[Exec] toggle-slide-keyboard.sh` |
| Guide (logo) | button 6 | Super+Tab (window cycle) | `0x1000022` + `0x1000001` |
| Menu (☰) | button 7 | Tab | `0x1000001` |
| LS (Left Stick click) | button 8 | Space | `0x20` |
| RS (Right Stick click) | button 9 | Enter / Return | `0x1000004` |
| LB | button 10 | Hold Shift | `0x1000020` |
| RB | button 11 | Right Click | mousebutton 3 ⚠️ |
| LT | trigger 5 | Hold Ctrl | `0x1000021` |
| RT | trigger 6 | **F13 — STT trigger (LOCKED)** | `0x100003c` |
| Left Stick | stick 1 | Smooth mouse move | mousemovement |
| Right Stick | stick 2 | Scroll wheel (up/down) | wheel 4/5 |
| D-Pad | dpad 1 | Arrow keys (Up/Down/Left/Right) | `0x1000012-15` |

⚠️ **RB caveat:** the live profile encodes RB as AntiMicroX mouse button **3**,
which is typically *middle*-click. If RB does not right-click in practice,
change its slot to mouse button **2**. (A=button 1 = left is confirmed.)

### Legend HUD Layout (controller-legend.py, orange #FF6A00):
  A=Click, B=Bksp, X=Del, Y=Super, LB=Shift, RB=R·Clk, LT=Ctrl, RT=Talk,
  View=Kbd, ≡=Tab, Logo=W·Tab, LS=Space, RS=Enter, D↕=Arrows

## SERVICE FILES

### 1. hermes-agent.service (auto-starts agent on boot)
Path: ~/.config/systemd/user/hermes-agent.service
Status: enabled, waiting for tmux install (see blocker below)

```
[Unit]
Description=Hermes Agent Session — auto-start chat in tmux on boot
After=graphical-session.target hermes-gateway.service claf.service voice-bridge.service
Wants=graphical-session.target
Requires=hermes-gateway.service

[Service]
Type=forking
ExecStart=/usr/bin/tmux new-session -d -s hermes -x 220 -y 50 '/home/elijah/.hermes/hermes-agent/venv/bin/hermes chat --continue'
WorkingDirectory=/home/elijah
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/%U
Environment=TERM=xterm-256color
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

### 2. antimicrox-autoload.service (controller mapping)
Path: ~/.config/systemd/user/antimicrox-autoload.service
ExecStart: ~/scripts/controller-profile-switcher.sh — locked to always load ai-desktop.amgp
Status: enabled, active

### 3. hermes-gateway.service (messaging integration)
Path: ~/.config/systemd/user/hermes-gateway.service · ExecStart: hermes gateway run · enabled, active

### 4. claf.service (agent framework proxy)
Path: ~/.config/systemd/user/claf.service · ExecStart: ~/projects/claf/orchestrator.py · enabled, active

### 5. voice-bridge.service (STT pipeline)
Path: ~/.config/systemd/user/voice-bridge.service · ExecStart: ~/projects/ai-controller-profile/scripts/voice_bridge.py · enabled, active

### 6. ptt-pynput.service (push-to-talk listener)
Path: ~/.config/systemd/user/ptt-pynput.service · ExecStart: ~/scripts/ptt_pynput.py · enabled, active

### 7. sensei-bridge.service (Chrome MCP)
Path: ~/.config/systemd/user/sensei-bridge.service · ExecStart: ~/scripts/sensei_bridge.py · enabled, active

### 8. controller-legend.service (floating HUD)
Path: ~/.config/systemd/user/controller-legend.service · ExecStart: ~/scripts/controller-legend.py · enabled, active

### 9. browser-focus-controller.service (profile switcher)
Path: ~/.config/systemd/user/browser-focus-controller.service · ExecStart: ~/scripts/browser_focus_controller.py · enabled, active

### 10. claf-engagement.timer (2-min loop)
Path: ~/.config/systemd/user/claf-engagement.timer · enabled, active

## ONE BLOCKER: tmux NOT INSTALLED

The hermes-agent.service requires tmux for a persistent pseudo-terminal.
tmux is NOT currently installed.

FIX: `sudo bash /tmp/install_tmux.sh`

Until tmux is installed, the agent session won't auto-start on boot.
Everything else works.

## VOICE PIPELINE — NOW 100% LOCAL (updated 2026-06-18)

The full loop runs offline. Hermes config: `~/.hermes/config.yaml`
(backup: `~/.hermes/config.yaml.bak-20260618`).

| Stage | Engine | Setting | Local? |
|-------|--------|---------|--------|
| **STT** | faster-whisper `base` | `stt.provider: local`, `stt.local.model: base` | ✅ offline |
| **LLM** | Ollama `qwen2.5-coder:fast` | `model.default: qwen2.5-coder:fast` (fallback `qwen2.5-coder:64k`, provider `ollama-launch` @ `127.0.0.1:11434`) | ✅ offline |
| **TTS** | Piper (joe voice) | `tts.provider: piper`, `tts.piper.voice: /home/elijah/.local/share/piper/en_US-joe-medium.onnx` | ✅ offline |
| Playback | mpv via hermes_tts_play.sh | lowpass f=3000, sink = motherboard 3.5mm analog | — |
| Auto-speak | `voice.auto_tts: true` | responses spoken automatically (hands-free) | — |

**Voice controls:** record key `ctrl+b` (Hermes) and Xbox **RT → F13** (PTT via
ptt_pynput.py → voice_bridge). Max 120s/utterance, auto-stops after 3s silence.

**Why local Piper voice path is absolute:** the configured `en_US-lessac-medium`
voice had a 0-byte `.json` (broken download). Switched to the verified-working
`en_US-joe-medium.onnx` via absolute path so Piper loads it directly with no
download — guaranteeing offline operation. Verified: Hermes' own `_generate_piper_tts`
produced a WAV with no network. (`en_US-joe-medium.onnx` 63MB + `.onnx.json` 4794B.)

**CLAF hybrid escape hatch:** when a question genuinely needs the big cloud brain,
route via CLAF (`:8000`) which can escalate to cloud models; default stays local.

## FILES

```
Controller profile:   ~/.config/antimicrox/ai-desktop.amgp
Profile switcher:      ~/scripts/controller-profile-switcher.sh
slide-kbd toggle:      ~/scripts/toggle-slide-keyboard.sh   (View button — show/hide via SIGUSR1)
onboard toggle:        ~/scripts/onboard-toggle.sh          (legacy, superseded by slide toggle)
alt-tab helper:        ~/scripts/alt-tab.sh
Legend HUD:            ~/scripts/controller-legend.py
TTS playback:          ~/scripts/hermes_tts_play.sh
PTT listener:          ~/scripts/ptt_pynput.py
On-screen keyboard:    ~/scripts/slide_keyboard.py
Voice bridge:          ~/projects/ai-controller-profile/scripts/voice_bridge.py
Hermes config:         ~/.hermes/config.yaml
Piper voice (TTS):     ~/.local/share/piper/en_US-joe-medium.onnx
Sensei bridge:         ~/scripts/sensei_bridge.py
Browser focus:         ~/scripts/browser_focus_controller.py
CLAF:                  ~/projects/claf/orchestrator.py
Autostart (sensei):    ~/scripts/master_ai_autostart.sh
tmux install script:   /tmp/install_tmux.sh
```

## HOW TO RESTART AFTER EDITS

```bash
# Controller profile / PTT
systemctl --user daemon-reload
systemctl --user restart antimicrox-autoload ptt-pynput

# Voice config (after editing ~/.hermes/config.yaml)
systemctl --user restart hermes-gateway
```

## REBOOT SURVIVAL STATUS

SURVIVES REBOOT:
  [x] Ollama (system service)
  [x] Tailscale (system service)
  [x] Hermes Gateway (user service)
  [x] CLAF (user service)
  [x] Voice Bridge (user service)
  [x] PTT/pynput (user service)
  [x] Sensei Bridge (user service)
  [x] AntiMicroX + profile switcher (user service)
  [x] Controller Legend HUD (user service)
  [x] Browser Focus Controller (user service)
  [x] CLAF Engagement Timer (user timer)
  [x] TTS playback (per-utterance script, mpv system-managed)
  [x] PulseAudio/PipeWire (system service)
  [x] Controller profile + local Piper voice (files on disk)

DOES NOT SURVIVE REBOOT (until tmux is installed):
  [ ] Hermes Agent Session (hermes-agent.service — enabled but needs tmux)

## GITHUB REPO

Standalone repo "AI Controller" for this configuration.
Target: https://github.com/ebey317/ai-controller

Contents to include:
  - ai-desktop.amgp (controller profile)
  - controller-legend.py (HUD)
  - controller-profile-switcher.sh
  - onboard-toggle.sh, alt-tab.sh
  - hermes_tts_play.sh (TTS playback)
  - ptt_pynput.py (push-to-talk)
  - All systemd service files
  - This README (AI_CONTROLLER_STANDALONE_CONFIG.md)
