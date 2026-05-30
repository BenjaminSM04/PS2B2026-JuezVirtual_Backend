import copy
import hashlib
import os
import shutil
from datetime import timedelta
from zipfile import ZipFile

from django.conf import settings

from utils.api.tests import APITestCase

from account.models import AdminType, ProblemPermission

from .models import ProblemTag, ProblemIOMode
from .models import Problem, ProblemRuleType, ProblemShareMode
from contest.models import Contest
from contest.tests import DEFAULT_CONTEST_DATA

from .views.admin import TestCaseAPI
from .utils import parse_problem_template

DEFAULT_PROBLEM_DATA = {"_id": "A-110", "title": "test", "description": "<p>test</p>", "input_description": "test",
                        "output_description": "test", "time_limit": 1000, "memory_limit": 256, "difficulty": "Low",
                        "visible": True, "tags": ["test"], "languages": ["C", "C++", "Java", "Python2"], "template": {},
                        "samples": [{"input": "test", "output": "test"}], "spj": False, "spj_language": "C",
                        "spj_code": "", "spj_compile_ok": True, "test_case_id": "499b26290cc7994e0b497212e842ea85",
                        "test_case_score": [{"output_name": "1.out", "input_name": "1.in", "output_size": 0,
                                             "stripped_output_md5": "d41d8cd98f00b204e9800998ecf8427e",
                                             "input_size": 0, "score": 0}],
                        "io_mode": {"io_mode": ProblemIOMode.standard, "input": "input.txt", "output": "output.txt"},
                        "share_submission": False,
                        "rule_type": "ACM", "hint": "<p>test</p>", "source": "test"}


class ProblemCreateTestBase(APITestCase):
    @staticmethod
    def add_problem(problem_data, created_by):
        data = copy.deepcopy(problem_data)
        if data["spj"]:
            if not data["spj_language"] or not data["spj_code"]:
                raise ValueError("Invalid spj")
            data["spj_version"] = hashlib.md5(
                (data["spj_language"] + ":" + data["spj_code"]).encode("utf-8")).hexdigest()
        else:
            data["spj_language"] = None
            data["spj_code"] = None
        if data["rule_type"] == ProblemRuleType.OI:
            total_score = 0
            for item in data["test_case_score"]:
                if item["score"] <= 0:
                    raise ValueError("invalid score")
                else:
                    total_score += item["score"]
            data["total_score"] = total_score
        data["created_by"] = created_by
        tags = data.pop("tags")

        data["languages"] = list(data["languages"])

        problem = Problem.objects.create(**data)

        for item in tags:
            try:
                tag = ProblemTag.objects.get(name=item)
            except ProblemTag.DoesNotExist:
                tag = ProblemTag.objects.create(name=item)
            problem.tags.add(tag)
        return problem


class ProblemTagListAPITest(APITestCase):
    def test_get_tag_list(self):
        ProblemTag.objects.create(name="name1")
        ProblemTag.objects.create(name="name2")
        resp = self.client.get(self.reverse("problem_tag_list_api"))
        self.assertSuccess(resp)


