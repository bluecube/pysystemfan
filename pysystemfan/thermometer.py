from . import config_params
import os

class Thermometer(config_params.Configurable):
    _params = [
        ("name", "", "Name that wil appear in status output if present "
                     "If empty (the default), gets assigned based on path."),
        ("max_temperature", None, "Max temperature that we are allowed to reach."),
    ]

    def __init__(self):
        if not len(self.name):
            self.name = self.get_automatic_name()

    def get_automatic_name(self):
        """ Return automatic name determined from config parameters """
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

    def get_automatic_name(self):
        if not self.path.endswith("_input"):
            return self.path

        try:
            with open(self._path[:-len("input")] + "name", "r") as fp:
                return fp.read().strip()
        except:
            return self.path

    def update(self):
        return self.get_temperature(), os.getloadavg()[0]
