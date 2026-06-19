#!/usr/bin/env python3
"""
Toggle the active AI controller TTS voice between Joe (local Piper)
and Aria (Edge TTS online). State is stored in ~/.config/ai_controller_voice.
Can be triggered from the keyboard, a controller button, or the command line.
"""
import os
import subprocess
import sys

STATE_FILE = os.path.expanduser("~/.config/ai_controller_voice")
VOICES = ["joe", "aria"]


def load_voice():
    try:
        v = open(STATE_FILE).read().strip().lower()
        return v if v in VOICES else VOICES[0]
    except Exception:
        return VOICES[0]


def save_voice(voice):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(voice)


def toggle():
    current = load_voice()
    idx = VOICES.index(current)
    next_voice = VOICES[(idx + 1) % len(VOICES)]
    save_voice(next_voice)
    return next_voice


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def speak(text, voice=None):
    voice = voice or load_voice()
    if voice == "joe":
        model_path = os.path.join(SCRIPT_DIR, "voices", "joe", "en_US-joe-medium.onnx")
        subprocess.run(
            ["piper", "--model", model_path,
             "--output_file", "/tmp/ai_controller_tts.wav"],
            input=text.encode(), check=False
        )
        subprocess.run(["mpv", "--no-video", "/tmp/ai_controller_tts.wav"], check=False)
    else:
        subprocess.run(
            ["edge-tts", "--voice", "en-US-AriaNeural",
             "--pitch=-22Hz", "--rate=+12%",
             "--text", text, "--write-media", "/tmp/ai_controller_tts.mp3"],
            check=False
        )
        subprocess.run(["mpv", "--no-video", "/tmp/ai_controller_tts.mp3"], check=False)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--speak":
        text = " ".join(sys.argv[2:]) or "Voice ready."
        speak(text)
    else:
        new_voice = toggle()
        print(new_voice)
        speak(f"Switched to {new_voice}.", voice=new_voice)
