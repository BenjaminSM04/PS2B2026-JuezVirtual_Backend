"""Sugerencias para el docente: motor simulado, sin modelos ni datos reales."""
import http.client
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from account.models import AdminType, ProblemPermission
from ai_tutor.models import TutorProblemConfigVersion
from ai_tutor.serializers import ConfigContentSerializer
from ai_tutor.services.engine import suggest
from contest.models import Contest
from contest.tests import DEFAULT_CONTEST_DATA
from problem.models import Problem
from problem.tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase
from utils.api import APIError

ENGINE_REPLY = {
    "concepts": [
        {"name": "Lectura de enteros", "explanation": "Antes de operar hay que leer cada valor con el tipo adecuado."},
        {"name": "Acumulador", "explanation": "Una variable que guarda el resultado parcial mientras se recorren los datos."},
    ],
    "hints": {
        "concept": "¿Qué tipo de dato necesitas para guardar la suma?",
        "location": "Revisa cómo declaras las variables que reciben la lectura.",
        "strategy": "Compara el rango de los valores con el rango del tipo elegido.",
    },
}
UNAVAILABLE = "tutor-suggest-unavailable"


class SuggestionAPITests(ProblemCreateTestBase):
    def setUp(self):
        cache.clear()
        self.owner = self.create_admin()
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, self.owner)
        self.url = "/api/admin/ai_tutor/config/suggest"
        self.enabled = self.settings(AI_TUTOR_MODEL_ENABLED=True, AI_TUTOR_ENGINE_TIMEOUT=7, AI_TUTOR_SUGGEST_TIMEOUT=77,
                                     AI_TUTOR_ENGINE_URL="http://oj-tutor:8080")
        self.enabled.enable()
        self.addCleanup(self.enabled.disable)

    def ask(self, **fields):
        return self.client.post(self.url, {"problem_id": self.problem.id, **fields})

    def engine(self, reply=None, **kwargs):
        return patch("ai_tutor.services.engine.post_json", return_value=ENGINE_REPLY if reply is None else reply, **kwargs)

    def test_returns_reviewable_content_without_saving_anything(self):
        with self.engine() as post:
            response = self.ask()
        self.assertSuccess(response)
        data = response.data["data"]
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["concepts"], ["Lectura de enteros", "Acumulador"])
        self.assertEqual(data["concept_explanations"]["Acumulador"], ENGINE_REPLY["concepts"][1]["explanation"])
        self.assertEqual(data["hint_policy"], {"max_help_level": 3, "hints": ENGINE_REPLY["hints"]})
        self.assertTrue(ConfigContentSerializer(data=data).is_valid())
        self.assertFalse(TutorProblemConfigVersion.objects.exists())
        self.assertEqual(post.call_args.args[0], "http://oj-tutor:8080/suggest")
        # Plazo propio de la sugerencia, no el de las observaciones.
        self.assertEqual(post.call_args.kwargs["timeout"], 77)
        # El borrador se guarda con el flujo existente de versiones.
        saved = self.client.post("/api/admin/ai_tutor/config/versions", {"problem_id": self.problem.id, **data})
        self.assertSuccess(saved)
        self.assertEqual(saved.data["data"]["status"], "draft")

    def test_engine_receives_only_bounded_public_redacted_text(self):
        Problem.objects.filter(pk=self.problem.pk).update(
            title="Suma", description="<p>Contacto docente@ejemplo.com " + "largo " * 600 + "</p>",
            input_description="<b>Dos</b> enteros &amp; token=secreto", output_description="La suma.",
            samples=[{"input": "1 2", "output": "3"}, {"input": "docente@ejemplo.com\n" + "9" * 500, "output": "4"}, {"input": "5", "output": "6"}])
        with self.engine() as post:
            self.assertSuccess(self.ask())
        problem = json.loads(post.call_args.args[1])["problem"]
        self.assertEqual(set(problem), {"title", "description", "input_description", "output_description", "samples"})
        self.assertTrue(1190 < len(problem["description"]) <= 1200)
        self.assertTrue(problem["description"].endswith("…"))
        self.assertNotIn("<", str(problem))
        self.assertNotIn("docente@ejemplo.com", str(problem))
        self.assertNotIn("secreto", str(problem))
        self.assertEqual(len(problem["samples"]), 2)
        self.assertEqual(problem["samples"][0], {"input": "1 2", "output": "3"})
        self.assertLessEqual(len(problem["samples"][1]["input"]), 300)
        self.assertIn("\n", problem["samples"][1]["input"])

    def test_requires_the_model_to_be_enabled(self):
        for flag in (False, None):
            with self.subTest(flag=flag), self.settings(AI_TUTOR_MODEL_ENABLED=flag), self.engine() as post:
                response = self.ask()
                self.assertEqual(response.data["error"], UNAVAILABLE)
                self.assertIn("no están activadas", response.data["data"])
                post.assert_not_called()

    def test_engine_failures_are_reported_without_opening_the_student_circuit(self):
        for failure in (TimeoutError, ConnectionRefusedError, ValueError("http-status"), http.client.IncompleteRead(b"")):
            cache.delete("tutor:suggest:user:" + str(self.owner.id))
            with self.subTest(failure=failure), patch("ai_tutor.services.engine.post_json", side_effect=failure):
                response = self.ask()
                self.assertEqual(response.data["error"], UNAVAILABLE)
                self.assertIn("Inténtalo de nuevo", response.data["data"])
        self.assertIsNone(cache.get("tutor:engine-open"))

    def test_malformed_engine_replies_are_rejected_by_the_config_schema(self):
        concept = ENGINE_REPLY["concepts"][0]
        hints = ENGINE_REPLY["hints"]
        replies = [[], {}, {"concepts": [], "hints": hints}, {"concepts": ["x"], "hints": hints}, {"concepts": [{"name": "x"}], "hints": hints},
                   {"concepts": [concept, {**concept, "name": concept["name"].upper()}], "hints": hints},
                   {"concepts": [{**concept, "explanation": "e" * 2001}], "hints": hints},
                   {"concepts": [concept], "hints": {**hints, "location": hints["concept"]}},
                   {"concepts": [concept], "hints": {"concept": "a", "location": "b"}}]
        for reply in replies:
            cache.delete("tutor:suggest:user:" + str(self.owner.id))
            with self.subTest(reply=reply), self.engine(reply):
                self.assertEqual(self.ask().data["error"], UNAVAILABLE)

    def test_permissions_follow_problem_versions(self):
        with self.engine() as post:
            self.create_user("alumno", "clave")
            self.assertFailed(self.ask())
            self.create_user("docente-sin-permiso", "clave", admin_type=AdminType.ADMIN, problem_permission=ProblemPermission.NONE)
            self.assertFailed(self.ask())
            self.create_admin("otro-docente", "clave")
            self.assertFailed(self.ask(), "Problem does not exist")
            self.client.logout()
            self.assertFailed(self.ask())
            post.assert_not_called()
            self.create_super_admin()
            self.assertSuccess(self.ask())
            self.client.login(username="admin", password="admin")
            self.assertSuccess(self.ask())

    def test_contest_unknown_problem_and_unknown_fields_are_rejected(self):
        with self.engine() as post:
            self.assertFailed(self.client.post(self.url, {"problem_id": self.problem.id + 1000}))
            self.assertFailed(self.client.post(self.url, {"problem_id": "x"}))
            self.assertFailed(self.client.post(self.url, {}))
            self.assertFailed(self.ask(extra=1))
            contest = Contest.objects.create(created_by=self.owner, **DEFAULT_CONTEST_DATA)
            Problem.objects.filter(pk=self.problem.pk).update(contest=contest)
            self.assertEqual(self.ask().data["error"], "tutor-contest-blocked")
            post.assert_not_called()

    def test_problem_without_statement_does_not_call_the_model(self):
        Problem.objects.filter(pk=self.problem.pk).update(title="", description="<p> </p>")
        with self.engine() as post:
            self.assertEqual(self.ask().data["error"], "tutor-suggest-empty")
        post.assert_not_called()

    def test_each_user_may_ask_six_times_per_minute(self):
        with self.engine() as post:
            for _ in range(6):
                self.assertSuccess(self.ask())
            blocked = self.ask()
            self.assertEqual(blocked.data["error"], "tutor-rate-limit")
            self.assertEqual(post.call_count, 6)
            self.create_super_admin()
            self.assertSuccess(self.ask())

    def test_audit_records_outcome_without_the_generated_text(self):
        with patch("ai_tutor.services.suggestions.audit_log") as audit:
            with self.engine():
                self.assertSuccess(self.ask())
            with patch("ai_tutor.services.engine.post_json", side_effect=TimeoutError):
                self.assertFailed(self.ask())
        self.assertEqual([call.args[1] for call in audit.call_args_list], ["tutor_config_suggested", "tutor_config_suggest_failed"])
        self.assertEqual(audit.call_args_list[0].args[2:4], ("Problem", self.problem.id))
        self.assertEqual(audit.call_args_list[0].args[4], {"concepts": 2})
        self.assertNotIn("Acumulador", str(audit.call_args_list))

    def test_keeps_csrf_protection(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="admin", password="admin"))
        self.assertEqual(client.post(self.url, {"problem_id": self.problem.id}, format="json").status_code, 403)


