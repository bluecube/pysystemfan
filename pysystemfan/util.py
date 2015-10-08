import itertools
import logging

class TimeoutHelper:
    def __init__(self, time, update_interval):
        self.limit = round(time / update_interval)
        self.reset()

    def reset(self):
        self.counter = 0

    def tick(self):
        self.counter += 1
        if self.counter >= self.limit:
            self.reset()
            return True
        else:
            return False

class Interrupter:
    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, ex_traceback):
        if ex_type is KeyboardInterrupt:
            self._logger.info("Interrupted")
            return True
        else:
            return False