class TestCaseUploadAPITest(APITestCase):
    def setUp(self):
        self.api = TestCaseAPI()
        self.url = self.reverse("test_case_api")
        self.create_super_admin()

    def test_filter_file_name(self):
        self.assertEqual(self.api.filter_name_list(["1.in", "1.out", "2.in", ".DS_Store"], spj=False),
                         ["1.in", "1.out"])
        self.assertEqual(self.api.filter_name_list(["2.in", "2.out"], spj=False), [])

        self.assertEqual(self.api.filter_name_list(["1.in", "1.out", "2.in"], spj=True), ["1.in", "2.in"])
        self.assertEqual(self.api.filter_name_list(["2.in", "3.in"], spj=True), [])

    def make_test_case_zip(self):
        base_dir = os.path.join("/tmp", "test_case")
        shutil.rmtree(base_dir, ignore_errors=True)
        os.mkdir(base_dir)
        file_names = ["1.in", "1.out", "2.in", ".DS_Store"]
        for item in file_names:
            with open(os.path.join(base_dir, item), "w", encoding="utf-8") as f:
                f.write(item + "\n" + item + "\r\n" + "end")
        zip_file = os.path.join(base_dir, "test_case.zip")
        with ZipFile(os.path.join(base_dir, "test_case.zip"), "w") as f:
            for item in file_names:
                f.write(os.path.join(base_dir, item), item)
        return zip_file

    def test_upload_spj_test_case_zip(self):
        with open(self.make_test_case_zip(), "rb") as f:
            resp = self.client.post(self.url,
                                    data={"spj": "true", "file": f}, format="multipart")
            self.assertSuccess(resp)
            data = resp.data["data"]
            self.assertEqual(data["spj"], True)
            test_case_dir = os.path.join(settings.TEST_CASE_DIR, data["id"])
            self.assertTrue(os.path.exists(test_case_dir))
            for item in data["info"]:
                name = item["input_name"]
                with open(os.path.join(test_case_dir, name), "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), name + "\n" + name + "\n" + "end")

    def test_upload_test_case_zip(self):
        with open(self.make_test_case_zip(), "rb") as f:
            resp = self.client.post(self.url,
                                    data={"spj": "false", "file": f}, format="multipart")
            self.assertSuccess(resp)
            data = resp.data["data"]
            self.assertEqual(data["spj"], False)
            test_case_dir = os.path.join(settings.TEST_CASE_DIR, data["id"])
            self.assertTrue(os.path.exists(test_case_dir))
            for item in data["info"]:
                name = item["input_name"]
                with open(os.path.join(test_case_dir, name), "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), name + "\n" + name + "\n" + "end")


class ProblemAdminAPITest(APITestCase):
    def setUp(self):
        self.url = self.reverse("problem_admin_api")
        self.create_super_admin()
        self.data = copy.deepcopy(DEFAULT_PROBLEM_DATA)

    def test_create_problem(self):
        resp = self.client.post(self.url, data=self.data)
        self.assertSuccess(resp)
        return resp

    def test_duplicate_display_id(self):
        self.test_create_problem()

        resp = self.client.post(self.url, data=self.data)
        self.assertFailed(resp, "Display ID already exists")

    def test_spj(self):
        data = copy.deepcopy(self.data)
        data["spj"] = True

        resp = self.client.post(self.url, data)
        self.assertFailed(resp, "Invalid spj")

        data["spj_code"] = "test"
        resp = self.client.post(self.url, data=data)
        self.assertSuccess(resp)

    def test_get_problem(self):
        self.test_create_problem()
        resp = self.client.get(self.url)
        self.assertSuccess(resp)

    def test_get_one_problem(self):
        problem_id = self.test_create_problem().data["data"]["id"]
        resp = self.client.get(self.url + "?id=" + str(problem_id))
        self.assertSuccess(resp)

    def test_edit_problem(self):
        problem_id = self.test_create_problem().data["data"]["id"]
        data = copy.deepcopy(self.data)
        data["id"] = problem_id
        resp = self.client.put(self.url, data=data)
        self.assertSuccess(resp)


class ProblemAPITest(ProblemCreateTestBase):
    def setUp(self):
        self.url = self.reverse("problem_api")
        admin = self.create_admin(login=False)
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, admin)
        self.create_user("test", "test123")

    def test_get_problem_list(self):
        resp = self.client.get(f"{self.url}?limit=10")
        self.assertSuccess(resp)

    def get_one_problem(self):
        resp = self.client.get(self.url + "?id=" + self.problem._id)
        self.assertSuccess(resp)


class ContestProblemAdminTest(APITestCase):
    def setUp(self):
        self.url = self.reverse("contest_problem_admin_api")
        self.create_admin()
        self.contest = self.client.post(self.reverse("contest_admin_api"), data=DEFAULT_CONTEST_DATA).data["data"]

    def test_create_contest_problem(self):
        data = copy.deepcopy(DEFAULT_PROBLEM_DATA)
        data["contest_id"] = self.contest["id"]
        resp = self.client.post(self.url, data=data)
        self.assertSuccess(resp)
        return resp.data["data"]

    def test_get_contest_problem(self):
        self.test_create_contest_problem()
        contest_id = self.contest["id"]
        resp = self.client.get(self.url + "?contest_id=" + str(contest_id))
        self.assertSuccess(resp)
        self.assertEqual(len(resp.data["data"]["results"]), 1)

    def test_get_one_contest_problem(self):
        contest_problem = self.test_create_contest_problem()
        contest_id = self.contest["id"]
        problem_id = contest_problem["id"]
        resp = self.client.get(f"{self.url}?contest_id={contest_id}&id={problem_id}")
        self.assertSuccess(resp)


class ContestProblemTest(ProblemCreateTestBase):
    def setUp(self):
        admin = self.create_admin()
        url = self.reverse("contest_admin_api")
        contest_data = copy.deepcopy(DEFAULT_CONTEST_DATA)
        contest_data["password"] = ""
        contest_data["start_time"] = contest_data["start_time"] + timedelta(hours=1)
        self.contest = self.client.post(url, data=contest_data).data["data"]
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, admin)
        self.problem.contest_id = self.contest["id"]
        self.problem.save()
        self.url = self.reverse("contest_problem_api")

    def test_admin_get_contest_problem_list(self):
        contest_id = self.contest["id"]
        resp = self.client.get(self.url + "?contest_id=" + str(contest_id))
        self.assertSuccess(resp)
        self.assertEqual(len(resp.data["data"]), 1)

    def test_admin_get_one_contest_problem(self):
        contest_id = self.contest["id"]
        problem_id = self.problem._id
        resp = self.client.get("{}?contest_id={}&problem_id={}".format(self.url, contest_id, problem_id))
        self.assertSuccess(resp)

    def test_regular_user_get_not_started_contest_problem(self):
        self.create_user("test", "test123")
        resp = self.client.get(self.url + "?contest_id=" + str(self.contest["id"]))
        self.assertDictEqual(resp.data, {"error": "error", "data": "Contest has not started yet."})

    def test_reguar_user_get_started_contest_problem(self):
        self.create_user("test", "test123")
        contest = Contest.objects.first()
        contest.start_time = contest.start_time - timedelta(hours=1)
        contest.save()
        resp = self.client.get(self.url + "?contest_id=" + str(self.contest["id"]))
        self.assertSuccess(resp)


