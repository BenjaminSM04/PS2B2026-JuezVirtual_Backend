"""Regresiones de integridad del motor, sin descargar ni aprobar modelos."""
import hashlib
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest import mock
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODULES = (("guard", "ai_tutor/services/output_guard.py"), ("classifier_runtime", "ai_tutor/ml/runtime.py"),
           ("bounded_http", "utils/bounded_http.py"), ("tutor_prompt", "ai_tutor/ml/prompt.py"), ("tutor_server", "tutor_engine/server.py"))
for module, file in MODULES:
    spec = importlib.util.spec_from_file_location(module, ROOT / file)
    instance = importlib.util.module_from_spec(spec)
    sys.modules[module] = instance
    spec.loader.exec_module(instance)
server = sys.modules["tutor_server"]


class IntegrityTests(unittest.TestCase):
    def test_technical_artifact_is_rejected_by_default_and_requires_synthetic_classifier(self):
        with TemporaryDirectory() as temp:
            old_root = server.ROOT
            self.addCleanup(setattr, server, "ROOT", old_root)
            server.ROOT = Path(temp)
            (server.ROOT / "model.gguf").write_bytes(b"fixture-not-a-real-model")
            classifier = server.ROOT / "classifier.json"
            classifier.write_text(json.dumps({"dataset_version": "fixture", "scope": "technical-demo"}))

            def entry(path):
                return {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            manifest = {"scope": "technical-demo", "decision": "demonstration", "human_review": "not-performed",
                        "license": "fixture", "model_revision": "a" * 40, "dataset_version": "fixture",
                        "generator": entry(server.ROOT / "model.gguf"), "classifier": entry(classifier)}
            (server.ROOT / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                server.load_artifacts()
            self.assertEqual(server.load_artifacts(technical_demo=True)[0]["scope"], "technical-demo")

    def test_only_exact_model_path_can_be_approved(self):
        with TemporaryDirectory() as temp:
            server.ROOT = Path(temp)
            approved = server.ROOT / "approved"
            approved.mkdir()
            (approved / "model.gguf").write_bytes(b"synthetic-reviewed-fixture")
            (server.ROOT / "model.gguf").write_bytes(b"synthetic-unreviewed-fixture")
            classifier = server.ROOT / "classifier.json"
            classifier.write_text(json.dumps({"dataset_version": "fixture"}))

            def entry(path):
                return {"file": str(path.relative_to(server.ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            manifest = {"decision": "integrate", "reviewer": "fixture-reviewer", "trained_by": "fixture-author", "reviewed_at": "2026-01-01",
                        "license": "fixture", "model_revision": "fixture", "dataset_version": "fixture",
                        "generator": entry(approved / "model.gguf"), "classifier": entry(classifier)}
            (server.ROOT / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                server.load_artifacts()

    def test_inline_and_multiline_programs_are_rejected(self):
        for text in ("a,b=map(int,open(0).read().split()); print(a+b)",
                     'x = __import__("sys").stdin.read(); __import__("sys").stdout.write(str(sum(map(int,x.split()))))',
                     "a,b=map(int,open(0).read().split())\nprint(a+b)",
                     "Observa el siguiente paso: console.log(a + b)",
                     "Revisa esto: System.out.println(a+b);"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                server.validate_output({"content": text, "uncertainty": "", "model_version": "fixture"})


class FakeModel(BaseHTTPRequestHandler):
    """llama.cpp sin streaming: cabeceras solo al terminar de generar (o goteo tras ellas)."""
    delay = 0.0
    drip = False
    staged = False
    header_drip = False
    body = json.dumps({"choices": [{"message": {"content": json.dumps(
        {"content": "Revisa cómo cambia el acumulador en cada iteración.", "uncertainty": "", "model_version": "x"})}}]}).encode()

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        try:
            if self.header_drip:
                self.wfile.write(b"HTTP/1.0 200 OK\r\nX-Fixture: ")
                self.wfile.flush()
                for _ in range(20):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.2)
                return
            if self.drip:
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.end_headers()
                for _ in range(100):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.3)
                return
            time.sleep(self.delay)
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.body)))
            self.end_headers()
            if self.staged:
                time.sleep(0.7)
            self.wfile.write(self.body)
        except OSError:
            pass  # el motor cortó antes: es el caso esperado en las pruebas de exceso


def serve(handler):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class TimeoutTests(unittest.TestCase):
    """Regresión: el timeout de socket no puede ser más corto que la generación."""

    def setUp(self):
        self.model = serve(FakeModel)
        self.engine = serve(server.Handler)
        saved = (server.MODEL_URL, server.MODEL_TIMEOUT_S, server.ARTIFACTS, server.predict)
        self.addCleanup(lambda: (setattr(server, "MODEL_URL", saved[0]), setattr(server, "MODEL_TIMEOUT_S", saved[1]),
                                 setattr(server, "ARTIFACTS", saved[2]), setattr(server, "predict", saved[3])))
        for httpd in (self.engine, self.model):
            self.addCleanup(lambda httpd=httpd: (httpd.shutdown(), httpd.server_close()))
        server.MODEL_URL = "http://127.0.0.1:%d" % self.model.server_address[1]
        server.ARTIFACTS = ({"model_revision": "fixture"}, {})
        server.predict = lambda classifier, record: ("fixture", 0.5)
        FakeModel.delay, FakeModel.drip, FakeModel.staged = 0.0, False, False
        FakeModel.header_drip = False

    def feedback(self):
        context = {"schema_version": 1, "action": "hint", "level": 1, "concept": "c", "problem": {}, "code": "x", "language": "C",
                   "diagnostic": {}, "concepts": [], "history": [], "config_version": 1}
        request = urllib.request.Request("http://127.0.0.1:%d/v1/feedback" % self.engine.server_address[1], json.dumps(context).encode(),
                                         {"Content-Type": "application/json"})
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read()), time.monotonic() - started
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read()), time.monotonic() - started

    def test_slow_generation_within_budget_is_accepted(self):
        FakeModel.delay = 1.0  # con el timeout anterior de 0.5 s esto fallaba
        server.MODEL_TIMEOUT_S = 3
        status, data, _ = self.feedback()
        self.assertEqual(status, 200)
        self.assertEqual(data["model_version"], "fixture")

    def test_generation_over_budget_is_rejected(self):
        FakeModel.delay = 2.5
        server.MODEL_TIMEOUT_S = 1
        status, data, elapsed = self.feedback()
        self.assertEqual((status, data), (503, {"error": "unavailable"}))
        self.assertLess(elapsed, 2.0)

    def test_dripping_response_is_cut_by_total_deadline(self):
        FakeModel.drip = True  # cada lectura llega antes del timeout de socket
        server.MODEL_TIMEOUT_S = 1
        status, _, elapsed = self.feedback()
        self.assertEqual(status, 503)
        self.assertLess(elapsed, 2.0)

    def test_budget_configuration_is_validated(self):
        for raw, expected in (("8", 8.0), ("1", 1.0), ("30", 30.0), ("2.5", 2.5)):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"MODEL_TIMEOUT_S": raw}):
                self.assertEqual(server.model_timeout(), expected)
        with mock.patch.dict(os.environ):
            os.environ.pop("MODEL_TIMEOUT_S", None)
            self.assertEqual(server.model_timeout(), 8.0)
        for raw in ("0", "0.5", "31", "-1", "abc", "", "nan", "inf"):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"MODEL_TIMEOUT_S": raw}), self.assertRaises(ValueError):
                server.model_timeout()

    def test_late_headers_do_not_grant_another_body_budget(self):
        FakeModel.delay, FakeModel.staged = 0.7, True
        server.MODEL_TIMEOUT_S = 1
        status, _, elapsed = self.feedback()
        self.assertEqual(status, 503)
        self.assertLess(elapsed, 1.25)

    def test_integrated_model_uses_fixed_uncertainty(self):
        status, data, _ = self.feedback()
        self.assertEqual(status, 200)
        self.assertEqual(data["uncertainty"], server.UNCERTAINTY)

    def test_extra_learned_keys_are_dropped(self):
        original = FakeModel.body
        self.addCleanup(setattr, FakeModel, "body", original)
        FakeModel.body = json.dumps({"choices": [{"message": {"content": json.dumps(
            {"content": "Revisa cómo cambia el acumulador en cada iteración del ciclo.", "uncertainty": "x",
             "model_version": "adapter", "history": ["x"]})}}]}).encode()
        status, data, _ = self.feedback()
        self.assertEqual(status, 200)
        self.assertEqual(set(data), {"content", "uncertainty", "model_version"})

    def test_unhelpful_generations_fall_back(self):
        original = FakeModel.body
        self.addCleanup(setattr, FakeModel, "body", original)
        for content in ("Traza una línea y termina.",
                        "Aquí tienes una posible solución en C para este problema de enteros.",
                        "El código proporcionado es correcto y funciona para el caso público.",
                        "Check the loop because your counter should start at zero always."):
            with self.subTest(content=content):
                FakeModel.body = json.dumps({"choices": [{"message": {"content": json.dumps(
                    {"content": content, "uncertainty": "", "model_version": "x"})}}]}).encode()
                status, data, _ = self.feedback()
                self.assertEqual((status, data), (503, {"error": "unavailable"}))

    def test_dripping_headers_are_also_cut_by_total_deadline(self):
        FakeModel.header_drip = True
        server.MODEL_TIMEOUT_S = 1
        status, _, elapsed = self.feedback()
        self.assertEqual(status, 503)
        self.assertLess(elapsed, 1.25)


if __name__ == "__main__":
    unittest.main()
