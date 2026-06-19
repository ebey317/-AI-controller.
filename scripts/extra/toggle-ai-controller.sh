#!/bin/bash
if pgrep -f "/home/elijah/scripts/ai_controller_mapper.py" > /dev/null; then
    echo "Stopping AI Controller Keyboard Mapper..."
    pkill -f "/home/elijah/scripts/ai_controller_mapper.py"
    echo "OFF"
else
    echo "Starting AI Controller Keyboard Mapper..."
    # Run as sudo if needed because uinput requires permission
    sudo python3 /home/elijah/scripts/ai_controller_mapper.py &
    echo "ON"
fi
