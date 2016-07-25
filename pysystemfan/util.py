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
        ("derivative_smoothing", 5, "How many more ticks to use when calcualting derivatives")
        #TODO: Smoothing should be time based too (rather than tick based)
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        self.reset()

    def reset(self):
        self._integrator = 0
        self._last_error = None
        self._derivatives = collections.deque(maxlen=self.derivative_smoothing + 1)

    def update(self, error, dt):
        if self._last_error is not None:
            derivative = (error - self._last_error) / dt
        else:
            derivative = 0
        smooth_derivative = (sum(self._derivatives) + derivative) / (len(self._derivatives) + 1)
        self._derivatives.append(derivative)
        self._last_error = error

        self._integrator += error * dt

        return self.kP * error + self.kI * self._integrator + self.kD * smooth_derivative

class Interrupter:
    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, ex_traceback):
        if ex_type is KeyboardInterrupt:
            logger.info("Interrupted")
            return True
        else:
            return False

def clip(x, a, b):
    return max(a, min(x, b))
