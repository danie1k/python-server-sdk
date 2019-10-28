from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from queue import Queue
from six import iteritems
import socket
from threading import Thread

def get_available_port():
    s = socket.socket(socket.AF_INET, type = socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    _, port = s.getsockname()
    s.close()
    return port

def start_server():
    sw = MockServerWrapper(get_available_port())
    sw.start()
    return sw

class MockServerWrapper(Thread):
    def __init__(self, port):
        Thread.__init__(self)
        self.port = port
        self.uri = 'http://localhost:%d' % port
        self.server = HTTPServer(('localhost', port), MockServerRequestHandler)
        self.server.server_wrapper = self
        self.matchers = {}
        self.requests = Queue()
    
    def close(self):
        self.server.shutdown()
        self.server.server_close()
    
    def run(self):
        self.server.serve_forever()
    
    def setup_response(self, uri_path, status, body = None, headers = None):
        self.matchers[uri_path] = MockServerResponse(status, body, headers)

    def setup_json_response(self, uri_path, data, headers = None):
        final_headers = {} if headers is None else headers.copy()
        final_headers['Content-Type'] = 'application/json'
        return self.setup_response(uri_path, 200, json.dumps(data), headers)

    def await_request(self):
        return self.requests.get()
    
    def require_request(self):
        return self.requests.get(block=False)
    
    # enter/exit magic methods allow server to be auto-closed by "with" statement
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

class MockServerRequestHandler(BaseHTTPRequestHandler):
    # def __init__(self, server_wrapper, request, client_address, server):
    #     self.server_wrapper = server_wrapper
    #     BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def do_GET(self):
        self._do_request('GET')

    def do_POST(self):
        self._do_request('POST')

    def _do_request(self, method):
        server_wrapper = self.server.server_wrapper
        server_wrapper.requests.put(MockServerRequest(method, self.path, self.headers))
        if self.path in server_wrapper.matchers:
            resp = server_wrapper.matchers[self.path]
            self.send_response(resp.status)
            if resp.headers is not None:
                for key, value in iteritems(resp.headers):
                    self.send_header(key, value)
            self.end_headers()
            if resp.body is not None:
                self.wfile.write(resp.body)
        else:
            self.send_error(404)

class MockServerRequest(object):
    def __init__(self, method, path, headers):
        self.method = method
        self.path = path
        self.headers = headers

class MockServerResponse(object):
    def __init__(self, status, body, headers):
        self.status = status
        self.body = body
        self.headers = headers
