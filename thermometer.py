from . import config_params

class Thermometer(config_params.Configurable):
    _params = [
        ("name", "", "Optional name that wil appear in status output if present"),
        ("max_temperature", None, "Max temperature that we are allowed to reach."),
    ]


class SystemThermometer(config_params.Configurable, Thermometer):
    _params = [
        ("path", None, "Path in /sys (typically /sys/class/hwmon/hwmon?/temp?_input) that has the temperature."),

        ("kP", 20, "Proportional constant of the controler."),
        ("kI", 10, "Integration constant of the controller."),
        ("kD", 20, "Derivation constant of the controller."),

        ("derivative_smoothing_window", 300, "Number of seconds to use as a smoothing window for derivative term. This gets rounded to a nearest whole number of updates.")
    ]

    def __init__(self, fan, **params):
        _process_params(self, params)

        self._anti_windup = 300 / self.kI

        self._last_temperature = collections.deque([self.get_temperature()], round(self.derivative_smoothing_window / fan._sleep_time) + 1)
        self._integral = fan.min_pwm / self.kI

    def get_temperature(self):
        if self.path.startswith(self._smartctl_prefix):
            return self._get_smartctl_temperature(self.path[len(self._smartctl_prefix):])
        else:
            with open(self.rpm_path, "r") as fp:
                return int(fp.readline())

    def get_activity(self):
        return self.getloadavg()[0]

    def config(self):
        return _dump_params(self)
