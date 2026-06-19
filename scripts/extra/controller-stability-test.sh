#!/usr/bin/env bash
# controller-stability-test.sh
# Run after plugging the Xbox controller in. Monitors /dev/input/js0 and
# kernel dmesg for 60 seconds, reports whether the connection stayed stable.
DUR=60
LOG=/tmp/controller_stability_$(date +%Y%m%d_%H%M%S).log
exec > >(tee "$LOG") 2>&1

echo "=== Controller stability test: ${DUR}s ==="
echo "Start: $(date)"
echo "Press Ctrl+C to stop early"

OK=0
FAIL=0
START_JS=$(ls /dev/input/js0 2>/dev/null)
(
  dmesg -w | grep -iE 'xbox|xone|045e|usb 5-1' &
  DMESG_PID=$!
  for ((i=0; i<DUR; i++)); do
      if ls /dev/input/js0 >/dev/null 2>&1; then
          ((OK++))
      else
          ((FAIL++))
      fi
      sleep 1
  done
  kill $DMESG_PID 2>/dev/null
)
END_JS=$(ls /dev/input/js0 2>/dev/null)
echo "End: $(date)"
echo "Seconds present: $OK / $DUR"
echo "Seconds absent:  $FAIL / $DUR"
echo "js0 start: ${START_JS:-missing}"
echo "js0 end:   ${END_JS:-missing}"
if [[ "$FAIL" -eq 0 && -n "$END_JS" ]]; then
    echo "RESULT: STABLE"
else
    echo "RESULT: UNSTABLE — try a different USB port/cable"
fi
echo "Log saved: $LOG"
