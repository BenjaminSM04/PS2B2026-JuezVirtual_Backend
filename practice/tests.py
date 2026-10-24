from datetime import timedelta
from django.utils import timezone
from django.core.management import call_command
from practice.models import Achievement
from practice.services import mascot, record_accepted
from problem.tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase
from submission.models import Submission


class MascotTests(ProblemCreateTestBase):
    def setUp(self):
        self.user = self.create_admin()
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, self.user)

    def submit(self, **extra):
        return Submission.objects.create(user_id=self.user.id, username=self.user.username, problem=self.problem,
            language="Python3", code="print(1)", result=extra.pop("result", 0), **extra)

    def test_history_reconciles_without_get_and_survives_rejudge_and_deletion(self):
        submission = self.submit()
        Achievement.objects.all().delete()
        call_command("reconcile_mascot")
        self.assertEqual(Achievement.objects.count(), 1)
        submission.result = -1
        submission.save()
        submission.delete()
        self.problem.delete()
        self.assertEqual(mascot(self.user)["solved_count"], 1)

    def test_repetitions_partial_and_other_users_do_not_inflate(self):
        one = self.submit()
        record_accepted(one)
        self.submit()
        self.submit(result=8)
        self.assertEqual(mascot(self.user)["solved_count"], 1)
        other = self.create_user("mascota-ajena", "clave")
        self.assertEqual(mascot(other)["solved_count"], 0)

    def test_contest_accepted_never_counts(self):
        from contest.models import Contest
        from contest.tests import DEFAULT_CONTEST_DATA
        contest = Contest.objects.create(created_by=self.user, **DEFAULT_CONTEST_DATA)
        self.submit(contest=contest)
        self.problem.contest = contest
        self.problem.save()
        self.submit()
        self.assertEqual(Achievement.objects.count(), 0)

    def test_stages_and_locked_preferences_are_server_controlled(self):
        self.assertEqual(mascot(self.user)["stage"], "egg")
        self.assertFailed(self.client.patch("/api/mascot", {"color": "violet"}))
        self.assertFailed(self.client.patch("/api/mascot", {"solved_count": 100}))
        self.assertFailed(self.client.patch("/api/mascot", {"visible": "false"}))
        self.assertSuccess(self.client.patch("/api/mascot", {"visible": False, "animations_enabled": False}))
        for i in range(30):
            Achievement.objects.get_or_create(user=self.user, original_problem_id=1000 + i,
                defaults={"earned_at": timezone.now(), "first_submission_id": str(i)})
        self.assertEqual(mascot(self.user)["stage"], "adult")
        self.assertIsNone(mascot(self.user)["next_stage_at"])
        self.assertSuccess(self.client.patch("/api/mascot", {"color": "violet", "accessory": "backpack"}))

    def test_private_api_and_overview(self):
        self.submit(result=-1)
        response = self.client.get("/api/practice/overview")
        self.assertSuccess(response)
        self.assertEqual(response.data["data"]["continue_problem"]["id"], self.problem.id)
        self.client.logout()
        self.assertFailed(self.client.get("/api/mascot"))
