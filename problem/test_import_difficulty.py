import copy
import io
import json
import os
import tempfile
from unittest.mock import patch
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings

from contest.models import Contest
from contest.tests import DEFAULT_CONTEST_DATA
from .models import Problem
from .tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase


class ImportDifficultyTest(ProblemCreateTestBase):
    def setUp(self):
        self.admin = self.create_super_admin()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(TEST_CASE_DIR=self.directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def payload(self, **overrides):
        data = {
            "display_id": "BLZ2-046", "title": "Suma", "tags": [],
            "description": {"format": "html", "value": "Suma dos números"},
            "input_description": {"format": "html", "value": "Dos enteros"},
            "output_description": {"format": "html", "value": "La suma"},
            "hint": {"format": "html", "value": ""},
            "test_case_score": [{"input_name": "1.in", "output_name": "1.out", "score": 100}],
            "time_limit": 1000, "memory_limit": 128, "samples": [{"input": "1 2", "output": "3"}],
            "template": {}, "spj": None, "rule_type": "ACM", "source": "Banco", "answers": []
        }
        data.update(overrides)
        return data

    def upload(self, data):
        content = io.BytesIO()
        with ZipFile(content, "w") as archive:
            archive.writestr("1/problem.json", json.dumps(data))
            archive.writestr("1/testcase/1.in", "1 2\n")
            archive.writestr("1/testcase/1.out", "3\n")
        return self.client.post(self.reverse("import_problem_api"),
                                {"file": SimpleUploadedFile("problema.zip", content.getvalue())}, format="multipart")

    def test_import_zip_levels_and_fallbacks(self):
        cases = [
            ({"difficulty": "Low"}, "Low"), ({"difficulty": "Mid"}, "Mid"),
            ({"difficulty": "High"}, "High"), ({"tags": ["Dificultad: Baja"]}, "Low"),
            ({"tags": ["Dificultad: Media"]}, "Mid"), ({"tags": ["Dificultad: Alta"]}, "High"),
            ({}, "Mid"), ({"tags": ["Otra etiqueta"]}, "Mid"),
            ({"difficulty": "High", "tags": ["Dificultad: Baja"]}, "High"),
            ({"difficulty": "Low", "tags": ["Dificultad: Baja", "Dificultad: Alta"]}, "Low"),
            ({"tags": ["Dificultad: Baja", "Dificultad: Alta"]}, "Mid"),
            ({"tags": ["Dificultad: Alta", "Dificultad: Baja"]}, "Mid"),
            ({"tags": ["Dificultad: Baja", "Dificultad: Baja"]}, "Low"),
        ]
        for index, (overrides, expected) in enumerate(cases):
            with self.subTest(overrides=overrides):
                data = self.payload(**overrides)
                data["display_id"] = f"TEST-{index}"
                self.assertSuccess(self.upload(data))
                problem = Problem.objects.get(_id=data["display_id"])
                self.assertEqual(problem.difficulty, expected)
                self.assertEqual(problem.created_by, self.admin)
                self.assertTrue(problem.visible)
                self.assertEqual(problem.share_mode, "Shared")
                self.assertEqual(problem.samples, data["samples"])
                self.assertEqual(problem.time_limit, 1000)
                self.assertEqual(problem.memory_limit, 128)
                self.assertEqual(set(problem.tags.values_list("name", flat=True)),
                                 set(data["tags"] or ["SinEtiqueta"]))
                with open(os.path.join(self.directory.name, problem.test_case_id, "1.out")) as output:
                    self.assertEqual(output.read(), "3\n")

    def test_invalid_explicit_difficulty_rejected_without_writes(self):
        for value in ["Invalid", "low", "", None, 1]:
            with self.subTest(value=value):
                response = self.upload(self.payload(difficulty=value, tags=["Dificultad: Baja"]))
                self.assertFailed(response)
                self.assertIn("difficulty", response.data["data"])
                self.assertFalse(Problem.objects.exists())

    def test_export_zip_then_import_preserves_each_level(self):
        for level in ["Low", "Mid", "High"]:
            with self.subTest(level=level):
                self.assertSuccess(self.upload(self.payload(display_id=level, difficulty=level)))
                original = Problem.objects.get(_id=level)
                response = self.client.get(self.reverse("export_problem_api"), {"problem_id": [original.id]})
                self.assertEqual(response.status_code, 200)
                exported = b"".join(response.streaming_content)
                with ZipFile(io.BytesIO(exported)) as archive:
                    info = json.loads(archive.read("1/problem.json"))
                    self.assertIn("difficulty", info)
                    self.assertEqual(info["difficulty"], level)
                original.delete()
                response = self.client.post(self.reverse("import_problem_api"),
                                            {"file": SimpleUploadedFile("export.zip", exported)}, format="multipart")
                self.assertSuccess(response)
                self.assertEqual(Problem.objects.get(_id=level).difficulty, level)


class RepairDifficultyTest(ProblemCreateTestBase):
    def setUp(self):
        self.admin = self.create_super_admin()
        self.contest = Contest.objects.create(created_by=self.admin, **copy.deepcopy(DEFAULT_CONTEST_DATA))

    def problem(self, display_id, tags, contest=None):
        data = copy.deepcopy(DEFAULT_PROBLEM_DATA)
        data.update(_id=display_id, difficulty="Mid", tags=tags, contest=contest)
        return self.add_problem(data, self.admin)

    def run_command(self, apply=False):
        output = io.StringIO()
        call_command("reparar_dificultades", apply=apply, stdout=output)
        return output.getvalue()

    def test_simulation_does_not_write(self):
        problem = self.problem("BLZ2-046", ["Dificultad: Baja"])
        output = self.run_command()
        problem.refresh_from_db()
        self.assertEqual(problem.difficulty, "Mid")
        self.assertIn("BLZ2-046", output)
        self.assertIn("Low", output)
        self.assertIn("BLZ2-145", output)

    def test_apply_only_exact_unique_non_contest_ids_with_one_level(self):
        low = self.problem("BLZ2-046", ["Dificultad: Baja", "Algoritmos"])
        high = self.problem("BLZ2-145", ["Dificultad: Alta"])
        skipped = [self.problem("BLZ2-045", ["Dificultad: Baja"]),
                   self.problem("BLZ2-146", ["Dificultad: Alta"]),
                   self.problem("BLZ2-0046", ["Dificultad: Baja"]),
                   self.problem("BLZ2-047", ["Dificultad: Baja"], self.contest),
                   self.problem("BLZ2-048", ["Dificultad: Alta"]),
                   self.problem("BLZ2-048", ["Dificultad: Alta"]),
                   self.problem("BLZ2-049", []),
                   self.problem("BLZ2-050", ["Dificultad: Baja", "Dificultad: Alta"])]
        # Un homónimo en un concurso no impide reparar el problema público único.
        skipped.append(self.problem("BLZ2-046", ["Dificultad: Alta"], self.contest))
        before = {p.pk: Problem.objects.values().get(pk=p.pk) for p in [low, high] + skipped}
        output = self.run_command(apply=True)
        for problem, expected in [(low, "Low"), (high, "High")] + [(p, "Mid") for p in skipped]:
            after = Problem.objects.values().get(pk=problem.pk)
            self.assertEqual(after.pop("difficulty"), expected)
            previous = before[problem.pk].copy()
            previous.pop("difficulty")
            self.assertEqual(after, previous)
        for display_id in ["BLZ2-047", "BLZ2-048", "BLZ2-049", "BLZ2-050", "BLZ2-051"]:
            self.assertIn(display_id, output)
        self.assertIn("duplicados", output)
        self.assertIn("contradictorias", output)
        self.assertIn("ausente", output)
        self.assertIn("sin etiqueta", output)
        self.run_command(apply=True)
        low.refresh_from_db()
        self.assertEqual(low.difficulty, "Low")

    def test_apply_rolls_back_all_changes_on_error(self):
        first = self.problem("BLZ2-046", ["Dificultad: Baja"])
        self.problem("BLZ2-047", ["Dificultad: Alta"])
        from django.db.models.query import QuerySet
        update = QuerySet.update
        calls = []

        def fail_second(queryset, **kwargs):
            calls.append(True)
            if len(calls) == 2:
                raise RuntimeError("Fallo durante la reparación")
            return update(queryset, **kwargs)

        with patch.object(QuerySet, "update", fail_second):
            with self.assertRaises(RuntimeError):
                self.run_command(apply=True)
        first.refresh_from_db()
        self.assertEqual(first.difficulty, "Mid")
