#!/usr/bin/env python3
import subprocess
import sys

def inject_text(text):
    if not text:
        return
    # --clearmodifiers ensures that if the user is holding Shift/Ctrl for the trigger, 
    # it doesn't affect the typed text.
    subprocess.run(["xdotool", "type", "--clearmodifiers", text], check=False)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Join all arguments into a single string
        input_text = " ".join(sys.argv[1:])
        inject_text(input_text)
