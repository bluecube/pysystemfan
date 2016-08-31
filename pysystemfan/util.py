from . import config_params

import itertools
import collections
import logging

logger = logging.getLogger(__name__)

class TimeoutHelper:
    def __init__(self, limit):
        self.limit = limit
        self.reset()

    def reset(self):
        self.counter = self.limit

    def __call__(self, dt):
        self.counter -= dt
        if self.counter < 0:
            self.reset()
            return True
        else:
            return False

class Pid(config_params.Configurable):
    _params = [
        ("kP", 0, "Proportional constant"),
        ("kI", 0, "Integral constant"),
        ("kD", 0, "Derivative constant"),
        ("derivative_smoothing", 120, "How many seconds of history to use when calcualting derivatives")
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        self.reset()

    def reset(self):
        self._integrator = 0
        self._last_errors = collections.deque()
        self._last_errors_dt = 0

    def reset_accumulator(self):
        self._integrator = 0

    def update(self, error, dt, min_value, max_value):
        if len(self._last_errors):
            self._last_errors_dt += dt
            if self._last_errors_dt > self.derivative_smoothing:
                self._last_errors.popleft()
                self._last_errors_dt -= self._last_errors[0][1]
            smooth_derivative = (error - self._last_errors[0][0]) / self._last_errors_dt
        else:
            smooth_derivative = 0

        self._last_errors.append((error, dt))

        logger.debug("error = {:.2f}, derivative = {:.2f}, integrator = {:.2f}".format(error,
                                                                                smooth_derivative,
                                                                                self._integrator))

        ret = self.kP * error + self.kI * self._integrator + self.kD * smooth_derivative

        if (error > 0 and ret < max_value) or (error < 0 and ret > min_value):
            self._integrator += error * dt

        if ret < min_value:
            return min_value
        elif ret > max_value:
            return max_value
        else:
            return ret

class Interrupter:
    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, ex_traceback):
        if ex_type is KeyboardInterrupt:
            logger.info("Interrupted")
            return True
        else:
            return False
