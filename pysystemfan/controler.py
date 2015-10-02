from . import config_params
from . import model
from . import history
from . import fan
from . import thermometer
from . import harddrive
from . import status_server
from . import util

import json
import time
import collections
import logging
import contextlib

class Controler(config_params.Configurable):
    _params = [
        ("log_file", "", "Where to log. If empty (default), logs to stdout."),
        ("log_level", "WARNING", "Minimal logging level. "
                                 "One of DEBUG, INFO, WARNING, ERROR, CRITICAL"),
        ("update_time", 30, "Time between updates in seconds."),
        ("status_server", config_params.InstanceOf([status_server.StatusServer]), ""),
        ("model", config_params.InstanceOf([model.Model]), ""),
        ("history", config_params.InstanceOf([history.History], {}), ""),
        ("fans", config_params.ListOf([fan.SystemFan,
                                       fan.MockFan]), ""),
        ("thermometers", config_params.ListOf([thermometer.SystemThermometer,
                                               harddrive.Harddrive,
                                               thermometer.MockThermometer]), ""),
    ]

    def __init__(self, **extra_args):
        self._load_config("pysystemfan.json")
        logging_config = {
            "level": logging.getLevelName(self.log_level),
            "format": "%(asctime)s %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
        if len(self.log_file):
            logging_config["filename"] = self.log_file
        logging.basicConfig(**logging_config)
        self._logger = logging.getLogger(__name__)

        self._prev_time = None
        self._prev_pwm = None

        self._extra_args = extra_args

    def _load_config(self, path):
        with open(path, "r") as fp:
            config = json.load(fp)

        self.process_params(config)

    def get_status(self):
        "Return status for the status server that can be directly jsonified"

        return collections.OrderedDict([
            ("last_update", self._prev_time),
            ("update_interval", self.update_time),
            ("thermometers", [x.get_status() for x in self.thermometers]),
            ("fans", [x.get_status() for x in self.fans]),
            ("model", self.model.get_status()),
            ])

    def _set_pwm(self, pwms):
        for fan, pwm in zip(self.fans, pwms):
            assert(pwm == 0 or pwm > fan.min_pwm)
            fan.set_pwm(pwm)
        self._prev_pwm = pwms

    def _full_steam(self):
        self._logger.info("Setting all fans to 100% power.")
        self._set_pwm([255 for fan in self.fans])

    def _set_pwm_with_failsafe(self, pwm):
        for thermometer in self.thermometers:
            if thermometer.get_cached_temperature() > thermometer.max_temperature:
                self._logger.error("Temperature failsafe triggered.")
                self._full_steam()
                return

        self._set_pwm(pwm)

    def _init(self):
        self._prev_time = time.time()
        for x in self.thermometers:
            x.init()

        pwm = self.model.init(self.thermometers, self.fans, **self._extra_args)
        self._set_pwm_with_failsafe(pwm)

        self.history.init(self.thermometers, self.fans)

    def _update(self):
        t = time.time()
        dt = t - self._prev_time
        self._prev_time = t

        for x in self.thermometers:
            x.update(dt)

        pwm = self.model.update(self.thermometers, self.fans, self._prev_pwm, dt)
        self._set_pwm_with_failsafe(pwm)

        self.history.update(self.thermometers, self.fans)

    def run(self):
        try:
            with contextlib.ExitStack() as stack:
                stack.callback(self._full_steam)

                self._init()
                stack.callback(self.model.save)

                self.status_server.set_status_callback(self.get_status)
                stack.enter_context(self.status_server)

                stack.enter_context(util.Interrupter(self._logger))

                while True:
                    time.sleep(self.update_time)
                    self._update()

        except:
            self._logger.exception("Unhandled exception")
