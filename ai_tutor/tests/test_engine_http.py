"""Plazos con HTTP real en loopback; no usa modelos ni datos reales."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

from django.core.cache import cache
from django.test import SimpleTestCase

from ai_tutor.services.engine import generate


class DelayedEngine(BaseHTTPRequestHandler):
    header_delay = 0.7
    body_delay = 0.7

    def log_message(self, *args):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        body = json.dumps({"content": "Revisa el acumulador.", "uncertainty": "", "model_version": "fixture"}).encode()
        try:
            time.sleep(self.header_delay)
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            time.sleep(self.body_delay)
            self.wfile.write(body)
        except OSError:
            pass


class EngineHTTPTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), DelayedEngine)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        DelayedEngine.header_delay, DelayedEngine.body_delay = 0.7, 0.7

    def call_engine(self):
        with self.settings(AI_TUTOR_MODEL_ENABLED=True, AI_TUTOR_ENGINE_TIMEOUT=1,
                           AI_TUTOR_ENGINE_URL="http://127.0.0.1:%s" % self.server.server_port):
            return generate({"fixture": True})

    def test_late_headers_do_not_grant_another_body_budget(self):
        started = time.monotonic()
        self.assertIsNone(self.call_engine())
        self.assertLess(time.monotonic() - started, 1.25)
        self.assertTrue(cache.get("tutor:engine-open"))

    def test_slow_generation_within_budget_is_accepted(self):
        DelayedEngine.header_delay, DelayedEngine.body_delay = 0.6, 0.1
        self.assertEqual(self.call_engine()["content"], "Revisa el acumulador.")
        self.assertIsNone(cache.get("tutor:engine-open"))
