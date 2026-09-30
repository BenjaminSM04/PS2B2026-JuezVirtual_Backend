from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from account.models import User
from ai_tutor.models import TutorAttempt, TutorProblemConfig, TutorSession
from ai_tutor.services.sessions import advance_help_level, create_or_recover, register_attempt
from contest.models import Contest
from contest.tests import DEFAULT_CONTEST_DATA
from problem.tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase
from submission.models import JudgeStatus, Submission


class TutorSessionTests(ProblemCreateTestBase):
    def setUp(self):
        self.owner = self.create_admin()
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, self.owner)
        TutorProblemConfig.objects.create(problem=self.problem, enabled=True)
        self.student = self.create_user("alumno", "clave")
        self.session_url = "/api/ai_tutor/session"
        self.attempt_url = "/api/ai_tutor/attempt"

    def start(self, **extra):
        response = self.client.post(self.session_url, {"problem_id": self.problem.id, **extra})
        self.assertSuccess(response)
        return response.data["data"]

    def submission(self, **extra):
        return Submission.objects.create(problem=self.problem, user_id=self.student.id, username=self.student.username,
                                         code="código original", language="C++", result=-1, info={"prueba": "original"},
                                         statistic_info={"time_cost": 12}, **extra)

    def attempt(self, session, submission, **extra):
        return self.client.post(self.attempt_url, {"session_id": session["id"], "submission_id": submission.id, **extra})

    def test_get_does_not_create_and_post_recovers_same_session_at_zero(self):
        response = self.client.get(self.session_url, {"problem_id": self.problem.id})
        self.assertSuccess(response)
        self.assertIsNone(response.data["data"])
        self.assertFalse(TutorSession.objects.exists())
        first, second = self.start(), self.start()
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["highest_help_level"], 0)
        self.assertEqual(second["attempts"], [])
        self.assertEqual(TutorSession.objects.count(), 1)

    def test_register_is_idempotent_and_preserves_every_submission_column(self):
        session = self.start()
        submission = self.submission()
        original = Submission.objects.filter(pk=submission.id).values().get()
        first, second = self.attempt(session, submission), self.attempt(session, submission)
        self.assertSuccess(first)
        self.assertSuccess(second)
        self.assertEqual(first.data["data"]["id"], second.data["data"]["id"])
        self.assertEqual(first.data["data"]["help_level"], 0)
        self.assertEqual(first.data["data"]["result"], -1)
        self.assertEqual(first.data["data"]["language"], "C++")
        self.assertEqual(TutorAttempt.objects.count(), 1)
        self.assertEqual(Submission.objects.filter(pk=submission.id).values().get(), original)
        self.assertNotIn("code", first.data["data"])
        with self.assertRaises(ProtectedError):
            submission.delete()

    def test_recovery_reconciles_final_but_not_old_pending_or_foreign_submissions(self):
        old = self.submission()
        session = self.start()
        final = self.submission()
        pending = self.submission()
        pending.result = JudgeStatus.PENDING
        pending.save()
        foreign = self.submission()
        foreign.user_id = self.owner.id
        foreign.save()
        recovered = self.start()
        self.assertEqual([a["submission_id"] for a in recovered["attempts"]], [final.id])
        self.assertEqual(recovered["attempt_count"], 1)
        self.assertNotIn(old.id, [a["submission_id"] for a in recovered["attempts"]])
        pending.result = JudgeStatus.ACCEPTED
        pending.save()
        self.assertEqual(self.start()["attempt_count"], 2)
        self.assertEqual(self.start()["attempt_count"], 2)
        self.assertEqual(session["id"], recovered["id"])

    def test_rejects_pending_judging_unknown_old_foreign_other_problem_and_contest(self):
        session = self.start()
        for result in (6, 7, 9):
            submission = self.submission()
            submission.result = result
            submission.save()
            self.assertFailed(self.attempt(session, submission))
        submission = self.submission()
        Submission.objects.filter(pk=submission.id).update(create_time=timezone.now() - timedelta(days=1))
        self.assertFailed(self.attempt(session, submission))
        submission = self.submission()
        submission.user_id = self.owner.id
        submission.save()
        self.assertFailed(self.attempt(session, submission))
        other = self.add_problem({**DEFAULT_PROBLEM_DATA, "_id": "otro"}, self.owner)
        submission = self.submission()
        submission.problem = other
        submission.save()
        self.assertFailed(self.attempt(session, submission))
        contest = Contest.objects.create(created_by=self.owner, **DEFAULT_CONTEST_DATA)
        submission = self.submission(contest=contest)
        self.assertFailed(self.attempt(session, submission))
        self.assertFalse(TutorAttempt.objects.exists())

    def test_other_user_cannot_read_or_use_session_even_as_admin(self):
        session = self.start()
        submission = self.submission()
        self.client.login(username="admin", password="admin")
        self.assertFailed(self.attempt(session, submission))
        response = self.client.get(self.session_url, {"problem_id": self.problem.id})
        self.assertSuccess(response)
        self.assertIsNone(response.data["data"])

    def test_level_cannot_be_set_by_client_and_internal_progress_never_decreases(self):
        self.assertFailed(self.client.post(self.session_url, {"problem_id": self.problem.id, "highest_help_level": 3}))
        session = self.start()
        submission = self.submission()
        self.assertFailed(self.attempt(session, submission, help_level=3))
        self.assertFailed(self.attempt(session, submission, result=0))
        current = TutorSession.objects.get(pk=session["id"])
        advance_help_level(current.id, 2)
        advance_help_level(current.id, 1)
        self.assertSuccess(self.attempt(session, submission))
        self.assertEqual(TutorAttempt.objects.get().help_level, 2)
        current.refresh_from_db()
        self.assertEqual(current.highest_help_level, 2)
        with self.assertRaises(ValueError):
            advance_help_level(current.id, 4)

    def test_revoked_access_blocks_every_session_and_attempt_endpoint(self):
        session = self.start()
        submission = self.submission()
        for field, value in (("enabled", False), ("visible", False), ("is_disabled", True)):
            obj = TutorProblemConfig.objects.get(problem=self.problem) if field == "enabled" else self.problem if field == "visible" else self.student
            setattr(obj, field, value)
            obj.save()
            self.assertFailed(self.client.get(self.session_url, {"problem_id": self.problem.id}))
            self.assertFailed(self.client.post(self.session_url, {"problem_id": self.problem.id}))
            self.assertFailed(self.attempt(session, submission))
            setattr(obj, field, not value)
            obj.save()
        self.problem.contest = Contest.objects.create(created_by=self.owner, **DEFAULT_CONTEST_DATA)
        self.problem.save()
        self.assertFailed(self.client.post(self.session_url, {"problem_id": self.problem.id}))
        self.assertFailed(self.attempt(session, submission))

    def test_closed_session_rejects_attempts_and_can_be_replaced(self):
        session = self.start()
        TutorSession.objects.filter(pk=session["id"]).update(state="closed")
        self.assertFailed(self.attempt(session, self.submission()))
        self.assertNotEqual(self.start()["id"], session["id"])

    def test_invalid_uuid_unknown_submission_and_unknown_query_are_rejected(self):
        session = self.start()
        self.assertFailed(self.client.post(self.attempt_url, {"session_id": "invalid", "submission_id": "missing"}))
        self.assertFailed(self.client.post(self.attempt_url, {"session_id": session["id"], "submission_id": "missing"}))
        self.assertFailed(self.client.get(self.session_url, {"problem_id": self.problem.id, "user_id": self.owner.id}))

    def test_session_and_attempt_keep_csrf_protection(self):
        session = self.start()
        client = APIClient(enforce_csrf_checks=True)
        client.login(username="alumno", password="clave")
        self.assertEqual(client.post(self.session_url, {"problem_id": self.problem.id}).status_code, 403)
        self.assertEqual(client.post(self.attempt_url, {"session_id": session["id"], "submission_id": "x"}).status_code, 403)

    def test_database_rejects_duplicate_active_sessions_and_attempts(self):
        session = self.start()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorSession.objects.create(user=self.student, problem=self.problem)
        self.assertSuccess(self.attempt(session, self.submission()))
        attempt = TutorAttempt.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorAttempt.objects.create(session=attempt.session, submission=attempt.submission, language="C++", result=-1, help_level=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TutorSession.objects.filter(pk=session["id"]).update(highest_help_level=4)


class TutorConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.user = User.objects.create(username="concurrente")
        self.problem = ProblemCreateTestBase.add_problem(DEFAULT_PROBLEM_DATA, self.user)
        TutorProblemConfig.objects.create(problem=self.problem, enabled=True)

    def parallel(self, function):
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.id)
                barrier.wait(timeout=10)
                return function(user)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(lambda _: run(), range(2)))

    def test_simultaneous_starts_recover_one_active_session(self):
        ids = self.parallel(lambda user: create_or_recover(user, self.problem.id).id)
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(TutorSession.objects.count(), 1)

    def test_simultaneous_attempts_create_one_record(self):
        session = create_or_recover(self.user, self.problem.id)
        submission = Submission.objects.create(problem=self.problem, user_id=self.user.id, username=self.user.username,
                                               code="x", language="C", result=0)
        ids = self.parallel(lambda user: register_attempt(user, session.id, submission.id).id)
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(TutorAttempt.objects.count(), 1)
