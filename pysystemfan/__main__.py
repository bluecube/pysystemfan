import contextlib
import logging
import argparse

from . import controler
from . import util

def main():
    parser = argparse.ArgumentParser(description = "PySystemFan -- the overkill fan manager.")
    parser.add_argument("--outside-temperature", type=float,
                        help="Measured temperature outside the system.")
    args = parser.parse_args()

    c = controler.Controler(**{k: v for k, v in vars(args).items() if v is not None})

    try:
        with contextlib.ExitStack() as stack:
            stack.callback(c._full_steam)

            c.init()
            stack.callback(c.model.save)

            c.status_server.set_status_callback(c.get_status)
            c.status_server.set_history_callback(c.history.get_status)
            stack.enter_context(c.status_server)

            stack.enter_context(util.Interrupter())

            c.run()
    except:
        logging.getLogger(__name__).exception("Unhandled exception")


if __name__ == "__main__":
    main()
