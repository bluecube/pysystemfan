from . import config_params

import logging
import numpy.matlib

class Model(config_params.Configurable):
    """ Model that controls cooling.

    The main equation:

    d(temp_i)/d(time) = a_i + b_i * activity_i + c_i * (avg_temp - temp_i) + (d_i + sum_j(fan_j * e_i,j)) * (f - temp_i)

    temp_i and activity_i are measured variables
    fan_j is model the output of this model from previous step
    a_i, b_i, c_i, d_i, e_i,j and f are model parameters (f is estimate of outside temperature)
    avg_temp is average of temp_i
    """

    _params = [
        ("storage_path", None, "File where to save the model"),
        ("parameter_variance", 0.01, "1-sigma change per hour of parameters other"
                                     "than external temperature"),
        ("temperature_variance", 0.5, "1-sigma change per hour of external temperature"),
        ("thermometer_variance", 0.5, "Variance of thermometer measurements."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)

        self._prev_temperatures = None
        self._prev_activities = None

        self.param_estimate = None
        self.param_covariances = None

        self._logger = logging.getLogger(__name__)

    @staticmethod
    def _extract_state(thermometers):
        temperatures = []
        activities = []
        for thermometer in thermometers:
            temperatures.append(thermometer.get_cached_temperature())
            activities.append(thermometer.get_cached_activity())

        return temperatures, activities

    def load(self):
        self._logger.error("Not implemented")

    def save(self):
        self._logger.error("Not implemented")

    def init(self, thermometers, fans):
        temperatures, activities = self._extract_state(thermometers)
        self._prev_temperatures = temperatures
        self._prev_activities = activities
        self._prev_pwm = [255 for fan in fans]

        self.i = _IndexHelper(len(thermometers), len(fans))

        self.param_estimate = numpy.matlib.ones((self.i.param_count, 1))
        self.param_estimate[self.i.f, 0] = 21 # Initial estimate for outside temperature

        #self.param_covariances = numpy.matlib.zeros


        return self._prev_pwm

    def update(self, thermometers, fans):
        temperatures, activities = self._extract_state(thermometers)
        return self._prev_pwm

class _IndexHelper:
    """Just a helper that gives indices to the param array based on name"""

    def __init__(self, thermometers, fans):
        self.param_count = thermometers * (4 + fans) + 1
        self.a = range(0, thermometers)
        self.b = range(thermometers, 2 * thermometers)
        self.c = range(2 * thermometers, 3 * thermometers)
        self.d = range(3 * thermometers, 4 * thermometers)
        self.e = [range(4 * thermometers + i * fans,
                        4 * thermometers + (i + 1) * fans)
                  for i in range(thermometers)]
        self.f = self.param_count - 1

        assert all(len(x) == thermometers for x in (self.a, self.b, self.c, self.d, self.e))
        assert all(len(x) == fans for x in self.e)

        assert self.a[-1] + 1 == self.b[0]
        assert self.b[-1] + 1 == self.c[0]
        assert self.c[-1] + 1 == self.d[0]
        assert self.d[-1] + 1 == self.e[0][0]
        assert all(x[-1] + 1 == y[0] for x, y in zip(self.e[:-1], self.e[1:]))
        assert self.e[-1][-1] + 1 == self.f

