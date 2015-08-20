class Thermometer:
    _params = [
        ("path", None, "Path in /sys (typically /sys/class/hwmon/hwmon?/temp?_input) that has the temperature."),

        ("name", "", "Optional name that wil appear in status output if present"),

        ("target_temperature", None, "Temperature we are trying to reach when the fan is running"),
        ("fan_start_temperature", -100, "Temperature at which the fan needs to start. Set higher than target_temperature to be able to stop the fan, or very low to prevent spinning down the fan."),

        ("kP", 20, "Proportional constant of the controler."),
        ("kI", 10, "Integration constant of the controller."),
        ("kD", 20, "Derivation constant of the controller."),

        ("derivative_smoothing_window", 300, "Number of seconds to use as a smoothing window for derivative term. This gets rounded to a nearest whole number of updates.")
    ]

    def __init__(self, fan, **params):
        _process_params(self, params)

        self._anti_windup = 300 / self.kI

        self._last_temperature = collections.deque([self.get_temperature()], round(self.derivative_smoothing_window / fan._sleep_time) + 1)
        self._integral = fan.min_pwm / self.kI

    def get_temperature(self):
        if self.path.startswith(self._smartctl_prefix):
            return self._get_smartctl_temperature(self.path[len(self._smartctl_prefix):])
        else:
            with open(self.rpm_path, "r") as fp:
                return int(fp.readline())

    @staticmethod
    def _get_smartctl_temperature(arguments):
        command = ["smartctl", "-A"] + shlex.split(arguments)
        process = subprocess.Popen(command,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                   universal_newlines=True)
        for line in process.stdout:
            split = line.split()
            if len(split) >= 10 and split[1] == "Temperature_Celsius":
                return int(split[9])

        if process.wait():
            raise RuntimeError("Command {} failed with return code {}".format(str(command), process.returncode))
        else:
            raise RuntimeError("Didn't find temperature in output of command {}".format(str(command)))

    def update_temperature(self):
        self._last_temperature.append(self.get_temperature())

    def need_fan(self):
        return self._last_temperature[-1] >= self.fan_start_temperature

    def requiered_fan_pwm(self):
        temperature = self._last_temperature[-1]

        error = temperature - self.target_temperature

        self._integral += error
        if self._integral > self._anti_windup:
            self._integral = self._anti_windup
        elif self._integral < -self._anti_windup:
            self._integral = -self._anti_windup

        derivation = temperature - self._last_temperature[0]

        ret = self.kP * error + self.kI * self._integral + self.kD * derivation

        return ret

    def status(self):
        ret = {
            "temperature": self.get_temperature(),
            "need_fan": self.need_fan(),
            "_integral": self._integral,
            "_smoothed_last_temperature": self._last_temperature[0]
        }
        if self.name:
            ret["name"] = self.name
        return ret

    def config(self):
        return _dump_params(self)


def main():
    pysystemfan = PySystemFan()

    try:
        wakeup_times = [iter(f) for f in pysystemfan.fans]
        for wakeup_time in heapq.merge(*wakeup_times):
            print(_json_dump_indented(pysystemfan.status()))
            time.sleep(wakeup_time - time.time())
    finally:
        for fan in pysystemfan.fans:
            fan.set_pwm(255)

