from threading import Thread, Timer

from time import time
from time import sleep

from gpiozero import Button
from signal import pause
from lifxlan import LifxLAN, errors

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
                try:
                    g = lifx.get_devices_by_group(group)
                    print("Found %s %s lights" % (len(g.devices), group))
                    groups[group] = g
                    sleep(15)
                except errors.WorkflowException:
                    print("EXCEPTION!")

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
        group.set_color([32767, 0, 50000, 3000], 667)
        group.set_power('on')

def sc_timer():
    return Timer(0.35, single_click)

Button.was_held = False
Button.last_release = 0
Button.dim_down = True
Button.brightness = None
Button.sc_timer = sc_timer()

def held(button):
    try:
        print(time())
        group = groups[button_group_map[button.pin.number]]
        if not button.was_held:
            print("button is being held")
            if group and group.devices:
                if not group.devices[0].get_power():
                    group.set_brightness(1)
                    group.set_power('on', 500, True)
                    button.dim_down = False
                button.brightness = group.devices[0].get_color()[2]
        else:
            print("button still held")

        if group and group.devices:
            if button.dim_down:
                button.brightness = button.brightness - 16384
                if button.brightness < 1:
                    button.brightness = 1
            else:
                button.brightness = button.brightness + 16384
                if button.brightness > 65535:
                    button.brightness = 65535
            group.set_brightness(button.brightness, 1000, True)
            print("Set brightness %s" % button.brightness)

        button.was_held = True
    except errors.WorkflowException:
        print("EXCEPTION!")

def released(button):
    if not button.was_held:
        pressed()
    else:
        button.dim_down = not button.dim_down

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
