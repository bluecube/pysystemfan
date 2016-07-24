import contextlib
import logging
import argparse
import time

from . import controler
from . import util

def main():
    c = controler.Controler()

    try:
        with contextlib.ExitStack() as stack:
            stack.callback(c.full_steam)
            stack.enter_context(util.Interrupter())

            prev_time = time.time()
            while True:
                time.sleep(c.update_time)
                t = time.time()
                dt = t - prev_time
                c.update(t - prev_time)
                prev_time = t
    except:
        logging.getLogger(__name__).exception("Unhandled exception")


if __name__ == "__main__":
    main()
