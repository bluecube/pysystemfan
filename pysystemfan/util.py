from . import config_params

import itertools
import collections
import logging

logger = logging.getLogger(__name__)

def clamp(v, low, high):
    return max(low, min(v, high))

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
        ("derivative_smoothing", 10, "How many seconds has 50% influence on the result"),
        ("max_integrator", 255, "Maximum value of integrator (anti windup)"),
    ]

    def __init__(self, parent, params):
        self.process_params(params)

        if self.derivative_smoothing == 0:
            self._smoothing = 0
        else:
            self._smoothing = 2**(-1 / self.derivative_smoothing)

        self.reset()

    def reset(self):
        self._integrator = 0
        self._derivatives = None
        self._previous_errors = None

    def reset_accumulator(self):
        self._integrator = 0

    def update(self, errors, dt):
        m = self._smoothing**dt # Multiplier for derivative smoothing

        if self._derivatives is not None:
            if len(errors) != len(self._derivatives):
                raise ValueError("Changed number of errors")
        else:
            self._previous_errors = errors
            self._derivatives = itertools.repeat(0)

        logger.debug("m = {:.2g}".format(m))
        max_next_predicted_error = None
        selected_derivative = None # Selecting a derivative that would cause highest error in the next time step
        new_derivatives = []
        prev_max_error = -float("inf")
        max_error = -float("inf")
        max_derivative = 0;
        for (e, p, d) in zip(errors, self._previous_errors, self._derivatives):
            d = (1 - m) * d + m * (e - p) / dt # New smoothed derivative (using EWMA with variable time step)
            new_derivatives.append(d)

            if abs(d) > max_derivative:
                max_derivative = d

            next_predicted_error = e + d * dt # Predicted error after the next time step
            if max_next_predicted_error is None or max_next_predicted_error < next_predicted_error:
                max_next_predicted_error = next_predicted_error
                selected_derivative = d

            prev_max_error = max(prev_max_error, p)
            max_error = max(max_error, e)

        self._previous_errors = errors
        self._derivatives = new_derivatives

        logger.debug("error = {:.2g}, derivative = {:.2g}, integrator = {:.2g}".format(max_error,
                                                                                selected_derivative,
                                                                                self._integrator))

        ret = self.kP * max_error + self.kI * self._integrator + self.kD * selected_derivative

        self._integrator =  clamp(self._integrator + dt * (prev_max_error + max_error) / 2,
                                  0, self.max_integrator)

        return ret, max_derivative

class Interrupter:
    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, ex_traceback):
        if ex_type is KeyboardInterrupt:
            logger.info("Interrupted")
            return True
        else:
            return False
