from . import config_params
from . import thermometer
from . import harddrive
from . import util

import collections
import logging
import time

logger = logging.getLogger(__name__)

class Fan(config_params.Configurable):
    _params = [
        ("name", None, "Name that will appear in status output."),
        ("min_pwm", 80, "Minimal allowed nonzero PWM value. Below this the fan will stop in normal mode, or stay on minimum in settle mode."),
        ("spinup_pwm", 128, "Minimal pwm settings to overcome static friction in the fan. Will be kept for first update period after start."),
        ("min_settle_time", 120, "Minimal number of seconds at minimum pwm before stopping the fan."),
        ("max_settle_time", 3 * 60 * 60, "Maximal number of seconds at minimum pwm before stopping the fan."),
        ("settle_time_reset_interval", 60 * 60, "After how many seconds of stopped fan is the settle time reset to minimum"),
        ("pid", config_params.InstanceOf([util.Pid], Exception), "PID controller for this fan."),
        ("thermometers", config_params.ListOf([thermometer.SystemThermometer,
                                               harddrive.Harddrive,
                                               thermometer.MockThermometer]), ""),
    ]

    def __init__(self, parent, params):
        self.process_params(params)

        self._state = "running"
        self._settle_timer = util.TimeoutHelper(self.min_settle_time)
        self.set_pwm(255)

        self._last_pwm = None
        self._stopped_since = None

    def get_rpm(self):
        """ Read rpm of the fan. Needs to be overridden. """
        raise NotImplementedError()

    def set_pwm(self, pwm):
        """ Set the PWM input the fan. Needs to be overridden. """
        raise NotImplementedError()

    def _set_pwm_checked(self, pwm):
        """ Wrapped set_pwm, deduplicates and logs speed changes """
        pwm = int(pwm)
        if pwm == self._last_pwm:
            return

        logger.debug("Setting {} to {}%".format(self.name, (100 * pwm) // 255))
        self.set_pwm(pwm)
        self._last_pwm = pwm

    def _change_state(self, state):
        """ Change state and log it """
        self._state = state
        logger.info("Changing state of {} to {}".format(self.name, state))

    def update(self, dt):
        """ This is where the internal state machine is implemented """
        logger.debug("Speed of {} is {} rpm".format(self.name, self.get_rpm()))

        for thermometer in self.thermometers:
            thermometer.update(dt)

        normalized_temperature_error = max(t.get_normalized_temperature_error()
                                           for t in self.thermometers)
        pwm = self.pid.update(normalized_temperature_error, dt, self.min_pwm, 255)

        if self._state == "running":
            self._set_pwm_checked(pwm)
            if normalized_temperature_error < 0 and pwm <= self.min_pwm:
                self._settle_timer.reset()
                self._change_state("settle")
                logger.debug("Settle time for {} is {}s".format(self.name, self._settle_timer.limit))

        elif self._state == "settle":
            if normalized_temperature_error > 0 or pwm > self.min_pwm:
                self._set_pwm_checked(pwm)
                self._change_state("running")
            elif self._settle_timer(dt):
                self._set_pwm_checked(0)
                self._change_state("stopped")
                self._stopped_since = time.time()
            else:
                self._set_pwm_checked(pwm)

        elif self._state == "stopped":
            self.pid.reset_accumulator()
            if normalized_temperature_error > 0:
                self._set_pwm_checked(max(pwm, self.spinup_pwm))
                self._change_state("running")

                if self._stopped_since + self.settle_time_reset_interval < time.time():
                    self._settle_timer.limit = self.min_settle_time
                else:
                    self._settle_timer.limit = min(self._settle_timer.limit * 2,
                                                   self.max_settle_time)

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


class MockFan(Fan, config_params.Configurable):
    _params = [
        ("name", None, "Name that will appear in status output."),
        ("rpm", 1234, "RPM shown."),
    ]

    def get_rpm(self):
        return self.rpm

    def set_pwm(self, value):
        pass
