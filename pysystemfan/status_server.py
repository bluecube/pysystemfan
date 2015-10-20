from . import config_params

import threading
import http.server
import json
import logging
import os.path
import shutil

logger = logging.getLogger(__name__)

class StatusServer(config_params.Configurable):
    _params = [
        ("enabled", "", "If empty (the default), the status server is disabled."),
        ("port", 9191, "Port to listen on."),
        ("bind", "127.0.0.1", "Address to bind to. Empty to bind to all interfaces."),
        ("request_log_level", "INFO", "To which level should requests be logged. "
                                      "One of DEBUG, INFO, WARNING, ERROR, CRITICAL"),
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        self._http_server = None
        self._thread = None
        self._status_callback = None
        self._history_callback = None
        self._request_level = logging.getLevelName(self.request_log_level)

    def set_status_callback(self, callback):
        self._status_callback = callback

    def set_history_callback(self, callback):
        self._history_callback = callback

    def __enter__(self):
        if self.enabled == "":
            return self

        logger.info("Starting HTTP status server on %s:%d", self.bind, self.port)

        self._http_server = http.server.HTTPServer((self.bind, self.port),
                                                   _handler_factory(self))
        self._thread = threading.Thread(target=self._http_server.serve_forever,
                                        name="status server",
                                        daemon=True)

        self._thread.start()
        return self

    def __exit__(self, *ex_info):
        if self._thread is None:
            assert self._http_server is None
            return False

        self._http_server.shutdown()
        self._thread.join()

        logger.info("Status server stopped")

        return False

def _handler_factory(status_server):
    status_callback = status_server._status_callback
    history_callback = status_server._history_callback
    request_level = status_server._request_level

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_error(self, fmt, *args):
            self._log(logging.ERROR, fmt, *args)

        def log_request(self, code='-', size='-'):
            self._log(request_level, '"%s" %s %s',
                      self.requestline, str(code), str(size))

        def log_message(self, fmt, *args):
            self._log(logging.INFO, fmt, *args)

        def _log(self, log_level, fmt, *args):
            logger.log(log_level, "%s - " + fmt, self.address_string(), *args)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()

                dirname = os.path.dirname(__file__)
                with open(os.path.join(dirname, "status.html"), "rb") as fp:
                    shutil.copyfileobj(fp, self.wfile)
            elif self.path in ("/status.json"):
                string = json.dumps(status_callback())
                encoded = string.encode("utf-8")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(encoded)
            elif self.path in ("/history.json"):
                string = json.dumps(history_callback())
                encoded = string.encode("utf-8")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(encoded)
            else:
                self.send_error(404)

    return Handler
