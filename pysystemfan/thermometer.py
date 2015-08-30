from . import config_params
import os

import collections

class Thermometer(config_params.Configurable):
    _params = [
        ("name", "", "Name that will appear in status output."),
        ("max_temperature", None, "Max temperature that we are allowed to reach."),
    ]

    def __init__(self):
        if not len(self.name):
            self.name = self.get_automatic_name()

    def get_automatic_name(self):
        """ Return automatic name determined from config parameters """
        raise NotImplementedError()

    def get_status(self):
        raise NotImplementedError()

    def update(self):
        """ Returns tuple of current temperature and activity value, do any
        periodic tasks necessary. """
        raise NotImplementedError()

class SystemThermometer(Thermometer, config_params.Configurable):
    _params = [
        ("path", None, "Path in /sys (typically /sys/class/hwmon/hwmon?/temp?_input) that has the temperature."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        super().__init__()

    def get_temperature(self):
        with open(self.path, "r") as fp:
            return int(fp.readline()) / 1000

    def get_status(self):
        return collections.OrderedDict([
            ("name", self.name),
            ("temperature", self.get_temperature())])

    def update(self):
        return self.get_temperature(), os.getloadavg()[0]