class AddProblemFromPublicProblemAPITest(ProblemCreateTestBase):
    def setUp(self):
        admin = self.create_admin()
        url = self.reverse("contest_admin_api")
        contest_data = copy.deepcopy(DEFAULT_CONTEST_DATA)
        contest_data["password"] = ""
        contest_data["start_time"] = contest_data["start_time"] + timedelta(hours=1)
        self.contest = self.client.post(url, data=contest_data).data["data"]
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, admin)
        self.url = self.reverse("add_contest_problem_from_public_api")
        self.data = {
            "display_id": "1000",
            "contest_id": self.contest["id"],
            "problem_id": self.problem.id
        }

    def test_add_contest_problem(self):
        resp = self.client.post(self.url, data=self.data)
        self.assertSuccess(resp)
        self.assertTrue(Problem.objects.all().exists())
        self.assertTrue(Problem.objects.filter(contest_id=self.contest["id"]).exists())


class ProblemShareModeTest(ProblemCreateTestBase):
    """Teacher ownership + share_mode based discovery and reuse."""

    def _problem_data(self, _id, share_mode):
        data = copy.deepcopy(DEFAULT_PROBLEM_DATA)
        data["_id"] = _id
        data["share_mode"] = share_mode
        return data

    def setUp(self):
        self.list_url = self.reverse("problem_admin_api")
        self.add_url = self.reverse("add_contest_problem_from_public_api")
        self.contest_url = self.reverse("contest_admin_api")

        self.teacher_a = self.create_user("teacher_a", "pass123", admin_type=AdminType.TEACHER,
                                          problem_permission=ProblemPermission.OWN, login=False)
        self.teacher_b = self.create_user("teacher_b", "pass123", admin_type=AdminType.TEACHER,
                                          problem_permission=ProblemPermission.OWN, login=False)

        self.a_shared = self.add_problem(self._problem_data("A-SHARED", ProblemShareMode.SHARED), self.teacher_a)
        self.a_private = self.add_problem(self._problem_data("A-PRIVATE", ProblemShareMode.PRIVATE), self.teacher_a)
        self.b_own = self.add_problem(self._problem_data("B-OWN", ProblemShareMode.SHARED), self.teacher_b)

    def _login_b(self):
        self.client.login(username="teacher_b", password="pass123")

    def _ids(self, resp):
        return [p["id"] for p in resp.data["data"]["results"]]

    def test_scope_mine_shows_only_own(self):
        self._login_b()
        resp = self.client.get(f"{self.list_url}?limit=10&scope=mine")
        self.assertSuccess(resp)
        ids = self._ids(resp)
        self.assertEqual(ids, [self.b_own.id])

    def test_scope_shared_excludes_others_private(self):
        self._login_b()
        resp = self.client.get(f"{self.list_url}?limit=10&scope=shared")
        self.assertSuccess(resp)
        ids = self._ids(resp)
        self.assertIn(self.a_shared.id, ids)
        self.assertNotIn(self.a_private.id, ids)

    def test_scope_all_is_own_plus_shared(self):
        self._login_b()
        resp = self.client.get(f"{self.list_url}?limit=10&scope=all")
        self.assertSuccess(resp)
        ids = self._ids(resp)
        self.assertIn(self.b_own.id, ids)
        self.assertIn(self.a_shared.id, ids)
        self.assertNotIn(self.a_private.id, ids)

    def test_teacher_cannot_edit_others_problem(self):
        self._login_b()
        data = self._problem_data("A-SHARED-EDIT", ProblemShareMode.SHARED)
        data["id"] = self.a_shared.id
        resp = self.client.put(self.list_url, data=data)
        self.assertFailed(resp, "Problem does not exist")

    def test_teacher_cannot_delete_others_problem(self):
        self._login_b()
        resp = self.client.delete(f"{self.list_url}?id={self.a_shared.id}")
        self.assertFailed(resp, "Problem does not exist")
        self.assertTrue(Problem.objects.filter(id=self.a_shared.id).exists())

    def _create_contest_for_b(self):
        self._login_b()
        contest_data = copy.deepcopy(DEFAULT_CONTEST_DATA)
        contest_data["password"] = ""
        return self.client.post(self.contest_url, data=contest_data).data["data"]

    def test_reuse_shared_problem_preserves_author(self):
        contest_b = self._create_contest_for_b()
        resp = self.client.post(self.add_url, data={"display_id": "X-1",
                                                    "contest_id": contest_b["id"],
                                                    "problem_id": self.a_shared.id})
        self.assertSuccess(resp)
        snapshot = Problem.objects.get(contest_id=contest_b["id"], _id="X-1")
        self.assertNotEqual(snapshot.id, self.a_shared.id)
        self.assertEqual(snapshot.created_by_id, self.teacher_a.id)

    def test_cannot_reuse_others_private_problem(self):
        contest_b = self._create_contest_for_b()
        resp = self.client.post(self.add_url, data={"display_id": "X-2",
                                                    "contest_id": contest_b["id"],
                                                    "problem_id": self.a_private.id})
        self.assertFailed(resp, "No permission to use this problem")

    def test_cannot_add_problem_to_others_contest(self):
        # contest owned by teacher A
        self.client.login(username="teacher_a", password="pass123")
        contest_data = copy.deepcopy(DEFAULT_CONTEST_DATA)
        contest_data["password"] = ""
        contest_a = self.client.post(self.contest_url, data=contest_data).data["data"]
        # teacher B tries to inject a problem into A's contest
        self._login_b()
        resp = self.client.post(self.add_url, data={"display_id": "X-3",
                                                    "contest_id": contest_a["id"],
                                                    "problem_id": self.b_own.id})
        self.assertFailed(resp, "Contest does not exist")


