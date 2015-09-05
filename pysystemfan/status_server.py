from . import config_params

import threading
import http.server
import json
import logging

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
        self._callback = None
        self._logger = logging.getLogger(__name__)
        self._request_level = logging.getLevelName(self.request_log_level)

    def set_status_callback(self, callback):
        self._callback = callback

    def __enter__(self):
        if self.enabled == "":
            return self

        self._logger.info("Starting HTTP status server on %s:%d", self.bind, self.port)

        self._http_server = http.server.HTTPServer((self.bind, self.port),
                                                   _handler_factory(self))
        self._thread = threading.Thread(target=self._http_server.serve_forever,
                                        name="status server")

        self._thread.start()
        return self

    def __exit__(self, *args):
        if self.enabled == "":
            return

        self._http_server.shutdown()
        self._thread.join()

        self._logger.info("Status server stopped")

def _handler_factory(status_server):
    callback = status_server._callback
    logger = status_server._logger
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
            string = json.dumps(callback())
            encoded = string.encode("utf-8")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(encoded)


    return Handler
