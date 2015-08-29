from . import config_params

import threading
import http.server
import json

class StatusServer(config_params.Configurable):
    _params = [
        ("enabled", "", "If empty (the default), the status server is disabled."),
        ("port", 9191, "Port to listen on."),
        ("bind", "127.0.0.1", "Address to bind to. Empty to bind to all interfaces."),
    ]

    def __init__(self, parent, params):
        self.process_params(params)
        self._http_server = None
        self._thread = None
        self._callback = None

    def set_status_callback(self, callback):
        self._callback = callback

    def __enter__(self):
        if self.enabled == "":
            return self

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

def _handler_factory(status_server):
    callback = status_server._callback
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            string = json.dumps(callback())
            encoded = string.encode("utf-8")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(encoded)

    return Handler
