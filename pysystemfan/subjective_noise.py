#!/usr/bin/env python3

import fan
import time
import random

class Dummy:
    def __init__(self, update_time):
        self.update_time = update_time

f = fan.Fan(Dummy(30), pwm_path = "/sys/class/hwmon/hwmon2/pwm1",
                       rpm_path = "/sys/class/hwmon/hwmon2/fan1_input",
                       thermometers = [])

print("starting test, Ctrl+C to exit")

results = []

f.set_pwm(255)
time.sleep(2)
input("This is max loudness (10) (Enter to continue)")

try:
    while True:
        pwm = random.randrange(f.min_pwm, 256)
        f.set_pwm(pwm)
        time.sleep(2)
        while True:
            value = input("How loud is it? (1-10) ")
            try:
                value = float(value)
            except ValueError:
                print("That's not a number")
                continue

            if value < 1 or value > 10:
                print("Enter value between 1 and 10")
                continue

            break

        results.append((pwm, value))

except KeyboardInterrupt:
    print("Interrupted")
finally:
    f.set_pwm(255)

print(results)
