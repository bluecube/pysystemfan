from . import config_params
from . import thermometer

import subprocess
import shlex

class Harddrive(config_params.Configurable, thermometer.Thermometer):
    _params = [
        ("path", None, "Device file of the disk. For example /dev/sda"),
        ("stat_path", "", "Path for reading activity statistics (/sys/block/<path basename>/stat). "
                          "If empty (the default), gets automatically assigned.")

        ("name", "", "Optional name that wil appear in status output if present."),

        ("spindown_time", 0, "After how long inactivity should the disk spin down (seconds). "
                             "This value will be rounded to the nearest update interval, "
                             "if zero, the drive will not be spun down by this sctipt."),
        ("measure_in_idle", False, "Selects whether to keep measuring temperature even when the drive is idle."),
    ]

    def __init__(self, parent, **params):
        self.process_params(params)
        if not len(self.stat_path):
            self.stat_path = "/sys/block/{}/stat".format(os.path.basename(self.path))

        self.update_time = parent.update_time
        self._previous_stat = None
        self._spindown_ticks = round(spindown_time / self.update_time)
        self._spindown_countdown = spindown_time

        super.__init__()

    def _get_automatic_name(self):
        return self.path

    @staticmethod
    def _iterate_command_output(self, command)
        process = subprocess.Popen(command,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                   universal_newlines=True)
        for line in process.stdout:
            yield line

        if process.wait():
            raise RuntimeError("Command {} failed with return code {}".format(str(command), process.returncode))

    def get_temperature(self):
        if not self.measure_in_idle and not self.is_spinning():
            return None

        command = ["smartctl", "-A", self.path]
        for line in self._iterate_command_output(self, command):
            split = line.split()
            if len(split) >= 10 and int(split[0]) == 194: #"Temperature_Celsius"
                return int(split[9])

        raise RuntimeError("Didn't find temperature in output of {}".format(self._list_to_shell(command)))

    def get_activity(self):
        return 1 if self.is_spinning() else 0

    def spindown(self):
        subprocess.check_call(["hdparm", "-y", self.path])

    def is_spinning(self):
        command = ["hdparm", "-C", self.path]
        for line in self._iterate_command_output(self, command):
            split = line.split(":")
            if len(split) >= 2 and split[0].strip() == "drive state is":
                state = split[1].strip()
                if state == "unknown":
                    raise RuntimeError("Hdparm reported unknown state for " + self.path)
                elif state == "active/idle":
                    return True
                else:
                    return False

        raise RuntimeError("Didn't find drive state in output of {}".format(self._list_to_shell(command)))

    def _get_stat(self):
        with open(self.stat_path, "r") as fp:
            return tuple(map(int, fp.read().split()))

    def had_io(self):
        stat = self._get_stat()
        previous = self._previous_stat
        self._previous_stat = stat

        return stat != previous

    def update_spindown(self):
        raise NotImplementedError()

    @staticmethod
    def _list_to_shell(l):
        return " ".join(shlex.quote(x) for x in l)
