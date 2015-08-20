import config_params
import thermometer

class Fan(config_params.Configurable):
    _params = [
        ("pwm_path", None, "Path in (typically /sys/class/hwmon/hwmon?/pwm?) that is used to set fan pwm setting"),
        ("rpm_path", None, "Path in (typically /sys/class/hwmon/hwmon?/fan?_input) that is used to set rpm"),

        ("name", "", "Optional name that wil appear in status output if present"),
        ("min_pwm", 80, "Minimal allowed nonzero PWM value. Below this the fan will stop in normal mode, or stay on minimum in settle mode."),
        ("spinup_pwm", 128, "PWM value to spin the fan up."),
        ("spinup_time", 1, "How long the spinup_pwm will be applied (seconds)."),

        ("thermometers", config_params.ListOf(thermometer.Thermometer), "List of thermometers controling this fan")
    ]

    def __init__(self, parent, **params):
        self.process_params(**params)
        self.update_time = parent.update_time

        self._running = self.get_rpm() > 0

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

    def update_loop(self):
        while True:
            for thermometer in self.thermometers:
                thermometer.update_temperature()
            if self._state == self.STOPPED:
                if any(thermometer.need_fan() for thermometer in self.thermometers):
                    yield from self.spinup()
                else:
                    yield self._sleep_time
            else:
                if self._state == self.SETTLE:
                    if self._settle_remaining <= 0:
                        self._state = self.RUNNING
                    else:
                        self._settle_remaining -= 1

                pwm = max(thermometer.requiered_fan_pwm() for thermometer in self.thermometers)
                if pwm < self.min_pwm:
                    if self._state != self.SETTLE and not any(thermometer.need_fan() for thermometer in self.thermometers):
                        self.stop()
                    else:
                        self.set_pwm(self.min_pwm)
                elif pwm > 255:
                    self.set_pwm(255)
                else:
                    self.set_pwm(round(pwm))

                yield self._sleep_time

    def calibrate():
        raise NotImplementedError();

    def status(self):
        ret = {
            "rpm": self.get_rpm(),
            "thermometers": [thermometer.status() for thermometer in self.thermometers],
            "_state": {self.RUNNING: "running", self.SETTLE: "settle", self.STOPPED: "stopped"}[self._state]
        }
        if self.name:
            ret["name"] = self.name
        return ret

    def config(self):
        ret = _dump_params(self)
        ret["thermometers"] = [thermometer.config() for thermometer in self.thermometers]
        return ret

    def __iter__(self):
        return (time.time() + sleep_time for sleep_time in self.update_loop())

