
import evdev
from evdev import UInput, KeyEvent
import sys
import os

# TARGET MAPPINGS
# Xbox Controller Standard:
# RT = Axis 5 (value 0-255)
# F13 = keycode 202 (derived from controller-detect.sh)

F13_KEYCODE = 202 

def run_mapper():
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    controller = None
    
    for device in devices:
        if "Xbox" in device.name or "Microsoft" in device.name:
            controller = device
            break
    
    if not controller:
        print("Error: No Xbox controller found.")
        sys.exit(1)
        
    print(f"Control mapping active on: {controller.name}")
    
    # Create UInput device simulating a keyboard
    ui = UInput()
    
    try:
        # Track the state of the trigger to avoid spamming key-down events
        rt_pressed = False
        
        for event in controller.read_loop():
            if event.type == evdev.ecodes.EV_ABS:
                # RT Axis is typically code 5
                if event.code == 5:
                    if event.value > 128 and not rt_pressed:
                        # Send Key Down
                        ui.write(evdev.ecodes.EV_KEY, F13_KEYCODE, 1)
                        ui.syn()
                        rt_pressed = True
                    elif event.value <= 128 and rt_pressed:
                        # Send Key Up
                        ui.write(evdev.ecodes.EV_KEY, F13_KEYCODE, 0)
                        ui.syn()
                        rt_pressed = False
            
            elif event.type == evdev.ecodes.EV_KEY:
                # PROTECT LOGO BUTTON: Ignore codes 13/14
                if event.code == 13 or event.code == 14:
                    continue
                
    except KeyboardInterrupt:
        print("\nStopping AI Controller Mapper...")
    finally:
        ui.close()

if __name__ == "__main__":
    run_mapper()
