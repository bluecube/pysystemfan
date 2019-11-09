from . import config_params
from . import thermometer
from . import util

import subprocess
import shlex
import os
import collections
import logging

logger = logging.getLogger(__name__)

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
        ("spinning_only_activity", False, "Activity for this drive is 1 or 0 depending "
                                          "on whether it is spinning or not. Otherwise "
                                          "IO operation count per second is used."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        if not len(self.stat_path):
            self.stat_path = "/sys/block/{}/stat".format(os.path.basename(self.path))

        self._previous_stat = None
        self._spindown_timeout = util.TimeoutHelper(self.spindown_time)

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
            elif id_number == 190: #"Airflow_Temperature_Cel
                return int(split[9])

        raise RuntimeError("Didn't find temperature in output of {}".format(_list_to_shell(command)))

    def spindown(self):
        logger.info("Spinning down hard drive %s", self.name)
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

    def _get_stat(self):
        with open(self.stat_path, "r") as fp:
            return tuple(map(int, fp.read().split()))

    def _get_io(self):
        stat = self._get_stat()
        had_io = stat != self._previous_stat
        if self._previous_stat is None:
            ops = 0
        else:
            ops = stat[0] - self._previous_stat[0] + stat[4] - self._previous_stat[4]

        self._previous_stat = stat

        return had_io, ops

    def get_cached_temperature(self):
        return self._cached_temperature

    def get_cached_activity(self):
        if self.spinning_only_activity:
            return 1 if self._cached_spinning else 0
        else:
            return self._cached_iops

    def _get_temp_safe(self):
        """ Return temperature, is_spinning tuple."""
        is_spinning = self.is_spinning()

        if is_spinning or self.measure_in_idle:
            temperature = self.get_temperature()
        else:
            temperature = None

        return temperature, is_spinning

    def init(self):
        temperature, is_spinning = self._get_temp_safe()
        self._previous_stat = self._get_stat()

        self._cached_temperature = temperature
        self._cached_spinning = is_spinning
        self._cached_iops = 0

    def update(self, dt):
        temperature, is_spinning = self._get_temp_safe()
        had_io, ops = self._get_io()

        if is_spinning and self.spindown_time > 0:
            if had_io:
                self._spindown_timeout.reset()
            elif self._spindown_timeout(dt):
                self.spindown()

        self._cached_temperature = temperature
        self._cached_spinning = is_spinning
        self._cached_iops = ops / dt

        logger.debug("Harddrive {} {}°C (target {}°C), {:.1g} iops{}".format(self.name,
                                                                             self._cached_temperature,
                                                                             self.target_temperature,
                                                                             self._cached_iops,
                                                                             ", spinning" if self._cached_spinning else ""))
        return {"type": self.__class__.__name__,
                "temperature": self._cached_temperature,
                "target_temperature": self.target_temperature,
                "iops": self._cached_iops,
                "spinning": self._cached_spinning}
