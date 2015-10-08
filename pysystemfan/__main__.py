import contextlib
import logging
import time

from . import controler
from . import util

def main():
    c = controler.Controler()

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
