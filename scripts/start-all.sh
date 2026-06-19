#!/bin/bash
# Start the full AI Controller stack.
set -euo pipefail
systemctl --user start \
    antimicrox-autoload.service \
    voice-bridge.service \
    ptt-pynput.service \
    controller-legend.service \
    ai-slide-keyboard.service
echo "AI Controller started."
