import argparse

import lifxlan
import yaml

from threading import Thread, Timer
from signal import pause
from time import time
from time import sleep

from gpiozero import Button as LifxButton

class Discovery(Thread):
    def __init__(self, name, groups):
        Thread.__init__(self)
        self.name = name
        self.lifx = lifxlan.LifxLAN()
        self.groups = groups

    def run(self):
        print("DEBUG: starting discovery thread")
        while True:
            try:
                devices = self.lifx.get_devices()
                print(f"DEBUG: found {len(devices)} Lifx devices")
                for device in devices:
                    grp = device.get_group()
                    if grp:
                        grp = grp.lower()
                    if grp in self.groups:
                        found = False
                        for light in self.groups[grp].devices:
                            if device.get_mac_addr() == light.get_mac_addr():
                                found = True
                        if not found:
                            self.groups[grp].add_device(device)
                            print(f"INFO: {device.get_label()} added to group {grp}")
            except lifxlan.errors.WorkflowException:
                print("WARN: WorkflowException on discovery")
            sleep(15)

class LifxSwitch():
    def __init__(self, args=None):
        self.args = args
        if not self.args:
            self.parse_args()
        if not self.args:
            raise RuntimeError('Args not provided')

        LifxButton.last_release = 0
        LifxButton.was_held = False
        LifxButton.single_click = None
        LifxButton.double_click = None
        LifxButton.long_click = None
        LifxButton.sc_timer = None
        LifxButton.lifx_group = None

        self.buttons = {}
        self.groups = {}
        
        self.hold_time = 0.400
        self.sc_threshold = 0.400

        self.parse_config(self.args.config_file)

        self.discovery_thread = Discovery('lifx_discovery', self.groups)
        self.discovery_thread.start()

    def parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--config-file', '-c', required=True)
        self.args = parser.parse_args()

    def parse_config(self, config_file):
        config = None
        with open(config_file, 'rb') as fh:
            config = yaml.safe_load(fh)

        if 'timing' in config:
            if 'double_click' in config['timing']:
                self.sc_threshold = config['timing']['double_click'] / 1000
            if 'hold_time' in config['timing']:
                self.hold_time = config['timing']['hold_time'] / 1000

        for button_number, b_conf in config['buttons'].items():
            button = LifxButton(button_number, hold_time=self.hold_time)
            button.when_held = self.held
            button.when_released = self.released
            button.single_click = b_conf.get('single', None)
            button.double_click = b_conf.get('double', None)
            button.long_click = b_conf.get('hold', None)
            button.sc_timer = self.get_sc_timer(button)
            self.buttons[button_number] = button

            group_name = b_conf['group'].lower()
            group = self.groups.get(group_name, None)
            if not group:
                group = lifxlan.Group()
                self.groups[group_name] = group

            button.lifx_group = {
                'name': group_name,
                'group': group,
            }

    def toggle_power(self, button):
        group = button.lifx_group['group']
        if group and group.devices:
            power = group.devices[0].get_power()
            group.set_power(not power)

    def get_sc_timer(self, button):
            return Timer(self.sc_threshold, self.single_click, args=[button])

    def single_click(self, button):
        print(f"INFO: single click detected on button {button.pin.number}")
        # provide timer for next single click
        button.sc_timer = self.get_sc_timer(button)
        getattr(self, button.single_click)(button)

    def sc_detection(self, button):
        if not button.sc_timer.is_alive():
            print("DEBUG: starting single/double click timer")
            button.sc_timer.start()

    def double_click(self, button):
        print(f"INFO: double click detected on button {button.pin.number}")
        if button.double_click:
            getattr(self, button.double_click)()

    def long_press(self, button):
        pass

    def click(self, button):
        if (time() - button.last_release) < self.sc_threshold:
            self.double_click(button)
        else:
            self.sc_detection(button)

    def held(self, button):
        print(f"DEBUG: {button.pin.number} is being held")
        button.was_held = True

    def released(self, button):
        if button.was_held:
            print(f"DEBUG: {button.pin.number} has been released")
        else:
            print(f"DEBUG: {button.pin.number} has been clicked")
            self.click(button)

        button.was_held = False
        button.last_release = time()


if __name__ == '__main__':
    switch = LifxSwitch()
