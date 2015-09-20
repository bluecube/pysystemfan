from . import config_params
from . import thermometer
from . import util

import subprocess
import shlex
import os
import collections
import logging
import time

def _iterate_command_output(self, command):
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                               universal_newlines=True)
    for line in process.stdout:
        yield line

    if process.wait():
        raise RuntimeError("Command {} failed with return code {}".format(_list_to_shell(command),
                                                                          process.returncode))

def _list_to_shell(l):
    return " ".join(shlex.quote(x) for x in l)

class Harddrive(thermometer.Thermometer, config_params.Configurable):
    _params = [
        ("path", None, "Device file of the disk. For example /dev/sda"),
        ("stat_path", "", "Path for reading activity statistics (/sys/block/<path basename>/stat). "
                          "If empty (the default), gets automatically assigned."),

        ("name", "", "Optional name that wil appear in status output if present."),

        ("spindown_time", 0, "After how long inactivity should the disk spin down (seconds). "
                             "This value will be rounded to the nearest update interval, "
                             "if zero, the drive will not be spun down by this sctipt."),
        ("measure_in_idle", False, "Selects whether to keep measuring temperature even when the drive is idle."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        if not len(self.stat_path):
            self.stat_path = "/sys/block/{}/stat".format(os.path.basename(self.path))

        self.update_time = parent.update_time
        self._previous_time = None
        self._previous_stat = None
        self._spindown_timeout = util.TimeoutHelper(self.spindown_time, self.update_time)

        self._logger = logging.getLogger(__name__)

        self._cached_temperature = None
        self._cached_spinning = None
        self._cached_iops = None

    def get_temperature(self):
        command = ["smartctl", "-A", self.path]
        for line in _iterate_command_output(self, command):
            split = line.split()
            if len(split) < 10:
                continue
            try:
                id_number = int(split[0])
            except ValueError:
                continue

            if id_number == 194: #"Temperature_Celsius"
                return int(split[9])

        raise RuntimeError("Didn't find temperature in output of {}".format(_list_to_shell(command)))

    def spindown(self):
        self._logger.info("Spinning down hard drive %s", self.name)
        subprocess.check_call(["hdparm", "-y", self.path],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def is_spinning(self):
        command = ["hdparm", "-C", self.path]
        for line in _iterate_command_output(self, command):
            split = line.split(":")
            if len(split) >= 2 and split[0].strip() == "drive state is":
                state = split[1].strip()
                if state == "unknown":
                    raise RuntimeError("Hdparm reported unknown state for " + self.path)
                elif state == "active/idle":
                    return True
                else:
                    return False

        raise RuntimeError("Didn't find drive state in output of {}".format(_list_to_shell(command)))

    def _get_io(self):
        with open(self.stat_path, "r") as fp:
            stat = tuple(map(int, fp.read().split()))

        had_io = stat != self._previous_stat
        if self._previous_stat is None:
            ops = 0
        else:
            ops = stat[0] - self._previous_stat[0] + stat[4] - self._previous_stat[4]

        self._previous_stat = stat

        return had_io, ops

    def get_status(self):
        return collections.OrderedDict([
            ("name", self.name),
            ("temperature", self._cached_temperature),
            ("spinning", self._cached_spinning),
            ("iops", self._cached_iops)])

    def get_cached_temperature(self):
        return self._cached_temperature

    def get_cached_activity(self):
        return 1 if self._cached_spinning else 0

    def _get_temp_safe(self):
        """ Return temperature, is_spinning tuple."""
        is_spinning = self.is_spinning()

        if is_spinning or self.measure_in_idle:
            temperature = self.get_temperature()
        else:
            temperature = None

        return temperature, is_spinning

    def update(self):
        t = time.time()
        temperature, is_spinning = self._get_temp_safe()
        had_io, ops = self._get_io()

        if is_spinning and self.spindown_time > 0:
            if had_io:
                self._spindown_timeout.reset()
            elif self._spindown_timeout.tick():
                self.spindown()

        self._cached_temperature = temperature
        self._cached_spinning = is_spinning
        if self._previous_time is None:
            self._cached_iops = 0
        else:
            self._cached_iops = ops / (t - self._previous_time)

        self._previous_time = t
