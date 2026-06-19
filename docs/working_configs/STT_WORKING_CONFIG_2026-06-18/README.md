# STT Working Configuration — 2026-06-18

## What This Is
The complete, known-working configuration for Elijah's AI Controller STT (push-to-talk dictation) pipeline. Saved at the moment it was confirmed working after fixing an ENOSPC audio buffer flood.

## The Pipeline
1. RT trigger on Xbox controller → AntiMicroX maps to F13 (0x100003c) via xtest injection
2. ptt_pynput.py detects F13 via pynput → starts recording from controller headset mic
3. parec captures 24kHz mono audio from `alsa_input.usb-Microsoft_Controller_...-00.mono-fallback`
4. Audio POSTed to voice-bridge (localhost:8002) → Groq Whisper transcribes
5. Transcript typed via xdotool (with window focus save/restore)

## Files In This Archive
| File | Purpose | Install Location |
|------|---------|-----------------|
| ai-desktop.amgp | AntiMicroX button/trigger profile | ~/.config/antimicrox/ai-desktop.amgp |
| ptt_pynput.py | PTT listener + recorder + typer | ~/scripts/ptt_pynput.py |
| voice_config.json | Voice bridge config (sink, mode) | ~/scripts/voice_config.json |
| controller-profile-switcher.sh | AntiMicroX launch script with --eventgen xtest | ~/scripts/controller-profile-switcher.sh |
| antimicrox-autoload.service | Systemd user service for auto-start | ~/.config/systemd/user/antimicrox-autoload.service |
| ptt-pynput.service | Systemd user service for PTT listener | ~/.config/systemd/user/ptt-pynput.service |
| .Xmodmap | F13 keycode mapping (keycode 202 = F13) | ~/.Xmodmap |
| fix_headset_audio_ENOSPC.sh | Script to fix ENOSPC buffer flood (needs sudo) | /tmp/fix_headset_audio2.sh |

## Key Settings (DO NOT CHANGE)
- RT trigger → F13: hex code 0x100003c (Qt::Key_F13). NOT 0x100003d (that's F14, breaks STT)
- F13 X11 keycode: 202
- AntiMicroX flag: --eventgen xtest (REQUIRED for pynput detection)
- ptt_pynput mode: transcribe_only (NOT execute — execute routes through LLM chat)
- Mic source: alsa_input.usb-Microsoft_Controller_3039373130383038333134313433-00.mono-fallback (controller headset)
- SDL trigger indices: 5=LT→Tab, 6=RT→F13 (OPPOSITE of evdev axis codes)
- AntiMicroX version: 3.5.1 (DO NOT upgrade to 3.6.1 — SIGSEGV on Qt6 6.2.4)

## Known Recurring Issue: ENOSPC Buffer Flood
The xone_gip_headset module floods `gip_send_audio_samples: get buffer failed: -28` every ~63 seconds. This eventually backs up the audio channel until the mic captures zero bytes. Symptoms: ptt-pynput logs show "Recording..." → "Too short — skipped" in rapid succession.

Fix: `sudo bash /tmp/fix_headset_audio2.sh` (or the copy in this archive). Reloads xone_gip_headset after suspending PulseAudio's hold. If that fails (module in use), physically unplug/replug controller USB.

## Backup Locations
1. Desktop: ~/Desktop/STT_WORKING_CONFIG_2026-06-18/
2. Git repo: ~/projects/master-ai-context/CONFIGS/STT_WORKING_CONFIG_2026-06-18/
3. GitHub: github.com/ebey317/master-ai-context (push to persist off-machine)