class ResolveImportCreatorTest(APITestCase):
    """Fallback de created_by al importar un ejercicio (respeta autor si existe, si no cae al importador)."""

    def setUp(self):
        self.importer = self.create_user("importer", "pass123", login=False)
        self.author = self.create_user("orig_author", "pass123", login=False)

    def test_existing_author_is_respected(self):
        from .views.admin import resolve_import_creator
        self.assertEqual(resolve_import_creator("orig_author", self.importer).id, self.author.id)

    def test_missing_author_falls_back_to_importer(self):
        from .views.admin import resolve_import_creator
        self.assertEqual(resolve_import_creator(None, self.importer).id, self.importer.id)
        self.assertEqual(resolve_import_creator("", self.importer).id, self.importer.id)

    def test_unknown_author_falls_back_to_importer(self):
        from .views.admin import resolve_import_creator
        self.assertEqual(resolve_import_creator("ghost_user", self.importer).id, self.importer.id)


class ParseProblemTemplateTest(APITestCase):
    def test_parse(self):
        template_str = """
//PREPEND BEGIN
aaa
//PREPEND END

//TEMPLATE BEGIN
bbb
//TEMPLATE END

//APPEND BEGIN
ccc
//APPEND END
"""

        ret = parse_problem_template(template_str)
        self.assertEqual(ret["prepend"], "aaa\n")
        self.assertEqual(ret["template"], "bbb\n")
        self.assertEqual(ret["append"], "ccc\n")

    def test_parse1(self):
        template_str = """
//PREPEND BEGIN
aaa
//PREPEND END

//APPEND BEGIN
ccc
//APPEND END
//APPEND BEGIN
ddd
//APPEND END
"""

        ret = parse_problem_template(template_str)
        self.assertEqual(ret["prepend"], "aaa\n")
        self.assertEqual(ret["template"], "")
        self.assertEqual(ret["append"], "ccc\n")
