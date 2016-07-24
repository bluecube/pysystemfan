from . import config_params
from . import thermometer
from . import harddrive
from . import util

import collections
import logging

logger = logging.getLogger(__name__)

class Fan(config_params.Configurable):
    _params = [
        ("name", None, "Name that will appear in status output."),
        ("min_pwm", 80, "Minimal allowed nonzero PWM value. Below this the fan will stop in normal mode, or stay on minimum in settle mode."),
        ("min_settle_time", 30, "Number of seconds at minimum pwm before stopping the fan"),
        ("pid", config_params.InstanceOf([util.Pid], Exception), "PID controller for this fan"),
        ("thermometers", config_params.ListOf([thermometer.SystemThermometer,
                                               harddrive.Harddrive,
                                               thermometer.MockThermometer]), ""),
    ]

    def __init__(self, parent, params):
        self.process_params(params)

        self._state = "running"
        self._settle_timer = util.TimeoutHelper(self.min_settle_time)
        self.set_pwm(255)

    def get_rpm(self):
        raise NotImplementedError()

    def set_pwm(self, pwm):
        raise NotImplementedError()

    def _set_pwm_checked(self, pwm):
        #TODO: Avoid setting pwm if it has not changed
        if pwm < self.min_pwm and pwm != 0:
            pwm = int(self.min_pwm)
        elif pwm > 255:
            pwm = 255
        else:
            pwm = int(pwm)

        logger.debug("Setting {} to {}".format(self.name, pwm))
        self.set_pwm(pwm)

    def _change_state(self, state):
        self._state = state
        logger.info("Changing state of {} to {}".format(self.name, state))

    def update(self, dt):
        for thermometer in self.thermometers:
            thermometer.update(dt)

        normalized_temperature_error = max(t.get_normalized_temperature_error()
                                           for t in self.thermometers)

        if self._state == "running":
            pwm = self.pid.update(normalized_temperature_error)
            self._set_pwm_checked(pwm)
            if pwm < self.min_pwm:
                self._settle_timer.reset()
                self._change_state("settle")
                logger.debug("Settle time for {} is {}s".format(self.name, self._settle_timer.limit))

        elif self._state == "settle":
            pwm = self.pid.update(normalized_temperature_error)

            if pwm < self.min_pwm:
                # No need to set pwm, it is already at minimum
                if self._settle_timer(dt):
                    #TODO: Don't switch to stopped if error > 0
                    self._set_pwm_checked(0)
                    self._settle_timer.limit *= 2
                    self._change_state("stopped")
            else:
                self._set_pwm_checked(pwm)
                self._change_state("running")

        elif self._state == "stopped":
            if normalized_temperature_error > 0:
                self.pid.reset()
                pwm = self.pid.update(normalized_temperature_error)
                self._set_pwm_checked(pwm)
                self._change_state("running")
            else:
                self._settle_timer.limit = max(self._settle_timer.limit - dt,
                                               self.min_settle_time)

        else:
            raise Exception("Unknown state " + self._state)

class SystemFan(Fan, config_params.Configurable):
    _params = [
        ("pwm_path", None, "Path in (typically /sys/class/hwmon/hwmon?/pwm?) that is used to set fan pwm setting"),
        ("rpm_path", None, "Path in (typically /sys/class/hwmon/hwmon?/fan?_input) that is used to set rpm"),
    ]

    def __init__(self, parent, params):
        super().__init__(parent, params)

        if not len(self.name):
            self.name = self.get_automatic_name()

    def get_rpm(self):
        with open(self.rpm_path, "r") as fp:
            return int(fp.readline())

    def set_pwm(self, value):
        with open(self.pwm_path, "w") as fp:
            print(str(value), file=fp)

    def get_status(self):
        return collections.OrderedDict([
            ("name", self.name),
            ("rpm", self.get_rpm())])

class MockFan(Fan, config_params.Configurable):
    _params = [
        ("name", None, "Name that will appear in status output."),
        ("rpm", 1234, "RPM shown."),
    ]

    def get_rpm(self):
        return self.rpm

    def set_pwm(self, value):
        pass

    def get_status(self):
        return collections.OrderedDict([
            ("name", self.name),
            ("rpm", self.get_rpm())])
