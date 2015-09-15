from . import config_params
from . import util

import logging
import numpy.matlib
import json
import math
import time

class Model(config_params.Configurable):
    """ Model that controls cooling.

    Uses EKF to estimate parameters of the model, and then model predictive
    control to determine the fan speeds.

    The model equation:

    d(temp_i)/d(time) = h_i(...) = a_i + b_i * activity_i + c_i * (avg_temp - temp_i) + (d_i + sum_j(fan_j * e_i,j)) * (f - temp_i)

    temp_i and activity_i are measured variables
    fan_j is model the output of this model from previous step (range 0-1 is expected here!)
    a_i, b_i, c_i, d_i, e_i,j and f are model parameters (f is estimate of outside temperature)
    avg_temp is average of temp_i


    Partial derivatives for EKF update:

    d(h_i)/d(a_j)   = 1 if i == j
                    = 0 if i != j
    d(h_i)/d(b_j)   = activity_i if i == j
                    = 0 if i != j
    d(h_i)/d(c_j)   = (avg_temp - temp_i) if i == j
                    = 0 if i != j
    d(h_i)/d(d_j)   = (f - temp_i) if i == j
                    = 0 if i != j
    d(h_i)/d(e_j,k) = fan_k * (f - temp_i) if i == j
                    = 0 if i != j
    d(h_i)/d(f)     = d_i + sum_k(fan_k * e_i,k)
    """

    _params = [
        ("storage_path", None, "File where to save the model"),
        ("save_interval", 5*60, "Inteval between saves of model parameters."),
        ("parameter_stdev", 1e-6, "1-sigma change per hour of parameters other"
                                     "than external temperature"),
        ("temperature_stdev", 0.5, "Standard deviation of external temperature. In °C/hour"),
        ("thermometer_stdev", 0.5, "Standard deviation of thermometer measurements. In °C."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)

        self._logger = logging.getLogger(__name__)

        self.update_time = parent.update_time
        self.autosave_timeout = util.TimeoutHelper(self.save_interval, self.update_time)

        self.prev_time = None
        self.prev_temperatures = None
        self.prev_activities = None

        self.param_estimate = None
        self.param_covariance = None

        # Helper matrices for parameter estimation
        self.process_noise_covariance = None
        self.observation_noise_covariance = None

    @staticmethod
    def _extract_state(thermometers):
        temperatures = []
        activities = []
        for thermometer in thermometers:
            temperatures.append(thermometer.get_cached_temperature())
            activities.append(thermometer.get_cached_activity())

        return temperatures, activities

    def load(self):
        self._logger.info("Loading model parameters from %s", self.storage_path)

        try:
            with open(self.storage_path, "r") as fp:
                loaded = json.load(fp)
        except FileNotFoundError:
            self._logger.info("Model storage file %s not found", self.storage_path)
            return False
        except ValueError:
            self._logger.info("Invalid content of model storage file. Ignoring.")
            return False

        if self.i.fans != loaded["fans"] or self.i.thermometers != loaded["thermometers"]:
            self._logger.info("Loaded model has unexpected dimensions (%d thermometers, %d fans loaded, "
                              "%d thermometers, %d fans expected). Ignoring.",
                              loaded["thermometers"], loaded["fans"],
                              self.i.thermometers, self.i.fans)
            return False

        self.param_estimate = numpy.matrix(loaded["param_estimate"])
        self.param_covariance = numpy.matrix(loaded["param_covariance"])

        return True

    def save(self):
        self._logger.info("Saving model parameters to %s", self.storage_path)

        with open(self.storage_path, "w") as fp:
            json.dump({"thermometers": self.i.thermometers,
                       "fans": self.i.fans,
                       "param_estimate": self.param_estimate.tolist(),
                       "param_covariance": self.param_covariance.tolist()},
                      fp)

    def predict_measurement(self, temperatures, activities, fans, avg_temp):
        """ Calculate the h_i functions, returns temperature derivatives. """
        return numpy.matrix([[self.param_estimate[self.i.a[i], 0] +
                              self.param_estimate[self.i.b[i], 0] * activities[i] +
                              self.param_estimate[self.i.c[i], 0] * (avg_temp - temperatures[i]) +
                              self.param_estimate[self.i.d[i], 0] * (self.param_estimate[self.i.f, 0] - temperatures[i]) +
                              sum(self.param_estimate[self.i.e[i][j], 0] * fans[j] / 255 for j in range(self.i.fans)) * (self.param_estimate[self.i.f, 0] - temperatures[i])]
                              for i in range(self.i.thermometers)])

    def observation_matrix(self, temperatures, activities, fans, avg_temp):
        """ Return a matrix with partial derivatives of the observation function """

        ret = numpy.matlib.zeros((self.i.thermometers, self.i.param_count))
        for i in range(self.i.thermometers):
            ret[i, self.i.a[i]] = 1
            ret[i, self.i.b[i]] = activities[i]
            ret[i, self.i.c[i]] = avg_temp - temperatures[i]
            ret[i, self.i.d[i]] = self.param_estimate[self.i.f, 0] - temperatures[i]
            for k in range(self.i.fans):
                ret[i, self.i.e[i][k]] = fans[k] * (self.param_estimate[self.i.f, 0] - temperatures[i]) / 255
                ret[i, self.i.f] += fans[k] * self.param_estimate[self.i.e[i][k], 0] / 255
            ret[i, self.i.f] += self.param_estimate[self.i.d[i], 0]

        return ret

    def init(self, thermometers, fans, prev_pwm):
        temperatures, activities = self._extract_state(thermometers)
        self.prev_time = time.time()
        self.prev_temperatures = temperatures
        self.prev_activities = activities

        self.i = _IndexHelper(len(thermometers), len(fans))

        loaded = self.load()

        if not loaded:
            # Find the inital values for the model. Mostly just guessing.

            self.param_estimate = numpy.matlib.ones((self.i.param_count, 1)) * 1e-3
            self.param_estimate[self.i.f, 0] = 21 # Initial estimate for outside temperature

            self.param_covariance = numpy.matlib.zeros((self.i.param_count, self.i.param_count))
            numpy.matlib.fill_diagonal(self.param_covariance, 1e-3)
            self.param_covariance[self.i.f, self.i.f] = 25 # 1 sigma error 5°C

        self.process_noise_covariance = numpy.matlib.zeros((self.i.param_count, self.i.param_count))
        numpy.matlib.fill_diagonal(self.process_noise_covariance,
                                   self.parameter_stdev**2 * self.update_time / 3600)
        self.process_noise_covariance[self.i.f, self.i.f] = self.temperature_stdev**2 * self.update_time / 3600

        self.observation_noise_covariance = numpy.matlib.zeros((self.i.thermometers, self.i.thermometers))
        numpy.matlib.fill_diagonal(self.observation_noise_covariance,
                                   self.thermometer_stdev**2 * 2)

        return [0 for fan in fans]

    def update(self, thermometers, fans, prev_pwm):
        if self.autosave_timeout.tick():
            self.save()

        temperatures, activities = self._extract_state(thermometers)

        t = time.time()
        dt = t - self.prev_time
        avg_temperatures = [(t1 + t2) / 2 for t1, t2 in zip(self.prev_temperatures, temperatures)]
        avg_activities = [(a1 + a2) / 2 for a1, a2 in zip(self.prev_activities, activities)]
        measurement = numpy.matrix([[(t1 - t2) / dt] for t1, t2 in zip(self.prev_temperatures, temperatures)])
        avg_temp = math.fsum(avg_temperatures) / len(temperatures)

        self.prev_time = t
        self.prev_temperatures = temperatures
        self.prev_activities = activities


        # Kalman filter:

        # 1) Predict:
        self.param_covariance += self.process_noise_covariance

        # 2) Update

        predicted_measurement = self.predict_measurement(avg_temperatures,
                                                         avg_activities,
                                                         prev_pwm,
                                                         avg_temp)

        measurement_residual = measurement - predicted_measurement

        observation_matrix = self.observation_matrix(avg_temperatures,
                                                     avg_activities,
                                                     prev_pwm,
                                                     avg_temp)

        residual_covariance = observation_matrix * self.param_covariance * observation_matrix.T + self.observation_noise_covariance
        kalman_gain = self.param_covariance * observation_matrix.T * residual_covariance.I
        self.param_covariance = (numpy.matlib.identity(self.i.param_count) - kalman_gain * observation_matrix) * self.param_covariance
        self.param_estimate += kalman_gain * measurement_residual

        return prev_pwm

class _IndexHelper:
    """Just a helper that gives indices to the param array based on name"""

    def __init__(self, thermometers, fans):
        self.thermometers = thermometers
        self.fans = fans
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

