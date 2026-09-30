from unittest.mock import patch

from rest_framework.test import APIClient

from account.models import AdminType, ProblemPermission
from contest.models import Contest
from contest.tests import DEFAULT_CONTEST_DATA
from problem.tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase


class TutorAccessTests(ProblemCreateTestBase):
    def setUp(self):
        self.owner = self.create_admin()
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, self.owner)
        self.config_url = "/api/admin/ai_tutor/config"
        self.availability_url = "/api/ai_tutor/availability"

    def config(self, enabled, **extra):
        return self.client.put(self.config_url, {"problem_id": self.problem.id, "enabled": enabled, **extra})

    def test_defaults_disabled_without_creating_configuration(self):
        from ai_tutor.models import TutorProblemConfig
        response = self.client.get(self.config_url, {"problem_id": self.problem.id})
        self.assertSuccess(response)
        self.assertFalse(response.data["data"]["enabled"])
        self.assertFalse(TutorProblemConfig.objects.exists())
        response = self.client.get(self.availability_url, {"problem_id": self.problem.id})
        self.assertSuccess(response)
        self.assertFalse(response.data["data"]["can_start"])

    def test_effective_changes_audited_but_repeated_save_is_not(self):
        from ai_tutor.models import TutorProblemConfig
        with patch("ai_tutor.services.access.audit_log") as audit:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertSuccess(self.config(True))
            self.assertEqual(audit.call_count, 1)
            config = TutorProblemConfig.objects.get(problem=self.problem)
            original_time = config.updated_at
            with self.captureOnCommitCallbacks(execute=True):
                self.assertSuccess(self.config(True))
            self.assertEqual(audit.call_count, 1)
            config.refresh_from_db()
            self.assertEqual(config.updated_at, original_time)
            self.assertEqual(config.created_by, self.owner)
            self.assertEqual(config.updated_by, self.owner)
            with self.captureOnCommitCallbacks(execute=True):
                self.assertSuccess(self.config(False))
            self.assertEqual(audit.call_count, 2)
        self.problem.refresh_from_db()
        self.assertEqual(self.problem.submission_number, 0)

    def test_existing_permissions_allow_owner_teacher_and_all_problem_manager(self):
        for role, permission in ((AdminType.TEACHER, ProblemPermission.OWN), (AdminType.ADMIN, ProblemPermission.ALL)):
            self.owner.admin_type = role
            self.owner.problem_permission = permission
            self.owner.save()
            self.assertSuccess(self.config(True))

    def test_other_teacher_regular_disabled_and_no_permission_cannot_edit(self):
        other = self.create_user("otro", "clave", admin_type=AdminType.TEACHER, problem_permission=ProblemPermission.OWN)
        self.assertFailed(self.config(True))
        for role, permission, disabled in ((AdminType.REGULAR_USER, ProblemPermission.NONE, False),
                                          (AdminType.TEACHER, ProblemPermission.NONE, False),
                                          (AdminType.ADMIN, ProblemPermission.ALL, True)):
            other.admin_type, other.problem_permission, other.is_disabled = role, permission, disabled
            other.save()
            self.assertFailed(self.config(True))

    def test_unknown_fields_invalid_ids_and_missing_fields_are_rejected(self):
        self.assertFailed(self.config(True, highest_help_level=3))
        for data in ({}, {"problem_id": "texto"}, {"problem_id": -1}, {"problem_id": self.problem.id, "contest_id": 1}):
            self.assertFailed(self.client.get(self.config_url, data))
        self.assertFailed(self.client.put(self.config_url, {"problem_id": self.problem.id}))

    def test_availability_is_safe_for_anonymous_disabled_and_hidden_problem(self):
        self.assertSuccess(self.config(True))
        self.client.logout()
        response = self.client.get(self.availability_url, {"problem_id": self.problem.id})
        self.assertSuccess(response)
        self.assertTrue(response.data["data"]["enabled"])
        self.assertFalse(response.data["data"]["can_start"])
        student = self.create_user("alumno", "clave")
        self.assertTrue(self.client.get(self.availability_url, {"problem_id": self.problem.id}).data["data"]["can_start"])
        student.is_disabled = True
        student.save()
        self.assertFalse(self.client.get(self.availability_url, {"problem_id": self.problem.id}).data["data"]["can_start"])
        self.problem.visible = False
        self.problem.save()
        self.assertFailed(self.client.get(self.availability_url, {"problem_id": self.problem.id}))

    def test_contest_problem_is_blocked_even_with_enabled_configuration(self):
        from ai_tutor.models import TutorProblemConfig
        contest = Contest.objects.create(created_by=self.owner, **DEFAULT_CONTEST_DATA)
        self.problem.contest = contest
        self.problem.save()
        TutorProblemConfig.objects.create(problem=self.problem, enabled=True)
        self.assertFailed(self.config(True))
        self.assertFailed(self.client.get(self.availability_url, {"problem_id": self.problem.id}))

    def test_put_keeps_csrf_protection(self):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username="admin", password="admin")
        response = client.put(self.config_url, {"problem_id": self.problem.id, "enabled": True})
        self.assertEqual(response.status_code, 403)
