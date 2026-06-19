#!/usr/bin/env bash
# controller_audio_toggle.sh
# Toggle default audio output/input between Xbox controller headset jack
# and the next-best sink (PC speakers/HDMI).

CONTROLLER_SINK=$(pactl list sinks short | awk '/Microsoft_Controller.*stereo-fallback/{print $2}' | head -1)
CONTROLLER_SOURCE=$(pactl list sources short | awk '/Microsoft_Controller.*mono-fallback/{print $2}' | head -1)
PC_SINK=$(pactl list sinks short | awk '!/Microsoft_Controller/{print $2}' | head -1)
PC_SOURCE=$(pactl list sources short | awk '/analog-stereo\.monitor/{next} !/Microsoft_Controller/ && /analog-stereo$/{print $2}' | head -1)

CURRENT_SINK=$(pactl info | awk -F': ' '/Default Sink/{print $2}')

if [[ -z "$CONTROLLER_SINK" ]]; then
    notify-send -t 3000 "🎮 Controller audio" "Xbox controller headset not found"
    echo "Controller headset sink not found. Is the controller plugged in?"
    exit 1
fi

if [[ "$CURRENT_SINK" == "$CONTROLLER_SINK" ]]; then
    # Switch to PC audio
    if [[ -n "$PC_SINK" ]]; then
        pactl set-default-sink "$PC_SINK"
        notify-send -t 2000 "🔊 PC audio" "Default output switched to PC speakers"
        echo "Switched default output to $PC_SINK"
    fi
    if [[ -n "$PC_SOURCE" ]]; then
        pactl set-default-source "$PC_SOURCE"
        echo "Switched default input to $PC_SOURCE"
    fi
else
    # Switch to controller headset
    pactl set-default-sink "$CONTROLLER_SINK"
    pactl set-sink-volume "$CONTROLLER_SINK" 95%
    notify-send -t 2000 "🎮 Controller audio" "Default output switched to controller headset"
    echo "Switched default output to $CONTROLLER_SINK"
    if [[ -n "$CONTROLLER_SOURCE" ]]; then
        pactl set-default-source "$CONTROLLER_SOURCE"
        pactl set-source-volume "$CONTROLLER_SOURCE" 76%
        echo "Switched default input to $CONTROLLER_SOURCE"
    fi
fi
