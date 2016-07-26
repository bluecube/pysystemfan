from . import config_params
from . import fan
from . import util

import contextlib
import argparse
import time
import json
import logging

logger = logging.getLogger(__name__)

class Controler(config_params.Configurable):
    _params = [
        ("log_file", "", "Where to log. If empty (default), logs to stdout."),
        ("log_level", "WARNING", "Minimal logging level. "
                                 "One of DEBUG, INFO, WARNING, ERROR, CRITICAL"),
        ("update_time", 30, "Time between updates in seconds."),
        ("fans", config_params.ListOf([fan.SystemFan,
                                       fan.MockFan]), ""),
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

        self._prev_time = None

        self._extra_args = extra_args

    def _load_config(self, path):
        with open(path, "r") as fp:
            config = json.load(fp)

        self.process_params(config)

    def full_steam(self):
        logger.info("Setting all fans to 100% power.")
        for fan in self.fans:
            fan.set_pwm(255)

    def update(self, dt):
        for f in self.fans:
            f.update(dt)

    def run(self):
        try:
            with contextlib.ExitStack() as stack:
                stack.callback(self.full_steam)
                stack.enter_context(util.Interrupter())

                logger.info("PySystemFan started")
                while True:
                    time.sleep(self.update_time)
                    self.update(self.update_time)
        except:
            logger.exception("Unhandled exception")
