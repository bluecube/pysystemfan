from . import config_params
from . import model
from . import fan
from . import thermometer
from . import harddrive

import json

class PySystemFan(config_params.Configurable):
    _params = [
        ("update_time", 30, "Time between updates in seconds."),
        ("model", config_params.InstanceOf(model.Model), ""),
        ("model", config_params.InstanceOf(model.Model), ""),
        ("fans", config_params.ListOf(fan.Fan), ""),
        ("thermometers", config_params.ListOf(thermometer.SystemThermometer), ""),
        ("hadrddrives", config_params.ListOf(harddrive.Harddrive), ""),
    ]

    def __init__(self):
        self._load_config("pysystemfan.json")

    def _load_config(self, path):
        with open(path, "r") as fp:
            config = json.load(fp)

        self.process_params(config)
