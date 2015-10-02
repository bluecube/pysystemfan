from . import config_params

import collections
import logging

class History(config_params.Configurable):
    """ Stores past data in a in-memory buffer and optionaly also in a file. """

    _params = [
        ("storage_time", 3600, "How many seconds to record. Roudned to whole update intervals"),
        #("storage_path", None, "File where to save the model"),
        #("save_interval", 5*60, "Inteval between saves of model parameters."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)

        self._logger = logging.getLogger(__name__)

        self.update_time = parent.update_time

        self._buffer = None
        self._labels = None

    def _update(statuses):
        row_dict = {}
        for status in statuses:
            name = status["name"]
            for k, v in status.items():
                if k == "name":
                    continue
                key = (name, k)
                if key not in labels:
                    index = len(self._labels)
                    self._labels[key] = index
                else:
                    index = self._labels[key]

                row_dict[index] = v

        return [row_dict.get(i) for i in range(max(row_dict) + 1)]

    def init(self, thermometers, fans):
        self._buffer = collections.deque(round(self.storage_time / self.update_time))
        labels = {}

        thermometer_statuses = [thermometer.get_status() for thermometer in thermometers]

        self._buffers = collections.deque(round(self.storage_time / self.update_time))
        self._labels = None

        self.update(thermometers, fans)

    def update(self, thermometers, fans):
        row = []
        for thermometer in thermometers:
            row.append(thermometer.get_status())
        for fan in fans:
            row.append(fan.get_status)

        self._buffer.append(

    def get_status(self):
        
