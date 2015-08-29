from . import config_params
from . import model
from . import fan
from . import thermometer
from . import harddrive
from . import status_server

import json
import time

class PySystemFan(config_params.Configurable):
    _params = [
        ("update_time", 30, "Time between updates in seconds."),
        ("status_server", config_params.InstanceOf(status_server.StatusServer), ""),
        ("model", config_params.InstanceOf(model.Model), ""),
        ("fans", config_params.ListOf(fan.Fan), ""),
        ("thermometers", config_params.ListOf(thermometer.SystemThermometer), ""),
        ("harddrives", config_params.ListOf(harddrive.Harddrive), ""),
    ]

    def __init__(self):
        self._load_config("pysystemfan.json")

    def _load_config(self, path):
        with open(path, "r") as fp:
            config = json.load(fp)

        self.process_params(config)

    def run(self):
        self.status_server.set_status_callback(lambda: {"hello": "world"})
        with self.status_server:
            while True:
                thermometers = [thermometer.update() for thermometer in self.thermometers]
                harddrives = [harddrive.update() for harddrive in self.harddrives]

                time.sleep(self.update_time)
