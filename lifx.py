from gpiozero import Button
from signal import pause
from lifxlan import LifxLAN

def bon():
    print("Switching on")
    kitchen.set_power("on")

def boff():
    print("Switching off")
    kitchen.set_power("off")

button = Button(4)
button.when_pressed = bon
button.when_released = boff

lifx = LifxLAN()
# TODO: periodically repeat this discovery
kitchen = lifx.get_devices_by_group("Kitchen")
print("Found %s kitchen lights" % len(kitchen.devices))

print("Button is currently %s" % button.is_active)

state = "off"
if button.is_active:
    state = "on"
print("Ensuring lights are %s" % state)
kitchen.set_power(state)

print("Awaiting events")
pause()
