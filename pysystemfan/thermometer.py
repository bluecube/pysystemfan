from . import config_params

import os
import collections

class Thermometer(config_params.Configurable):
    _params = [
        ("name", "", "Name that will appear in status output."),
        ("max_temperature", None, "Max temperature that we are allowed to reach."),
    ]

    def get_cached_temperature(self):
        """ Return temperature (in °C) measured by the thermometer during last update."""
        raise NotImplementedError()

    def get_cached_activity(self):
        """ Return activity value measured during the last update.
        Activity value is a number that should be a multiple of the power
        dissipated near this thermometer. """
        raise NotImplementedError()

    def get_status(self):
        """ Returns a dict with current cached status. """
        raise NotImplementedError()

    def update(self):
        """ Do any periodic tasks necessary, update cached temperature and activity """
        raise NotImplementedError()

class SystemThermometer(Thermometer, config_params.Configurable):
    _params = [
        ("path", None, "Path in /sys (typically /sys/class/hwmon/hwmon?/temp?_input) that has the temperature."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        self._cached_temperature = None
        self._cached_activity = None

    def get_temperature(self):
        with open(self.path, "r") as fp:
            return int(fp.readline()) / 1000

    def get_status(self):
        return collections.OrderedDict([
            ("name", self.name),
            ("temperature", self._cached_temperature)])

    def get_cached_temperature(self):
        return self._cached_temperature

    def get_cached_activity(self):
        return self._cached_activity

    def update(self):
        self._cached_temperature = self.get_temperature()
        self._cached_activity = os.getloadavg()[0]
