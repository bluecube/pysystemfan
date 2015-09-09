from . import config_params
from . import thermometer

import subprocess
import shlex
import os
import collections
import logging

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
        self._previous_stat = None
        self._spindown_ticks = round(self.spindown_time / self.update_time)
        self._spindown_countdown = self._spindown_ticks

        self._logger = logging.getLogger(__name__)

        super().__init__()

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

    def had_io(self):
        stat = self._get_stat()
        previous = self._previous_stat
        self._previous_stat = stat

        return stat != previous

    def _update_spindown(self, is_spinning):
        if not is_spinning:
            # if the drive is stopped we don't need to handle spindowns
            return

        if self.spindown_time == 0:
            # if spindowns are not enabled, we don't need to handle them
            return

        if self.had_io():
            self._spindown_counter = 0
        else:
            self._spindown_counter += 1

        if self._spindown_counter >= self._spindown_ticks:
            self._logger.info("Spinning down hard drive %s", self.name)
            self.spindown()

    def get_status(self):
        temperature, is_spinning = self._get_temp_safe()
        return collections.OrderedDict([
            ("name", self.name),
            ("temperature", temperature),
            ("spinning", is_spinning)])

    def _get_temp_safe(self):
        """ Return temperature, is_spinning tuple."""
        is_spinning = self.is_spinning()

        if is_spinning or self.measure_in_idle:
            temperature = self.get_temperature()
        else:
            temperature = None

        return temperature, is_spinning

    def update(self):
        temperature, is_spinning = self._get_temp_safe()
        self._update_spindown(is_spinning)
        self._cached_temperature = temperature
        self._cached_activity = 1 if is_spinning else 0
