import subprocess
import os
import time
import json

CONFIG_PATH = "/home/elijah/scripts/voice_config.json"
QUEUE_FILE = "/tmp/voice_queue.txt"

def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except:
        return {"model_path": "/home/elijah/scripts/voices/en_US-lessac-medium.onnx", "length_scale": 1.1, "sink": "alsa_output.pci-0000_28_00.4.analog-stereo"}

def execute_tts(text):
    config = load_config()
    out_file = "/tmp/sovereign_voice.mp3"
    sink = config.get("sink", "alsa_output.pci-0000_28_00.4.analog-stereo")
    try:
        # HIGH FIDELITY ROUTE (Edge) — LOCKED PARAMS (tuned 2026-06-17)
        pitch = config.get("edge_pitch", "-22Hz")
        rate = config.get("edge_rate", "+4%")
        voice = config.get("edge_voice", "en-US-AriaNeural")
        cmd = f'edge-tts --voice {voice} --pitch={pitch} --rate={rate} --text "{text}" --write-media {out_file}'
        subprocess.run(cmd, shell=True, check=True)
        # USE MPV instead of paplay
        subprocess.run(f'mpv --no-video --audio-device={sink} {out_file}', shell=True, check=True)
        return True
    except Exception as e:
        print(f"Edge failed: {e}. Falling back to Piper.")
        try:
            # LOCAL FALLBACK (Piper)
            model = config.get("model_path")
            scale = config.get("length_scale", 1.1)
            # PIPE directly into mpv
            cmd = f'echo "{text}" | piper --model {model} --length_scale {scale} --output_raw | mpv --no-video --audio-device={sink} -'
            subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e2:
            print(f"Piper also failed: {e2}")
            return False

if __name__ == "__main__":
    if os.path.exists(QUEUE_FILE):
        open(QUEUE_FILE, 'w').close()

    while True:
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, 'r+') as f:
                lines = f.readlines()
                if lines:
                    text = lines[0].strip()
                    f.seek(0)
                    f.truncate()
                    f.writelines(lines[1:])
                    if text:
                        execute_tts(text)
        time.sleep(0.5)
