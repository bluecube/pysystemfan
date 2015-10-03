from . import config_params

import collections
import logging
import itertools
import time

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

    def init(self, thermometers, fans):
        self._buffer = collections.deque(maxlen = round(self.storage_time / self.update_time))
        self._labels = collections.OrderedDict([(("time",), 0)])

        self.update(thermometers, fans)

    def update(self, thermometers, fans):
        row_dict = {0: time.time()}
        for x in itertools.chain(thermometers, fans):
            status = x.get_status()
            name = status["name"]
            for k, v in status.items():
                if k == "name":
                    continue
                key = (name, k)
                if key not in self._labels:
                    index = len(self._labels)
                    self._labels[key] = index
                else:
                    index = self._labels[key]

                row_dict[index] = v

        self._buffer.append([row_dict.get(i) for i in range(max(row_dict) + 1)])

    def get_status(self):
        labels = collections.OrderedDict()
        for k, v in self._labels.items():
            labels[" - ".join(k)] = v
        return collections.OrderedDict([
            ("labels", labels),
            ("values", list(self._buffer))])
