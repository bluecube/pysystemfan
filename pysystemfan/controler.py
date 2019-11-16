from . import config_params
from . import fan
from . import status_server
from . import util

import contextlib
import argparse
import time
import datetime
import json
import logging
import logging.handlers

logger = logging.getLogger(__name__)

class Controler(config_params.Configurable):
    _params = [
        ("log_file", "", "Where to log. If empty (default), logs to stdout."),
        ("log_level", "WARNING", "Minimal logging level. "
                                 "One of DEBUG, INFO, WARNING, ERROR, CRITICAL"),
        ("min_rpm_probe_interval", 30 * 24 * 60 * 60, "How often to try decreasing the minimum fan speed when one is already learned"),
        ("update_time", 30, "Time between updates in seconds."),
        ("fans", config_params.ListOf([fan.SystemFan,
                                       fan.MockFan]), ""),
        ("status_server", config_params.InstanceOf([status_server.StatusServer], {}), ""),
    ]

    def __init__(self, config = None, **extra_args):
        if config is None:
            self._load_config("pysystemfan.json")
        else:
            self._load_config(config)

        logging_config = {
            "level": logging.getLevelName(self.log_level),
            "format": "%(asctime)s %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
        logging_config["handlers"] = [logging.StreamHandler()]
        if len(self.log_file):
            logging_config["handlers"].append(logging.handlers.FileHandler(self.log_file))
        else:
            logging_config["handlers"].append(logging.handlers.SysLogHandler())

        logging.basicConfig(**logging_config)

        self._extra_args = extra_args

        duplicate_fan_names = util.duplicates(fan.name for fan in self.fans)
        if duplicate_fan_names:
            raise ValueError("Duplicate fan names: {}".format(", ".join(duplicate_fan_names)))

    def _load_config(self, path):
        with open(path, "r") as fp:
            config = json.load(fp)

        self.process_params(config)

    def full_steam(self):
        logger.info("Setting all fans to 100% power.")
        for fan in self.fans:
            fan.set_pwm_checked(255)

    def update_forever(self):
        last_update = time.time()
        next_update = last_update + self.update_time

        while True:
            util.sleep_until(next_update)
            last_update, next_update = self.update(last_update)

    def update(self, last_update):
        """ Update all fans and status server. """

        now = time.time()
        dt = now - last_update
        new_dt = self.update_time

        fan_status = {}
        for f in self.fans:
            fan_dt, status_block = f.update(dt)
            fan_status[f.name] = status_block
            new_dt = min(new_dt, fan_dt)

        self.status_server["fans"] = fan_status
        self.status_server["last_update"] = datetime.datetime.fromtimestamp(now).isoformat()
        self.status_server["dt"] = new_dt

        self.status_server.update()

        return now, now + new_dt

    def run(self):
        try:
            with contextlib.ExitStack() as stack:
                logger.info("PySystemFan started")
                stack.enter_context(self.status_server)
                stack.callback(self.full_steam)
                stack.enter_context(util.Interrupter())

                self.update_forever()

        except:
            logger.exception("Unhandled exception")
