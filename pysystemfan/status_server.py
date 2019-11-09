from . import config_params
from . import util

import http.server
import threading
import json
import logging

logger = logging.getLogger(__name__)

_not_set = object()

class StatusServer(config_params.Configurable):
    _params = [
        ("port", _not_set, "Port where to serve the status page. Default is to not run a server."),
        ("bind", "127.0.0.1", "Address to bind to"),
        ("status_path", "/status.json", "Path of the status file on the server")
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        self._data = {} # Storage for the exported data that are being processed (inactive yet)
        self._active_data = {} # Storage for the exported data that are being served

    def __enter__(self):
        if self.port is not _not_set:
            self.start()
        return self

    def __exit__(self, *args):
        if self.port is not _not_set:
            self.stop()

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def update(self):
        self._active_data = self._data

    def start(self):
        path = self.status_path
        instance = self # Local copy for handler
        address = (self.bind, self.port)
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    if self.path == path:
                        document = json.dumps(instance._active_data, indent=2).encode("utf-8")

                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self.send_header("Content-length", len(document))
                        self.end_headers()
                        self.wfile.write(document)
                    else:
                        self.send_error(404)
                except Exception as e:
                    logger.exception("Exception in handler")

            def log_error(self, msg, *args):
                logger.warning("%s: " + msg, self.client_address[0], *args)

            def log_message(self, msg, *args):
                logger.debug("%s: " + msg, self.client_address[0], *args)

        self._server = http.server.HTTPServer(address, Handler)
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        name="Status HTTP")

        logger.info("Starting server at %s", address)
        self._thread.start()

    def stop(self):
        logger.debug("Waiting for server to shut down")
        self._server.shutdown()
        self._thread.join()
        logger.info("Server stopped")
