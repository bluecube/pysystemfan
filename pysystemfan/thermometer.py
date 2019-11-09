from . import config_params

import os
import collections
import logging

logger = logging.getLogger(__name__)

class Thermometer(config_params.Configurable):
    _params = [
        ("name", "", "Name that will appear in status output."),
        ("target_temperature", None, "We're trying to keep temperature below this value."),
        ("temperature_scale", 1, "Temperature difference gets divided by this value before it is used for determining the fan speed."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        self.update(None)

    def get_normalized_temperature_error(self):
        return (self.get_cached_temperature() - self.target_temperature) / self.temperature_scale

    def get_cached_temperature(self):
        """ Return temperature (in °C) measured by the thermometer during last update."""
        raise NotImplementedError()

    def get_cached_activity(self):
        """ Return activity value measured during the last update.
        Activity value is a number that should be a multiple of the power
        dissipated near this thermometer. """
        raise NotImplementedError()

    def update(self, dt):
        """ Do any periodic tasks necessary, update cached temperature and activity.
        dt is time since the last update. """
        raise NotImplementedError()

class SystemThermometer(Thermometer, config_params.Configurable):
    _params = [
        ("path", None, "Path in /sys (typically /sys/class/hwmon/hwmon?/temp?_input) that has the temperature."),
    ]

    def __init__(self, parent, params):
        super().__init__(parent, params)
        self._cached_temperature = None
        self._cached_activity = None

    def get_temperature(self):
        with open(self.path, "r") as fp:
            return int(fp.readline()) / 1000

    def get_cached_temperature(self):
        return self._cached_temperature

    def get_cached_activity(self):
        return self._cached_activity

    def update(self, dt):
        self._cached_temperature = self.get_temperature()
        self._cached_activity = os.getloadavg()[0]

        logger.debug("Thermometer {} {}°C (target {}°C)".format(self.name, self._cached_temperature, self.target_temperature))

        return {"type": self.__class__.__name__,
                "temperature": self._cached_temperature,
                "target_temperature": self.target_temperature}

class MockThermometer(Thermometer, config_params.Configurable):
    _params = [
        ("value", 30, "Temperature shown."),
        ("activity", 0.5, "Activity shown."),
    ]

    def get_temperature(self):
        return self.value

    def get_cached_temperature(self):
        return self.value

    def get_cached_activity(self):
        return self.activity

    def update(self, dt):
        return {"type": self.__class__.__name__,
                "temperature": self.value,
                "target_temperature": self.target_temperature}
