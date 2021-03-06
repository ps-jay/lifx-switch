"""
Provides physical switching of Lifx devices from a Raspberry Pi
"""

import argparse
import random

from threading import Thread, Timer
from time import time
from time import sleep

import lifxlan
import yaml

from gpiozero import Button as LifxButton

class Discovery(Thread):
    """An endless thread that discovers Lifx devices"""
    def __init__(self, name, groups):
        Thread.__init__(self)
        self.name = name
        self.lifx = lifxlan.LifxLAN()
        self.groups = groups

    def run(self):
        print("DEBUG: starting discovery thread")
        sleep_time = 5
        devices_max = 0
        while True:  # pylint: disable=too-many-nested-blocks
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
                if len(devices) > devices_max:
                    devices_max = len(devices)
                elif devices and len(devices) == devices_max:
                    # increase sleep until max sleep of 15 minutes
                    if sleep_time < (15 * 60):
                        sleep_time = sleep_time + 5

            except lifxlan.errors.WorkflowException:
                print("WARN: WorkflowException on discovery")

            sleep(sleep_time)

class LifxSwitch():
    """Provides the main logic of switching Lifx devices from a Raspberry Pi"""
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
        LifxButton.scenes = None
        LifxButton.sc_timer = None
        LifxButton.lifx_group = None

        self.buttons = {}
        self.groups = {}

        self.hold_time = 0.400
        self.sc_threshold = 0.400
        self.transition_time = 0.400 * 1000

        self.parse_config(self.args.config_file)

        self.discovery_thread = Discovery('lifx_discovery', self.groups)
        self.discovery_thread.start()

    def parse_args(self):
        """Parse the arguments to the program"""
        parser = argparse.ArgumentParser()
        parser.add_argument('--config-file', '-c', required=True)
        self.args = parser.parse_args()

    def parse_config(self, config_file):
        """
        Parse the configuration file

        XXX: This could be much better
        """
        config = None
        with open(config_file, 'rb') as fh:  # pylint: disable=invalid-name
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
            button.long_click = b_conf.get('long', None)
            button.scenes = b_conf['scenes']
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

    def toggle_power(self, button, group):
        """Toggle the power status of the given group of devices"""
        power = None
        for device in group.devices:
            try:
                power = device.get_power()
            except lifxlan.errors.WorkflowException:
                print(f"INFO: WorkflowException on get_power for button {button.pin.number}")
            if power is not None:
                break
        if power is None:
            print(f"WARN: no devices replied to get_power for button {button.pin.number}")
            return
        group.set_power(not power, self.transition_time, True)
        print(f"DEBUG: toggled power {not power}")

    def reset_or_boost(self, button, group):
        """Reset the devices to the default scene, or to the "boost" scene if already on the default"""
        color = None
        for device in group.devices:
            try:
                color = device.get_color()
            except lifxlan.errors.WorkflowException:
                print(f"INFO: WorkflowException on get_color for button {button.pin.number}")
            if color is not None:
                break
        if color is None:
            print(f"WARN: no devices replied to get_color for button {button.pin.number}")
            return
        if (color[2] == button.scenes['default'][2]) and (color[3] == button.scenes['default'][3]):
            group.set_color(button.scenes['boost'], self.transition_time, True)
            print(f"DEBUG: {button.pin.number} was default, now boosted")
        else:
            # is something non-default, now back to default
            group.set_color(button.scenes['default'], self.transition_time, True)
            print(f"DEBUG: {button.pin.number} restored to default")

        group.set_power('on', self.transition_time, True)

    def dim_cycle_plus_colourful(self, button, group):
        """
        Progressively dim the devices in the group, or set them to random colours if fully dimmed
        Resets to the default scene if none of the dim scenes are detected
        """
        color = None
        for device in group.devices:
            try:
                color = device.get_color()
            except lifxlan.errors.WorkflowException:
                print(f"INFO: WorkflowException on get_color for button {button.pin.number}")
            if color is not None:
                break
        if color is None:
            print(f"WARN: no devices replied to get_color for button {button.pin.number}")
            return
        if (color[2] == button.scenes['default'][2]) and (color[3] == button.scenes['default'][3]):
            group.set_color(button.scenes['dim'], self.transition_time, True)
            print(f"DEBUG: {button.pin.number} was default, now dim")
        elif (color[2] == button.scenes['dim'][2]) and (color[3] == button.scenes['dim'][3]):
            group.set_color(button.scenes['dimmer'], self.transition_time, True)
            print(f"DEBUG: {button.pin.number} was dim, now dimmer")
        elif (color[2] == button.scenes['dimmer'][2]) and (color[3] == button.scenes['dimmer'][3]):
            group.set_color(button.scenes['dimmest'], self.transition_time, True)
            print(f"DEBUG: {button.pin.number} was dimmer, now dimmest")
        elif (color[2] == button.scenes['dimmest'][2]) and (color[3] == button.scenes['dimmest'][3]):
            # multi-threaded color change
            threads = []
            for device in group.devices:
                color = [random.randint(0, 65535), 49151, 49151, 3500]
                thread = Thread(target=device.set_color, args=[color, self.transition_time, True])
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()
            print(f"DEBUG: {button.pin.number} was dimmest, now colourful")
        else:
            group.set_color(button.scenes['default'], self.transition_time, True)
            print(f"DEBUG: {button.pin.number} is now back to default")

        group.set_power('on', self.transition_time, True)

    def get_sc_timer(self, button):
        """Returns a timer to use with single/double click detection"""
        return Timer(self.sc_threshold, self.single_click, args=[button])

    def single_click(self, button):
        """Executes the single click function of the button"""
        print(f"INFO: single click detected on button {button.pin.number}")
        # provide timer for next single click
        button.sc_timer = self.get_sc_timer(button)
        group = button.lifx_group['group']
        if group and group.devices:
            getattr(self, button.single_click)(button, group)

    @staticmethod
    def sc_detection(button):
        """Starts the timer to see if this is a single click"""
        if not button.sc_timer.is_alive():
            print("DEBUG: starting single/double click timer")
            button.sc_timer.start()

    def double_click(self, button):
        """Executes the double click function of the button"""
        print(f"INFO: double click detected on button {button.pin.number}")
        button.sc_timer.cancel()
        # provide timer for next single click
        button.sc_timer = self.get_sc_timer(button)
        if button.double_click:
            group = button.lifx_group['group']
            if group and group.devices:
                getattr(self, button.double_click)(button, group)

    def long_press(self, button):
        """Executes the long press function of the button"""
        group = button.lifx_group['group']
        if group and group.devices:
            getattr(self, button.long_click)(button, group)

    def click(self, button):
        """Receives a click event (from button released event)"""
        if (time() - button.last_release) < self.sc_threshold:
            self.double_click(button)
        else:
            self.sc_detection(button)

    def held(self, button):
        """Receives a button held event"""
        print(f"DEBUG: {button.pin.number} is being held")
        button.was_held = True
        self.long_press(button)

    def released(self, button):
        """Receives a button released event"""
        if button.was_held:
            print(f"DEBUG: {button.pin.number} has been released")
        else:
            print(f"DEBUG: {button.pin.number} has been clicked")
            self.click(button)

        button.was_held = False
        button.last_release = time()


if __name__ == '__main__':
    switch = LifxSwitch()

    # Note: if the discovery thread exits, the program will exit
