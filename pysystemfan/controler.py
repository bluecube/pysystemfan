from . import config_params
from . import model
from . import fan
from . import thermometer
from . import harddrive
from . import status_server
from . import util

import json
import time
import collections
import logging

class Controler(config_params.Configurable):
    _params = [
        ("log_file", "", "Where to log. If empty (default), logs to stdout."),
        ("log_level", "WARNING", "Minimal logging level. "
                                 "One of DEBUG, INFO, WARNING, ERROR, CRITICAL"),
        ("update_time", 30, "Time between updates in seconds."),
        ("status_server", config_params.InstanceOf(status_server.StatusServer), ""),
        ("model", config_params.InstanceOf(model.Model), ""),
        ("fans", config_params.ListOf(fan.Fan), ""),
        ("thermometers", config_params.ListOf(thermometer.SystemThermometer), ""),
        ("harddrives", config_params.ListOf(harddrive.Harddrive), ""),
    ]

    def __init__(self):
        self._load_config("pysystemfan.json")
        self.all_thermometers = util.ConcatenatedLists(self.thermometers,
                                                       self.harddrives)
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

    def _load_config(self, path):
        with open(path, "r") as fp:
            config = json.load(fp)

        self.process_params(config)


    def get_status(self):
        "Return status for the status server that can be directly jsonified"

        return collections.OrderedDict([
            ("last_update", self._prev_time),
            ("update_interval", self.update_time),
            ("thermometers", [x.get_status() for x in self.all_thermometers]),
            ("fans", [x.get_status() for x in self.fans]),
            ])

    def _set_pwm(self, pwms):
        for fan, pwm in zip(self.fans, pwms):
            assert(pwm == 0 or pwm > fan.min_pwm)
            fan.set_pwm(pwm)
        self._prev_pwm = pwms

    def _full_steam(self):
        self._logger.info("Setting all fans to 100% power.")
        self._set_pwm([255 for fan in self.fans])

    def _check_temperatures_failsafe(self):
        for thermometer in self.all_thermometers:
            if thermometer.get_cached_temperature() > thermometer.max_temperature:
                return False
        return True

    def _update(self, func):
        self._prev_time = time.time()
        for x in self.all_thermometers:
            x.update()

        pwm = func(self.all_thermometers, self.fans, self._prev_pwm)

        if self._check_temperatures_failsafe():
            self._set_pwm(pwm)
        else:
            self._logger.error("Temperature failsafe triggered.")
            self._full_steam()

        time.sleep(self.update_time)

    def run(self):
        self.status_server.set_status_callback(self.get_status)
        self.status_server.start()

        try:
            self._update(self.model.init)
            while True:
                self._update(self.model.update)

        except KeyboardInterrupt:
            self._logger.info("Keyboard interrupt")
        except:
            self._logger.exception("Unhandled exception")
        finally:
            self._full_steam()
            self.model.save()
            self.status_server.stop()
