from unittest.mock import patch

from django.core.cache import cache
from rest_framework.test import APIClient

from ai_tutor.models import TutorProblemConfigVersion
from ai_tutor.tests.config_factory import config_content
from contest.models import ACMContestRank, Contest, ContestAnnouncement
from contest.tests import DEFAULT_CONTEST_DATA
from problem.models import Problem
from problem.tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase
from submission.models import Submission
from utils.constants import CacheKey

HAS_SUBMISSIONS = "El concurso tiene envíos; ocúltalo en lugar de borrarlo para conservar el historial."


class ContestDeleteAPITest(ProblemCreateTestBase):
    def setUp(self):
        cache.clear()
        self.owner = self.create_admin()
        self.contest = self.new_contest(self.owner)
        self.url = self.reverse("contest_admin_api") + "?id="

    def new_contest(self, owner):
        contest = Contest.objects.create(created_by=owner, **DEFAULT_CONTEST_DATA)
        ContestAnnouncement.objects.create(contest=contest, title="Aviso", content="<p>Hola</p>", created_by=owner)
        ACMContestRank.objects.create(user=owner, contest=contest)
        problem = self.add_problem(DEFAULT_PROBLEM_DATA, owner)
        Problem.objects.filter(pk=problem.pk).update(contest=contest)
        return contest

    def delete(self, value=None):
        return self.client.delete(self.url + str(self.contest.id if value is None else value))

    def submit(self, **fields):
        return Submission.objects.create(user_id=self.owner.id, username=self.owner.username, code="x", language="C", result=0, **fields)

    def test_owner_deletes_a_contest_without_submissions_and_its_dependents(self):
        other = self.new_contest(self.owner)
        cache.set(f"{CacheKey.contest_rank_cache}:{self.contest.id}", "ranking")
        with patch("contest.views.admin.audit_log") as audit:
            response = self.delete()
        self.assertSuccess(response)
        self.assertFalse(Contest.objects.filter(pk=self.contest.id).exists())
        self.assertFalse(Problem.objects.filter(contest_id=self.contest.id).exists())
        self.assertFalse(ContestAnnouncement.objects.filter(contest_id=self.contest.id).exists())
        self.assertFalse(ACMContestRank.objects.filter(contest_id=self.contest.id).exists())
        self.assertIsNone(cache.get(f"{CacheKey.contest_rank_cache}:{self.contest.id}"))
        # No toca otros concursos ni los problemas públicos.
        self.assertTrue(Contest.objects.filter(pk=other.id).exists())
        self.assertTrue(Problem.objects.filter(contest_id=other.id).exists())
        self.assertEqual(audit.call_args.args[1:4], ("contest.delete", "Contest", str(self.contest.id)))
        self.assertEqual(audit.call_args.args[4]["problems"], 1)

    def test_super_admin_can_delete_a_contest_created_by_another_teacher(self):
        self.create_super_admin()
        self.assertSuccess(self.delete())
        self.assertFalse(Contest.objects.filter(pk=self.contest.id).exists())

    def test_contest_with_submissions_is_rejected_and_nothing_is_deleted(self):
        problem = Problem.objects.get(contest=self.contest)
        self.submit(problem=problem, contest=self.contest)
        response = self.delete()
        self.assertEqual((response.data["error"], response.data["data"]), ("contest-has-submissions", HAS_SUBMISSIONS))
        self.assertTrue(Contest.objects.filter(pk=self.contest.id).exists())
        self.assertTrue(Problem.objects.filter(contest=self.contest).exists())
        self.assertTrue(ContestAnnouncement.objects.filter(contest=self.contest).exists())
        self.assertTrue(ACMContestRank.objects.filter(contest=self.contest).exists())
        self.assertEqual(Submission.objects.count(), 1)

    def test_submission_linked_only_through_a_contest_problem_also_blocks(self):
        self.submit(problem=Problem.objects.get(contest=self.contest))
        self.assertEqual(self.delete().data["error"], "contest-has-submissions")
        self.assertTrue(Contest.objects.filter(pk=self.contest.id).exists())

    def test_submissions_of_other_contests_do_not_block(self):
        other = self.new_contest(self.owner)
        self.submit(problem=Problem.objects.get(contest=other), contest=other)
        self.assertSuccess(self.delete())
        self.assertEqual(Submission.objects.count(), 1)

    def test_only_the_creator_teacher_or_a_super_admin_may_delete(self):
        self.create_admin("otro-docente", "clave")
        response = self.delete()
        self.assertFailed(response, "Contest does not exist")
        self.create_user("alumno", "clave")
        self.assertFailed(self.delete())
        self.client.logout()
        self.assertFailed(self.delete())
        self.assertTrue(Contest.objects.filter(pk=self.contest.id).exists())
        self.assertTrue(Problem.objects.filter(contest=self.contest).exists())

    def test_invalid_or_unknown_ids_are_rejected(self):
        for value in ("", "abc", "-1", "1;2", str(self.contest.id + 1000)):
            with self.subTest(value=value):
                self.assertFailed(self.delete(value))
        self.assertEqual(self.client.delete(self.url[:-4]).data["error"], "error")
        self.assertTrue(Contest.objects.filter(pk=self.contest.id).exists())

    def test_protected_tutor_history_aborts_the_whole_delete(self):
        problem = Problem.objects.get(contest=self.contest)
        TutorProblemConfigVersion.objects.create(problem=problem, version=1, created_by=self.owner, **config_content())
        response = self.delete()
        self.assertEqual(response.data["error"], "protected-contest-history")
        self.assertTrue(Contest.objects.filter(pk=self.contest.id).exists())
        self.assertTrue(ContestAnnouncement.objects.filter(contest=self.contest).exists())
        self.assertTrue(ACMContestRank.objects.filter(contest=self.contest).exists())

    def test_delete_keeps_csrf_protection(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="admin", password="admin"))
        self.assertEqual(client.delete(self.url + str(self.contest.id)).status_code, 403)
        self.assertTrue(Contest.objects.filter(pk=self.contest.id).exists())
