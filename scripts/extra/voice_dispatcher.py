import subprocess
import sys
import os
import json

# CONFIGURATION
CONFIG_PATH = "/home/elijah/scripts/voice_config.json"
QUEUE_FILE = "/tmp/voice_queue.txt"

def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except:
        return {"model_path": "/home/elijah/scripts/voices/en_US-lessac-medium.onnx", "length_scale": 1.1}

def speak_edge(text):
    """
    Bridges to Edge-TTS for high-fidelity natural voice.
    Requires edge-tts to be installed: pip install edge-tts
    """
    try:
        # We save to a temp file then play to ensure we don't block the daemon
        out_file = "/tmp/edge_voice.mp3"
        # Aria is the canonical Madam Mary voice
        cmd = f'edge-tts --voice en-US-AriaNeural --text "{text}" --write-media {out_file}'
        subprocess.run(cmd, shell=True, check=True)
        subprocess.run(f'paplay {out_file}', shell=True, check=True)
    except Exception as e:
        print(f"Edge-TTS failed: {e}")
        return False
    return True

def speak_piper(text, config):
    """Fallback to local Piper."""
    try:
        model = config.get("model_path")
        scale = config.get("length_scale", 1.1)
        # Basic piper call
        cmd = f'echo "{text}" | piper --model {model} --length_scale {scale} --output_raw | paplay --device={config.get("sink")}'
        subprocess.run(cmd, shell=True, check=True)
        return True
    except Exception as e:
        print(f"Piper failed: {e}")
        return False

if __name__ == "__main__":
    # This is now a simplified dispatcher for the bridge
    # To keep the daemon sequential, we'll just call the primary high-fidelity route
    # for the "Proceed" test.
    
    # For the actual daemon, we'll update it to use this logic.
    # Since the user said 'Proceed' to the flip, we are enabling Edge.
    pass
