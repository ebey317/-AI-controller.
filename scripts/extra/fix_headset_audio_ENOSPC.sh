#!/bin/bash
# Fix: Reload xone_gip_headset to clear ENOSPC audio buffer flood
# Run with: sudo bash /tmp/fix_headset_audio2.sh
set -e

echo "=== Reloading xone_gip_headset to clear ENOSPC flood ==="

# 1. Kill PulseAudio's hold on the device by suspending the source
echo "Suspending PulseAudio source..."
su - elijah -c "pactl suspend-source alsa_input.usb-Microsoft_Controller_3039373130383038333134313433-00.mono-fallback true" 2>/dev/null || true
su - elijah -c "pactl suspend-sink alsa_output.usb-Microsoft_Controller_3039373130383038333134313433-00.stereo-fallback true" 2>/dev/null || true
sleep 1

# 2. Set card profile to off (releases ALSA device)
echo "Setting card profile to off..."
su - elijah -c "pactl set-card-profile alsa_card.usb-Microsoft_Controller_3039373130383038333134313433-00 off" 2>/dev/null || true
sleep 2

# 3. Now remove the headset module
echo "Removing xone_gip_headset..."
modprobe -r xone_gip_headset
sleep 1

# 4. Reload it
echo "Loading xone_gip_headset..."
modprobe xone_gip_headset
sleep 2

# 5. Re-enable the card
echo "Re-enabling controller audio card..."
su - elijah -c "pactl set-card-profile alsa_card.usb-Microsoft_Controller_3039373130383038333134313433-00 output:analog-stereo+input:mono-fallback" 2>/dev/null || \
su - elijah -c "pactl set-card-profile alsa_card.usb-Microsoft_Controller_3039373130383038333134313433-00 pro-audio" 2>/dev/null || \
su - elijah -c "pactl set-card-profile alsa_card.usb-Microsoft_Controller_3039373130383038333134313433-00 output:analog-stereo;input:mono-fallback" 2>/dev/null || true
sleep 1

# 6. Unsuspend
su - elijah -c "pactl suspend-source alsa_input.usb-Microsoft_Controller_3039373130383038333134313433-00.mono-fallback false" 2>/dev/null || true
su - elijah -c "pactl suspend-sink alsa_output.usb-Microsoft_Controller_3039373130383038333134313433-00.stereo-fallback false" 2>/dev/null || true

# 7. Verify
echo ""
echo "=== Verification ==="
echo "Module loaded:"
lsmod | grep xone_gip_headset
echo ""
echo "ALSA capture device:"
arecord -l 2>/dev/null | grep -A2 "Headset"
echo ""
echo "Testing 2-second recording..."
su - elijah -c "timeout 2 parec --device=alsa_input.usb-Microsoft_Controller_3039373130383038333134313433-00.mono-fallback --rate=24000 --channels=1 --format=s16le > /tmp/fix_test.raw 2>/dev/null" || true
SIZE=$(stat -c%s /tmp/fix_test.raw 2>/dev/null || echo 0)
echo "Captured: ${SIZE} bytes (expected ~96000 for 2s at 24kHz mono)"
if [ "$SIZE" -gt 1000 ]; then
    echo "SUCCESS: Mic is capturing audio"
else
    echo "FAILED: Mic still not capturing — physically unplug and replug controller USB"
fi
rm -f /tmp/fix_test.raw

echo ""
echo "Done."