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
        LifxButton.long_press = None
        # LifxButton.sc_timer = sc_timer()
        LifxButton.lifx_group = None

        self.buttons = {}
        self.groups = {}
        
        self.hold_time = 400
        self.sc_threshold = 400

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
                self.sc_threshold = config['timing']['double_click']
            if 'hold_time' in config['timing']:
                self.hold_time = config['timing']['hold_time']

        for button_number, b_conf in config['buttons'].items():
            button = LifxButton(button_number, hold_time=self.hold_time)
            #button.when_held = held
            #button.when_released = released
            button.single_click = b_conf.get('single', None)
            button.double_click = b_conf.get('double', None)
            button.double_click = b_conf.get('double', None)
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


if __name__ == '__main__':
    switch = LifxSwitch()