class SuggestEngine(BaseHTTPRequestHandler):
    status = 200
    delay = 0.0
    seen = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        SuggestEngine.seen.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
        body = json.dumps(ENGINE_REPLY if self.status == 200 else {"error": "unavailable"}).encode()
        time.sleep(self.delay)
        try:
            self.send_response(self.status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass


class SuggestEngineHTTPTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SuggestEngine)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        SuggestEngine.status, SuggestEngine.delay, SuggestEngine.seen = 200, 0.0, []

    def call_engine(self, timeout=2):
        with self.settings(AI_TUTOR_MODEL_ENABLED=True, AI_TUTOR_ENGINE_TIMEOUT=10, AI_TUTOR_SUGGEST_TIMEOUT=timeout,
                           AI_TUTOR_ENGINE_URL="http://127.0.0.1:%s" % self.server.server_port):
            return suggest({"title": "Suma", "samples": []})

    def test_posts_the_problem_to_the_suggest_route(self):
        self.assertEqual(self.call_engine(), ENGINE_REPLY)
        self.assertEqual(SuggestEngine.seen, [("/suggest", {"problem": {"title": "Suma", "samples": []}})])

    def test_engine_rejection_and_slow_generation_become_unavailable(self):
        SuggestEngine.status = 503
        with self.assertRaises(APIError) as rejected:
            self.call_engine()
        self.assertEqual(rejected.exception.err, UNAVAILABLE)
        SuggestEngine.status, SuggestEngine.delay = 200, 1.5
        started = time.monotonic()
        with self.assertRaises(APIError) as slow:
            self.call_engine(timeout=1)
        self.assertEqual(slow.exception.err, UNAVAILABLE)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertIsNone(cache.get("tutor:engine-open"))

    def test_slow_generation_beyond_the_observation_budget_is_accepted(self):
        SuggestEngine.delay = 1.5
        with self.settings(AI_TUTOR_MODEL_ENABLED=True, AI_TUTOR_ENGINE_TIMEOUT=1, AI_TUTOR_SUGGEST_TIMEOUT=4,
                           AI_TUTOR_ENGINE_URL="http://127.0.0.1:%s" % self.server.server_port):
            self.assertEqual(suggest({"title": "Suma", "samples": []}), ENGINE_REPLY)

    def test_suggest_budget_is_not_capped_like_the_observation_one(self):
        with self.settings(AI_TUTOR_MODEL_ENABLED=True, AI_TUTOR_ENGINE_TIMEOUT=30, AI_TUTOR_SUGGEST_TIMEOUT=100,
                           AI_TUTOR_ENGINE_URL="http://oj-tutor:8080"), patch("ai_tutor.services.engine.post_json", return_value=ENGINE_REPLY) as post:
            suggest({"title": "Suma", "samples": []})
        self.assertEqual(post.call_args.kwargs["timeout"], 100)
