#!/usr/bin/env python3

import heapq
import shlex
import json
import collections
import time

def _json_dump_compact(data):
    return json.dumps(data, indent=None, separators=",:")

def _json_dump_indented(data):
    return json.dumps(data, indent=4, separators=(",", ": "))

class PySystemFan:
    _params = [
        ("sleep_time", 30, "How long to sleep between updates (seconds)."),
        ("status_server_port", 9191, "Port on which to listen for HTTP status updates. Set to 0 to disable server."),
        ("status_server_bind", "localhost", "Address to bind for status server."),
    ]

    def __init__(self):
        with open("pysystemfan.json", "r") as fp:
            config = json.load(fp)

        _process_params(self, config)

        self.fans = [Fan(self.sleep_time, **fan_params) for fan_params in config["fans"]]

    def status(self):
        return {
            "timestamp": time.time(),
            "fans": [fan.status() for fan in self.fans]
        }

    def config(self):
        ret = _dump_params(self)
        ret["fans"] = [fan.config() for fan in self.fans]
        return ret

if __name__ == "__main__":
    main()
