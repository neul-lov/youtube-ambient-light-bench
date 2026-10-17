#!/usr/bin/env python3
"""Static server for the benchmark pages plus a /log endpoint.

Pages POST JSON events (phase start/end and their own stats) to /log; each is appended to
EVENTS.jsonl with the server's receive time, which the sampler's timestamps line up with.
/watch serves the mock YouTube watch page, because the userscript only runs on that path.

Usage: server.py PORT EVENTS.jsonl   (serves the repository root, bound to 127.0.0.1)
"""
import http.server
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.abspath(sys.argv[2])


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.split("?")[0] == "/watch":
            self.path = "/userscript-ab/watch.html"
        return super().do_GET()

    def do_POST(self):
        if self.path != "/log":
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        with open(EVENTS, "a") as f:
            f.write(json.dumps({"t": time.time(), **json.loads(body)}) + "\n")
        self.send_response(204)
        self.end_headers()


http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
