from . import thermometer
from . import harddrive

import json

def load_config(path):
    with open(path, "r") as fp:
        return json.load(fp)

def main():
    config_path = "pysystemfan.json"


    model = model.Model()

    try:
        wakeup_times = [iter(f) for f in pysystemfan.fans]
        for wakeup_time in heapq.merge(*wakeup_times):
            print(_json_dump_indented(pysystemfan.status()))
            time.sleep(wakeup_time - time.time())
    finally:
        for fan in pysystemfan.fans:
            fan.set_pwm(255)

if __name__ == "__main__":
    main()
