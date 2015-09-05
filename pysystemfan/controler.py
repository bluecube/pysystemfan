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

    def _load_config(self, path):
        with open(path, "r") as fp:
            config = json.load(fp)

        self.process_params(config)


    def get_status(self):
        "Return status for the status server that can be directly jsonified"

        return {
            "thermometers": [x.get_status() for x in self.all_thermometers],
            "fans": [x.get_status() for x in self.fans],
            }

    def run(self):
        self.status_server.set_status_callback(self.get_status)

        with self.status_server:
            try:
                time.sleep(self.update_time)

                while True:
                    status = tuple(zip(*[x.update() for x in self.all_thermometers]))

                    if self._last_status is not None:
                        fan_pwms = self.model.update(status, self._last_status)
                        for fan, pwm in zip(self.fans, fan_pwms):
                            fan.set_pwm(pwm)
                        self._last_fan_pwms = fan_pwms

                    self._last_status = status

                    time.sleep(self.update_time)
            except KeyboardInterrupt:
                self._logger.info("Keyboard interrupt")
            except:
                self._logger.exception("Unhandled exception")
            finally:
                self._logger.info("Restoring fans to 100% power.")
                for fan in self.fans:
                    fan.set_pwm(255)
