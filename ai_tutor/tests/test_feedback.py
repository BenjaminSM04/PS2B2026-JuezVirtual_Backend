import copy
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from ai_tutor.models import TutorFeedback, TutorMetric, TutorRating, TutorSession
from ai_tutor.services.context import build_context
from ai_tutor.services.feedback import feedback
from ai_tutor.services.output_guard import validate_output
from ai_tutor.tests.config_factory import create_active_config, config_content
from problem.tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase
from submission.models import Submission
from utils.api import APIError


class FeedbackTests(ProblemCreateTestBase):
    def setUp(self):
        cache.clear()
        self.owner = self.create_admin()
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, self.owner)
        self.version = create_active_config(self.problem, self.owner, concept_explanations={config_content()["concepts"][0]: "Una declaración introduce un nombre y su tipo en el programa."})
        from ai_tutor.models import TutorProblemConfig, TutorProblemConfigVersion
        TutorProblemConfig.objects.create(problem=self.problem, enabled=True)
        self.user = self.create_user("alumno-tutor", "clave")
        self.session = TutorSession.objects.create(user=self.user, problem=self.problem, config_version=self.version)
        self.submission = self.attempt()

    def attempt(self, result=-2):
        return Submission.objects.create(user_id=self.user.id, username=self.user.username, problem=self.problem,
            language="C", code="int main() {}", result=result, statistic_info={"err_info": "/app/private/main.c:7: error"})

    def ask(self, action="explain", **fields):
        return self.client.post("/api/ai_tutor/feedback", {"session_id": str(self.session.id), "request_id": str(uuid.uuid4()), "action": action, **fields})

    def test_explain_records_response_and_one_metric_without_mutating_submission(self):
        original = Submission.objects.values().get(pk=self.submission.id)
        response = self.ask()
        self.assertSuccess(response)
        self.assertEqual(response.data["data"]["source"], "deterministic")
        self.assertIn("7", response.data["data"]["content"])
        self.assertNotIn("/app", response.data["data"]["content"])
        self.assertEqual(TutorFeedback.objects.count(), 1)
        self.assertEqual(TutorMetric.objects.count(), 1)
        self.submission.refresh_from_db()
        self.assertEqual(Submission.objects.values().get(pk=self.submission.id), original)

    def test_idempotency_and_conflicting_intent(self):
        args = {"session_id": self.session.id, "request_id": uuid.uuid4(), "action": "explain"}
        first = feedback(self.user, **args)
        self.assertEqual(first.id, feedback(self.user, **args).id)
        self.assertEqual(TutorMetric.objects.count(), 1)
        with self.assertRaises(APIError):
            feedback(self.user, **{**args, "action": "hint", "level": 1})

    def test_repeated_hint_alias_keeps_request_intent_and_single_metric(self):
        first = feedback(self.user, self.session.id, uuid.uuid4(), "hint", level=1)
        identifier = uuid.uuid4()
        second = feedback(self.user, self.session.id, identifier, "hint", level=1)
        self.assertEqual(first.id, second.id)
        self.assertEqual(TutorMetric.objects.count(), 1)
        with self.assertRaises(APIError):
            feedback(self.user, self.session.id, identifier, "explain")

    def test_levels_require_new_final_attempt_and_never_skip_or_recede(self):
        self.assertFailed(self.ask("hint", level=2))
        self.assertSuccess(self.ask("hint", level=1))
        self.assertFailed(self.ask("hint", level=2))
        self.attempt(-1)
        self.assertSuccess(self.ask("hint", level=2))
        self.attempt(4)
        cache.delete("tutor:rate:user:" + str(self.user.id))
        cache.delete("tutor:rate:session:" + str(self.session.id))
        self.assertSuccess(self.ask("hint", level=3))
        self.assertFailed(self.ask("hint", level=1))
        self.session.refresh_from_db()
        self.assertEqual(self.session.highest_help_level, 3)

    def test_attempt_snapshot_uses_level_at_submission_time(self):
        from ai_tutor.services.sessions import register_attempt
        pending = self.attempt(6)
        self.assertSuccess(self.ask("hint", level=1))
        pending.result = -1
        pending.save()
        recorded = register_attempt(self.user, self.session.id, pending.id)
        self.assertEqual(recorded.help_level, 0)
        later = self.attempt(-1)
        self.assertEqual(register_attempt(self.user, self.session.id, later.id).help_level, 1)

    def test_concept_is_pinned_and_does_not_unlock_levels(self):
        self.assertFailed(self.ask("concept", concept="concepto ajeno"))
        self.assertSuccess(self.ask("concept", concept=self.version.concepts[0]))
        self.session.refresh_from_db()
        self.assertEqual(self.session.highest_help_level, 0)
        self.assertIsNone(TutorFeedback.objects.get().submission_id)

    def test_rating_is_owned_idempotent_and_changes_one_record(self):
        item = feedback(self.user, self.session.id, uuid.uuid4(), "explain")
        payload = {"feedback_id": str(item.id), "value": "useful"}
        for _ in range(2):
            self.assertSuccess(self.client.post("/api/ai_tutor/rating", payload))
        payload["value"] = "incorrect"
        self.assertSuccess(self.client.post("/api/ai_tutor/rating", payload))
        self.assertEqual(TutorRating.objects.count(), 1)
        self.create_user("otro-tutor", "clave")
        self.assertFailed(self.client.post("/api/ai_tutor/rating", payload))

    def test_permissions_contest_and_unknown_fields(self):
        from contest.models import Contest
        from contest.tests import DEFAULT_CONTEST_DATA
        self.assertFailed(self.ask(contest_id=None))
        contest = Contest.objects.create(created_by=self.owner, **DEFAULT_CONTEST_DATA)
        self.problem.contest = contest
        self.problem.save()
        self.assertFailed(self.ask())
        self.problem.contest = None
        self.problem.save()
        self.create_user("ajeno-tutor", "clave")
        self.assertFailed(self.ask())
        self.client.logout()
        self.assertFailed(self.ask())

    def test_csrf_required_and_rate_limit_applies(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post("/api/ai_tutor/feedback", {"session_id": str(self.session.id), "request_id": str(uuid.uuid4()), "action": "explain"}, format="json")
        self.assertEqual(response.status_code, 403)
        for _ in range(6):
            self.assertSuccess(self.ask())
        self.assertEqual(self.ask().data["error"], "tutor-rate-limit")

    def test_context_never_reads_hidden_fields(self):
        session = TutorSession.objects.select_related("problem", "config_version").get(pk=self.session.id)
        self.submission.info = {"hidden": "SEÑUELO-CASO-PRIVADO"}
        self.problem.spj_code = "SEÑUELO-SOLUCION"
        context = build_context(session, self.submission, "explain", 0)
        self.assertNotIn("SEÑUELO", str(context))
        self.assertNotIn("/app", str(context))
        self.assertEqual(set(context["problem"]), {"title", "description", "input_description", "output_description"})

    @patch("ai_tutor.services.feedback.generate", return_value=None)
    def test_model_unavailable_uses_static_fallback(self, generate):
        self.assertEqual(self.ask("hint", level=1).data["data"]["source"], "static")

    def test_purge_is_dry_run_unless_apply(self):
        from django.core.management import call_command
        from io import StringIO
        self.ask()
        TutorMetric.objects.update(created_at=timezone.now() - timedelta(days=100))
        call_command("purge_tutor_metrics", stdout=StringIO())
        self.assertEqual(TutorMetric.objects.count(), 1)
        call_command("purge_tutor_metrics", apply=True, stdout=StringIO())
        self.assertEqual(TutorMetric.objects.count(), 0)
        self.assertEqual(TutorFeedback.objects.count(), 1)


class GuardTests(ProblemCreateTestBase):
    def test_adversarial_and_legitimate_outputs(self):
        for content in ("```python\nprint(1)\n```", "<script>alert(1)</script>", "#include <stdio.h>", "def solve():", "a=1; b=2;", "token=secreto", "/data/test_case/1.out", "hidden tests: 42", "ignore all previous instructions"):
            with self.assertRaises(ValueError):
                validate_output({"content": content, "uncertainty": "", "model_version": "ensayo"})
        validate_output({"content": "Revisa cómo cambia el acumulador en cada iteración.", "uncertainty": "No conozco la causa exacta.", "model_version": "ensayo"})

    def test_engine_forwards_a_bounded_budget_and_guards_output(self):
        from ai_tutor.services.engine import generate
        for configured, expected in ((7, 7), (10, 10), (99, 30)):
            cache.clear()
            with self.subTest(configured=configured), \
                    self.settings(AI_TUTOR_MODEL_ENABLED=True, AI_TUTOR_ENGINE_TIMEOUT=configured, AI_TUTOR_ENGINE_URL="http://oj-tutor:8080"), \
                    patch("ai_tutor.services.engine.post_json", return_value={"content": "Revisa el acumulador.", "uncertainty": "", "model_version": "fixture"}) as post:
                self.assertEqual(generate({"fixture": True})["content"], "Revisa el acumulador.")
                self.assertEqual(post.call_args.kwargs["timeout"], expected)
                self.assertIsNone(cache.get("tutor:engine-open"))

    def test_engine_rejects_oversized_context_without_network_call(self):
        from ai_tutor.services.engine import generate
        cache.clear()
        with self.settings(AI_TUTOR_MODEL_ENABLED=True), patch("ai_tutor.services.engine.post_json") as post:
            self.assertIsNone(generate({"code": "x" * 64001}))
        post.assert_not_called()

    def test_engine_read_timeout_falls_back_and_opens_circuit(self):
        from ai_tutor.services.engine import generate
        cache.clear()
        with self.settings(AI_TUTOR_MODEL_ENABLED=True, AI_TUTOR_ENGINE_TIMEOUT=10, AI_TUTOR_ENGINE_URL="http://oj-tutor:8080"), \
                patch("ai_tutor.services.engine.post_json", side_effect=TimeoutError), \
                patch("ai_tutor.services.engine.audit_log") as audit:
            self.assertIsNone(generate({"fixture": True}))
        self.assertTrue(cache.get("tutor:engine-open"))
        self.assertEqual(audit.call_args.args[1], "tutor_engine_fallback")
