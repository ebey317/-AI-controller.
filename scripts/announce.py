#!/usr/bin/env python3
"""
announce.py — Voice feedback for AI controller slash commands and state changes.
Speaks the given text using the currently selected voice (Joe/Aria).
"""
import sys
sys.path.insert(0, "/home/elijah/scripts")
from voice_toggle import speak

if __name__ == "__main__":
    text = " ".join(sys.argv[1:]).strip() or "Command activated."
    speak(text)
