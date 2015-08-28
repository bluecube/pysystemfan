from . import config_params

class Fan(config_params.Configurable):
    _params = [
        ("pwm_path", None, "Path in (typically /sys/class/hwmon/hwmon?/pwm?) that is used to set fan pwm setting"),
        ("rpm_path", None, "Path in (typically /sys/class/hwmon/hwmon?/fan?_input) that is used to set rpm"),

        ("name", "", "Name that wil appear in status output if present "
                     "If empty (the default), gets assigned based on path."),
        ("min_pwm", 80, "Minimal allowed nonzero PWM value. Below this the fan will stop in normal mode, or stay on minimum in settle mode."),
        ("spinup_pwm", 128, "PWM value to spin the fan up."),
        ("spinup_time", 1, "How long the spinup_pwm will be applied (seconds)."),
    ]

    def __init__(self, parent, **params):
        self.process_params(**params)
        self.update_time = parent.update_time

        if not len(self.name):
            self.name = self.get_automatic_name()

        self._running = self.get_rpm() > 0

    def get_automatic_name(self):
        return self.rpm_path # TODO

    def spinup(self):
        self.set_pwm(self.spinup_pwm)
        yield self.spinup_time
        self._state = self.SETTLE
        self._settle_remaining = self.settle_update_count

    def stop(self):
        self.set_pwm(0)
        self._state = self.STOPPED

    def get_rpm(self):
        with open(self.rpm_path, "r") as fp:
            return int(fp.readline())

    def set_pwm(self, value):
        with open(self.pwm_path, "w") as fp:
            print(str(value), file=fp)
