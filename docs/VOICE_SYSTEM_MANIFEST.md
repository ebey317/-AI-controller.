# 🎙️ SOVEREIGN VOICE CONFIGURATION
**Status:** Operational | **Persona:** Madam Mary | **Fidelity:** High (Edge-TTS)

## 🛠️ Technical Stack
- **Engine:** Edge-TTS (Cloud-Natural) $\rightarrow$ Fallback to Piper (Local)
- **Voice Profile:** `en-US-AriaNeural`
- **Playback Tool:** `mpv` (Force-bypass for suspended sinks)
- **Audio Sink:** `alsa_output.pci-0000_28_00.4.analog-stereo` (Headphones)
- **Queue System:** FIFO via `/tmp/voice_queue.txt`

## ⚙️ Configuration Files
- **Logic:** `/home/elijah/scripts/voice_daemon.py`
- **Dispatcher:** `/home/elijah/scripts/voice_dispatcher.py`
- **Settings:** `/home/elijah/scripts/voice_config.json`

## 🚀 Quick-Start / Recovery
To restart the voice engine if it stalls:
`pkill -9 -f voice_daemon.py && python3 /home/elijah/scripts/voice_daemon.py &`

To test a specific phrase:
`echo "Test phrase" > /tmp/voice_queue.txt`
