import os
import time
import json
import subprocess
from collections import deque
from threading import Thread
from queue import Queue

# CONFIGURATION
MODEL_PATH = "/home/elijah/scripts/voices/en_US-lessac-medium.onnx"
QUEUE_FILE = "/tmp/voice_queue.json"
PAUSE_BETWEEN_SENTENCES = 0.5 # Seconds

class VoiceEngine:
    def __init__(self):
        self.queue = Queue()
        self.is_running = True
        self.worker_thread = Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def _process_queue(self):
        while self.is_running:
            try:
                text = self.queue.get(timeout=1)
                self._speak(text)
                time.sleep(PAUSE_BETWEEN_SENTENCES)
                self.queue.task_done()
            except:
                continue

    def _speak(self, text):
        if not text: return
        spoken = text[:500].split("\\n")[0]
        
        if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 0:
            try:
                p1 = subprocess.Popen(
                    ["piper", "-m", MODEL_PATH, "--output-raw"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                )
                p2 = subprocess.Popen(
                    ["paplay", "--raw", "--rate=22050", "--format=s16le", "--channels=1"],
                    stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                p1.stdin.write(spoken.encode())
                p1.stdin.close()
                p2.wait()
                return
            except Exception as e:
                print(f"Piper Error: {e}")

        subprocess.run(["spd-say", "-w", spoken], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def enqueue(self, text):
        self.queue.put(text)

    def clear(self):
        with self.queue.mutex:
            self.queue.queue.clear()

# This is a simple relay. Since we need the engine to be persistent,
# we'll run the engine as a background daemon.
if __name__ == "__main__":
    # This script is now called by the dispatcher to push to a daemon
    # To keep it simple for this iteration, we will implement the 
    # daemon as a separate service.
    pass
