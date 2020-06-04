from threading import Thread, Timer

from time import time
from time import sleep

from gpiozero import Button
from signal import pause
from lifxlan import LifxLAN

lifx = LifxLAN()

groups = {
    'Kitchen': None
}

button_group_map = {
    4: 'Kitchen'
}

class Discovery(Thread):
    def __init__(self, name):
        Thread.__init__(self)
        self.name = name

    def run(self):
        global groups
        while True:
            for group in groups:
                g = lifx.get_devices_by_group(group)
                print("Found %s %s lights" % (len(g.devices), group))
                groups[group] = g
                sleep(15)

discovery = Discovery("discovery")
discovery.start()

def single_click():
    button.sc_timer = sc_timer()
    print("single click %s - power toggle" % button.pin.number)
    group = groups[button_group_map[button.pin.number]]
    if group and group.devices:
        power = group.devices[0].get_power()
        if power:
            group.set_power('off')
        else:
            group.set_power('on')

def double_click():
    button.sc_timer.cancel()
    button.sc_timer = sc_timer()
    print("double click %s - reset scene" % button.pin.number)
    group = groups[button_group_map[button.pin.number]]
    if group and group.devices:
        group.set_color([32767, 0, 50000, 3000])
        group.set_power('on')

def sc_timer():
    return Timer(0.35, single_click)

Button.was_held = False
Button.last_release = 0
Button.sc_timer = sc_timer()

def held(button):
    button.was_held = True
    print("button was held not just pressed")

def released(button):
    if not button.was_held:
        pressed()
    button.was_held = False
    button.last_release = time()

def pressed():
    if (time() - button.last_release) < 0.35:
        double_click()
    else:
        if not button.sc_timer.is_alive():
            print("potential single click")
            button.sc_timer.start()

button = Button(4, hold_time=0.35, hold_repeat=True)

button.when_held = held
button.when_released = released

print("Awaiting events")
pause()
