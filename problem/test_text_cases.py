import hashlib
import os
from pathlib import Path

from django.conf import settings
from rest_framework.test import APIClient
from utils.api.tests import APITestCase
from .serializers import TextTestCasesSerializer
from .tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase
from account.models import User, AdminType, ProblemPermission


class TextTestCasesTest(APITestCase):
    def setUp(self):
        self.create_super_admin()
        self.url = self.reverse("text_test_case_api")

    def test_whitespace_empty_cases_and_unicode_match_zip_format(self):
        response = self.client.post(self.url, data={"cases": [
            {"input": "  á\r\n", "output": "  resultado \n"}, {"input": "", "output": ""}]})
        self.assertSuccess(response)
        data = response.data["data"]
        folder = Path(settings.TEST_CASE_DIR) / data["id"]
        self.assertEqual((folder / "1.in").read_bytes(), "  á\n".encode())
        self.assertEqual((folder / "1.out").read_bytes(), b"  resultado \n")
        self.assertEqual((folder / "2.out").read_bytes(), b"")
        self.assertEqual(data["info"][0]["stripped_output_md5"], hashlib.md5(b"  resultado").hexdigest())
        self.assertEqual(os.stat(folder / "1.in").st_mode & 0o777, 0o640)

    def test_rejects_empty_oversized_and_incomplete_lists(self):
        for data in ({"cases": []}, {"cases": [{"input": "x"}]},
                     {"cases": [{"input": "x", "output": "x"}] * 101},
                     {"cases": [{"input": "x" * 262145, "output": ""}]}):
            self.assertFalse(TextTestCasesSerializer(data=data).is_valid())

    def test_student_cannot_create_cases(self):
        self.client.logout()
        response = self.client.post(self.url, data={"cases": [{"input": "", "output": ""}]})
        self.assertIsNotNone(response.data["error"])

    def test_enforces_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="root", password="root"))
        self.assertEqual(client.post(self.url, data={"cases": [{"input": "", "output": ""}]}).status_code, 403)

    def test_saved_cases_require_problem_ownership(self):
        created = self.client.post(self.url, data={"cases": [{"input": "privado\n", "output": "respuesta\n"}]}).data["data"]
        problem = ProblemCreateTestBase.add_problem(dict(DEFAULT_PROBLEM_DATA, test_case_id=created["id"]), User.objects.get(username="root"))
        response = self.client.get(self.url, data={"problem_id": problem.id})
        self.assertSuccess(response)
        self.assertEqual(response.data["data"]["cases"], [{"input": "privado\n", "output": "respuesta\n"}])
        other = User.objects.create(username="otro-docente", admin_type=AdminType.TEACHER, problem_permission=ProblemPermission.OWN)
        self.client.force_login(other)
        response = self.client.get(self.url, data={"problem_id": problem.id})
        self.assertIsNotNone(response.data["error"])
        self.assertNotIn("privado", str(response.data))
