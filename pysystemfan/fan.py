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
        ("min_pwm", 80, "Initial value for minimal allowed nonzero PWM value. Below this the fan will stay on minimum in settle mode and then stop when the settle timeout runs out. This value will be modified to track the actual fan limits."),
        ("spinup_pwm", 128, "Minimal pwm settings to overcome static friction in the fan."),
        ("spinup_time", 10, "How long to keep the spinup pwm for start."),
        ("min_settle_time", 30, "Minimal number of seconds at minimum pwm before stopping the fan."),
        ("max_settle_time", 12 * 60 * 60, "Maximal number of seconds at minimum pwm before stopping the fan."),
        ("pid", config_params.InstanceOf([util.Pid], Exception), "PID controller for this fan."),
        ("thermometers", config_params.ListOf([thermometer.SystemThermometer,
                                               harddrive.Harddrive,
                                               thermometer.MockThermometer]), ""),
        ("fan_max_rpm_sanity_check", 0, "Fan speed larger than this value are considered as a glitch reading and ignored. Value of 0 means to not check the range."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)

        self._state = "running"
        self._spinup_timer = util.TimeoutHelper(self.spinup_time)
        self._settle_timer = util.TimeoutHelper(self.min_settle_time)

        self._min_pwm_helper = _MinPowerHelper(self.min_pwm, 1, parent.min_rpm_probe_interval)

        self._last_pwm = None
        self.set_pwm_checked(255)

        self._last_rpm = 0

        duplicate_thermometer_names = util.duplicates(thermometer.name for thermometer in self.thermometers)
        if duplicate_thermometer_names:
            raise ValueError("Duplicate thermometer names: {}".format(", ".join(duplicate_thermometer_names)))

    def get_rpm(self):
        """ Read rpm of the fan. Needs to be overridden. """
        raise NotImplementedError()

    def set_pwm(self, pwm):
        """ Set the PWM input the fan. Needs to be overridden. """
        raise NotImplementedError()

    def set_pwm_checked(self, pwm):
        """ Wrapped set_pwm, deduplicates and logs speed changes """
        pwm = int(pwm)
        if pwm > 255:
            pwm = 255
        if pwm == self._last_pwm:
            return

        logger.debug("Setting {} to {}".format(self.name, self._pwm_to_percent(pwm)))
        self.set_pwm(pwm)
        self._last_pwm = pwm

    @staticmethod
    def _pwm_to_percent(pwm):
        return str((100 * pwm) // 255) + "%"

    def _change_state(self, state):
        """ Change state and log it """
        self._state = state
        logger.debug("Changing state of {} to {}".format(self.name, state))

    def update(self, dt):
        """ This is where the internal state machine is implemented """
        new_dt = float("inf")
        status_block = {}

        rpm = self.get_rpm()
        if self.fan_max_rpm_sanity_check != 0 and rpm > self.fan_max_rpm_sanity_check:
            logger.warning("Detected glitch speed reading of {} ({}), using last value of {} instead.",
                           self.name, rpm, self._last_rpm)
            rpm = self._last_rpm
        else:
            logger.debug("Speed of {} is {} rpm".format(self.name, rpm))

        status_block["rpm"] = rpm

        thermometers_status = {}
        for thermometer in self.thermometers:
            thermometers_status[thermometer.name] = thermometer.update(dt)
        status_block["thermometers"] = thermometers_status

        errors = [t.get_normalized_temperature_error()
                  for t in self.thermometers]
        max_error = max(errors)
        pwm, max_derivative = self.pid.update(errors, dt)

        clamped_pwm = clamped_pwm = util.clamp(pwm, self._min_pwm_helper.value, 255)

        if rpm == 0 and self._state in ("running", "settle"):
            self._spinup(clamped_pwm)
            self._min_pwm_helper.failed()
            logger.info("%s not spinning when it should, increasing min PWM to %s",
                        self.name,
                        self._pwm_to_percent(self._min_pwm_helper.value))

        elif self._state in ("running", "spinup"):
            if self._state == "spinup":
                if self._spinup_timer(dt):
                    self._change_state("running")
                else:
                    new_dt = min(new_dt, self._spinup_timer.remaining_time)
                    clamped_pwm = max(clamped_pwm, self.spinup_pwm)

            self.set_pwm_checked(clamped_pwm)

            if max_error < 0 and clamped_pwm <= self._min_pwm_helper.value:
                self._settle_timer.reset()
                self._change_state("settle")
                logger.debug("Settle time for {} is {}s".format(self.name, self._settle_timer.limit))

        elif self._state == "settle":
            if max_error > 0 or clamped_pwm > self._min_pwm_helper.value:
                self.set_pwm_checked(clamped_pwm)
                self._change_state("running")
            elif self._settle_timer(dt):
                self.set_pwm_checked(0)
                self._change_state("stopped")
            else:
                self._min_pwm_helper.update(dt)
                self.set_pwm_checked(self._min_pwm_helper.value)

        elif self._state == "stopped":
            self.pid.reset_accumulator()
            if max_error > 0:
                self._spinup(clamped_pwm)

                # Increase settle timer when spinning up, to avoid periodic spinups and spin downs
                # due to minimum allowed fan RPM being too much for the required temperature
                self._settle_timer.limit = min(self._settle_timer.limit * 2,
                                               self.max_settle_time)
            elif max_derivative <= 0:
                # If the derivative is not increasing, then we are in steady state and we start
                # decreasing settle timer
                self._settle_timer.limit = max(self._settle_timer.limit - dt,
                                               self.min_settle_time)

        else:
            raise Exception("Unknown state " + self._state)

        status_block["pid"] = {"error": max_error, "derivative": 60*max_derivative, "integrator": self.pid._integrator/60} # Derivative is in degrees / minute, integrator in minutes
        status_block["min_pwm"] = self._min_pwm_helper.value
        status_block["settle_timeout"] = self._settle_timer.limit

        return new_dt, status_block

    def _spinup(self, pwm):
        self.set_pwm_checked(max(pwm, self.spinup_pwm))
        self._change_state("spinup")
        self._spinup_timer.reset()


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


class _MinPowerHelper:
    """ Helper state machine that tracks the minimum allowed PWM input of a fan. """

    def __init__(self, initial_value, step, probe_interval):
        self.value = initial_value
        self._step = step
        self._probe_timeout = util.TimeoutHelper(probe_interval)
        self._probing = True

    def update(self, dt):
        if self._probing:
            self.value -= self._step
        elif self._probe_timeout(dt):
            self._probing = True
            self.value -= self._step

        return self.value

    def failed(self):
        self.value += self._step
        self._probing = False
        self._probe_timeout.reset()
