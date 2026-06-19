#!/usr/bin/env python3
"""
Toggle the active AI controller TTS voice between available Piper voice packs.
State is stored in ~/.config/ai_controller_voice.
Can be triggered from the keyboard, a controller button, or the command line.
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from scipy import signal
from scipy.io import wavfile

STATE_FILE = os.path.expanduser("~/.config/ai_controller_voice")
UNLOCKS_FILE = os.path.expanduser("~/.config/ai_controller_unlocked_voices.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICES_DIR = os.path.join(SCRIPT_DIR, "voices")

_DEVNULL = subprocess.DEVNULL


def _discover_voices():
    """Find all voice packs under voices/ with valid config + onnx model."""
    voices = []
    if not os.path.isdir(VOICES_DIR):
        return voices
    for voice_id in sorted(os.listdir(VOICES_DIR)):
        voice_path = os.path.join(VOICES_DIR, voice_id)
        if not os.path.isdir(voice_path):
            continue
        config_path = os.path.join(voice_path, "config.json")
        if not os.path.exists(config_path):
            continue
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            continue
        # find any .onnx model in the pack (locked placeholders may ship without one)
        onnx_files = [n for n in os.listdir(voice_path) if n.endswith(".onnx")]
        model_file = None
        if onnx_files:
            model_file = onnx_files[0]
        if cfg.get("model"):
            candidate = cfg["model"]
            if os.path.exists(os.path.join(voice_path, candidate)):
                model_file = candidate
        if model_file is None and not cfg.get("locked"):
            # base/free voices must have a working model
            continue
        voices.append({
            "id": voice_id,
            "name": cfg.get("name", voice_id),
            "label": cfg.get("label", voice_id.upper()),
            "locked": bool(cfg.get("locked", False)),
            "price": cfg.get("price", ""),
            "description": cfg.get("description", ""),
            "model": os.path.join(voice_path, model_file) if model_file else None,
        })
    return voices


def _load_unlocks():
    try:
        with open(UNLOCKS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_unlocks(unlocks):
    os.makedirs(os.path.dirname(UNLOCKS_FILE), exist_ok=True)
    with open(UNLOCKS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(unlocks), f, indent=2)


def is_unlocked(voice_id):
    voice = get_voice(voice_id)
    if not voice or not voice["locked"]:
        return True
    return voice_id in _load_unlocks()


def unlock(voice_id):
    unlocks = _load_unlocks()
    unlocks.add(voice_id)
    _save_unlocks(unlocks)


def get_voice(voice_id):
    for v in _discover_voices():
        if v["id"] == voice_id:
            return v
    return None


def load_voice():
    """Return the active voice ID, falling back to the first unlocked voice."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            active = f.read().strip().lower()
    except Exception:
        active = ""
    voices = _discover_voices()
    unlocked = [v for v in voices if is_unlocked(v["id"])]
    if active and any(v["id"] == active for v in unlocked):
        return active
    if unlocked:
        return unlocked[0]["id"]
    if voices:
        return voices[0]["id"]
    return "joe"


def save_voice(voice_id):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(voice_id)


def list_voices():
    """Return all discovered voices with unlock status."""
    voices = _discover_voices()
    unlocks = _load_unlocks()
    for v in voices:
        v["unlocked"] = not v["locked"] or v["id"] in unlocks
    return voices


def _model_config_path(model_path):
    """Return the Piper model config JSON path, or None."""
    for ext in (".onnx.json", "_json"):
        candidate = model_path + ext if ext.startswith(".") else model_path + ext
        if os.path.exists(candidate):
            return candidate
    return None


def _make_spaced_config(base_config_path):
    """Create a temporary Piper config with slightly slower, more spaced speech."""
    try:
        with open(base_config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return base_config_path
    cfg.setdefault("inference", {})
    cfg["inference"]["length_scale"] = cfg["inference"].get("length_scale", 1.0) * 1.1
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="piper_cfg_")
    os.close(fd)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    return tmp_path


def _post_process_wav(input_path, output_path):
    """Reduce treble with a gentle low-pass filter and add slight sentence spacing."""
    try:
        rate, data = wavfile.read(input_path)
    except Exception:
        return
    if data.ndim > 1:
        data = data[:, 0]
    data = data.astype(np.float32)
    # Normalize
    peak = np.max(np.abs(data)) or 1.0
    data = data / peak
    # Gentle low-pass filter to take the edge off treble (cutoff ~8kHz on 22.05kHz)
    sos = signal.butter(4, 0.36, btype="low", output="sos")
    data = signal.sosfilt(sos, data)
    # Insert small silence at sentence pauses (detected by low-energy gaps)
    # Simpler: add a short trailing pad for breathing room
    silence = np.zeros(int(rate * 0.08), dtype=np.float32)
    data = np.concatenate([data, silence])
    # Restore volume
    data = data * peak
    data = np.clip(data, -1.0, 1.0)
    wavfile.write(output_path, rate, (data * 32767).astype(np.int16))


def speak(text, voice_id=None):
    voice_id = voice_id or load_voice()
    voice = get_voice(voice_id)
    if voice is None:
        # fallback: try legacy hardcoded Joe path
        voice = {
            "id": "joe",
            "model": os.path.join(VOICES_DIR, "joe", "en_US-joe-medium.onnx"),
        }
    model_path = voice["model"]
    base_config = _model_config_path(model_path)
    config_arg = []
    tmp_config = None
    if base_config:
        tmp_config = _make_spaced_config(base_config)
        config_arg = ["--config", tmp_config]
    subprocess.run(
        ["piper", "--model", model_path] + config_arg +
        ["--output_file", "/tmp/ai_controller_tts_raw.wav"],
        input=text.encode(), check=False,
        stdout=_DEVNULL, stderr=_DEVNULL
    )
    if tmp_config and os.path.exists(tmp_config):
        os.unlink(tmp_config)
    if os.path.exists("/tmp/ai_controller_tts_raw.wav"):
        _post_process_wav("/tmp/ai_controller_tts_raw.wav", "/tmp/ai_controller_tts.wav")
    subprocess.run(["mpv", "--no-video", "/tmp/ai_controller_tts.wav"],
                   check=False, stdout=_DEVNULL, stderr=_DEVNULL)


def toggle():
    voices = list_voices()
    unlocked = [v for v in voices if v["unlocked"]]
    if not unlocked:
        return None
    current = load_voice()
    ids = [v["id"] for v in unlocked]
    try:
        idx = ids.index(current)
    except ValueError:
        idx = -1
    next_voice = ids[(idx + 1) % len(ids)]
    save_voice(next_voice)
    return next_voice


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--speak":
        text = " ".join(sys.argv[2:]) or "Voice ready."
        speak(text)
    elif len(sys.argv) > 1 and sys.argv[1] == "--list":
        for v in list_voices():
            status = "UNLOCKED" if v["unlocked"] else "LOCKED"
            print(f"{v['id']}: {v['name']} [{status}]")
    elif len(sys.argv) > 2 and sys.argv[1] == "--unlock":
        unlock(sys.argv[2])
        print(f"Unlocked {sys.argv[2]}.")
    else:
        new_voice = toggle()
        if new_voice:
            print(new_voice)
            speak(f"Switched to {new_voice}.", voice_id=new_voice)
        else:
            print("No voices available.")
