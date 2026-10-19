"""Pruebas de anonimización y exportación segura (PB-05).

Las pruebas unitarias usan sustitutos y no requieren base de datos; las del
comando requieren PostgreSQL (igual que las demás pruebas del tutor) y usan
archivos temporales exclusivamente.
"""

import io
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from django.utils import timezone

from ai_tutor.dataset import anonymize
from ai_tutor.dataset.schema import TutorExampleSerializer
from ai_tutor.management.commands.export_authorized_submissions import parse_problem_ids
from contest.models import Contest
from problem.tests import DEFAULT_PROBLEM_DATA, ProblemCreateTestBase
from submission.models import Submission


def fake_problem():
    return SimpleNamespace(pk=7, title="Sumar dos enteros",
                           description="<p>Lea a y b e imprima la suma.</p>",
                           input_description="<p>Una línea con dos enteros.</p>",
                           output_description="<p>Un entero.</p>")


def fake_submission(code="int total = 0\n", language="C", result=-2, statistic_info=None,
                    username="estudiante_uno", ip="192.0.2.7"):
    return SimpleNamespace(code=code, language=language, result=result, statistic_info=statistic_info or {},
                           username=username, ip=ip)


class ParseProblemIdsTests(SimpleTestCase):
    def test_sorted_deduplicated_list(self):
        self.assertEqual(parse_problem_ids("3, 1, 2, 1", None), [1, 2, 3])

    def test_file_ignores_blank_and_comment_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problems.txt"
            path.write_text("# autorizados\n2\n\n1\n", encoding="utf-8")
            self.assertEqual(parse_problem_ids(None, path), [1, 2])

    def test_invalid_arguments_are_rejected(self):
        with self.assertRaises(CommandError):
            parse_problem_ids(None, None)
        with self.assertRaises(CommandError):
            parse_problem_ids("1", "2")
        with self.assertRaises(CommandError):
            parse_problem_ids("1, abc", None)
        with self.assertRaises(CommandError):
            parse_problem_ids("1, 0", None)
        with self.assertRaises(CommandError):
            parse_problem_ids("", None)


class AnonymizeUnitTests(SimpleTestCase):
    def setUp(self):
        self.problem = fake_problem()

    def build(self, submission, actor="docente-a"):
        return anonymize.build_record(submission, self.problem, "AUTH-TEST-2026-001",
                                      "2026-10-18T10:00:00Z", actor)

    def test_record_validates_against_contract(self):
        record = self.build(fake_submission())
        validator = TutorExampleSerializer(data=record)
        self.assertTrue(validator.is_valid(), validator.errors)

    def test_wrong_answer_is_unknown_with_alternatives_and_low_confidence(self):
        record = self.build(fake_submission(result=-1, statistic_info={"time_cost": 900, "memory_cost": 2048}))
        validator = TutorExampleSerializer(data=record)
        self.assertTrue(validator.is_valid(), validator.errors)
        self.assertEqual(record["category"], "unknown")
        self.assertLessEqual(record["uncertainty"]["confidence"], 0.5)
        self.assertTrue(record["uncertainty"]["alternatives"])

    def test_compile_and_runtime_gain_their_factual_category(self):
        compilation = self.build(fake_submission(result=-2,
                                                 statistic_info={"err_info": "error: expected ';' before 'a'"}))
        self.assertEqual(compilation["category"], "compilation")
        runtime = self.build(fake_submission(result=4, statistic_info={"err_info": "segfault"}))
        self.assertEqual(runtime["category"], "runtime")

    def test_pseudonym_is_random_and_not_derived_from_source(self):
        first = self.build(fake_submission())
        second = self.build(fake_submission())
        self.assertNotEqual(first["example_id"], second["example_id"])
        self.assertNotIn("estudiante_uno", first["example_id"])

    def test_problem_context_is_plain_public_text(self):
        context = anonymize.problem_context(self.problem)
        self.assertNotIn("<p>", context)
        self.assertIn("Sumar dos enteros", context)
        self.assertIn("Entrada:", context)
        self.assertLessEqual(len(context), 1900)

    def test_long_problem_context_is_clamped(self):
        problem = SimpleNamespace(pk=9, title="Título", description="<p>" + "largo " * 500 + "</p>",
                                  input_description="", output_description="")
        self.assertLessEqual(len(anonymize.problem_context(problem)), 1900)

    def test_record_discards_username_ip_and_internal_submission_id(self):
        serialized = json.dumps(self.build(fake_submission()), ensure_ascii=False)
        self.assertNotIn("estudiante_uno", serialized)
        self.assertNotIn("192.0.2.7", serialized)
        self.assertNotIn("user_id", serialized)

    def test_detector_catches_identity_email_ip_and_credentials(self):
        code = ("# contacto: soporte@univalle.edu\n"
                "# ver también http://10.10.1.2/config\n"
                '# api_key = "SK-proj-123456"\n'
                "/* estudiante_uno */\n")
        record = self.build(fake_submission(code=code))
        with self.assertRaises(anonymize.ForbiddenFieldsError) as captured:
            anonymize.detect_forbidden_fields(record, {"estudiante_uno"})
        findings = "; ".join(captured.exception.findings)
        self.assertIn("correo", findings)
        self.assertIn("dirección IP", findings)
        self.assertIn("credencial", findings)
        self.assertIn("identidad", findings)
        # Los hallazgos no exponen el contenido secreto o personal.
        self.assertNotIn("soporte@univalle.edu", findings)
        self.assertNotIn("10.10.1.2", findings)
        self.assertNotIn("SK-proj-123456", findings)
        self.assertNotIn("estudiante_uno", findings)

    def test_detector_accepts_clean_record(self):
        record = self.build(fake_submission())
        self.assertEqual(anonymize.detect_forbidden_fields(record, {"estudiante_uno", "192.0.2.7"}), [])

    def test_review_stays_draft_without_human_approval(self):
        record = self.build(fake_submission())
        self.assertEqual(record["review"]["status"], "draft")
        self.assertIsNone(record["review"]["reviewer"])
        self.assertIsNone(record["review"]["approved_at"])


class ExportCommandTests(ProblemCreateTestBase):
    def setUp(self):
        self.admin = self.create_admin()
        self.problem = self.add_problem(DEFAULT_PROBLEM_DATA, self.admin)
        self.student = self.create_user("estudiante_uno", "clave")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.out = Path(self.directory.name)
        self.output_path = self.out / "export.json"
        self.constancia_path = self.out / "constancia.txt"
        self.auth_path = self.out / "auth.json"
        self.write_auth({"schema_version": "1.0", "authorization": "AUTH-TEST-2026-001",
                         "problems": [self.problem.id], "issued_by": "DIRECCION-TEST",
                         "issued_at": "2026-10-18"})
        self.create_submission(-2, "C")
        self.create_submission(-1, "Python3")
        self.create_submission(0, "C")       # aceptado: no es ejemplo
        self.create_submission(6, "C")       # pendiente
        self.create_submission(-1, "Rust")   # lenguaje no soportado

    def write_auth(self, payload):
        self.auth_path.write_text(json.dumps(payload), encoding="utf-8")

    def create_submission(self, result, language, code=None, contest=None):
        return Submission.objects.create(problem=self.problem, contest=contest,
                                         user_id=self.student.id, username=self.student.username,
                                         code=code if code is not None else "int total = 0;\n",
                                         language=language, result=result,
                                         statistic_info={"time_cost": 10, "memory_cost": 2048},
                                         ip="192.0.2.7")

    def snapshot(self):
        return list(Submission.objects.filter(problem=self.problem)
                    .order_by("create_time", "id").values())

    def base_args(self):
        return ["--problems", str(self.problem.id), "--authorization-file", str(self.auth_path),
                "--output", str(self.output_path), "--constancia", str(self.constancia_path),
                "--actor", "docente-a"]

    def call_with_output(self, *args):
        stdout = io.StringIO()
        call_command("export_authorized_submissions", *self.base_args(), *args, stdout=stdout)
        return stdout.getvalue()

    def call_unverified(self, *args):
        """Versión con identificador suelto: sin --authorization-file."""
        extra = [arg for arg in self.base_args() if not arg.startswith("--authorization-file") and arg != str(self.auth_path)]
        stdout = io.StringIO()
        call_command("export_authorized_submissions", *extra, "--authorization", "AUTH-SIN-DOCS",
                     *args, stdout=stdout)
        return stdout.getvalue()

    def call_expect_error(self, *args):
        with self.assertRaises(CommandError) as captured:
            self.call_with_output(*args)
        return captured.exception

    def test_missing_authorization_blocked_with_constancia(self):
        stdout = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("export_authorized_submissions", "--problems", str(self.problem.id),
                         "--output", str(self.output_path), "--constancia", str(self.constancia_path),
                         stdout=stdout)
        self.assertFalse(self.output_path.exists())
        self.assertTrue(self.constancia_path.exists())
        text = self.constancia_path.read_text(encoding="utf-8")
        self.assertIn("constancia de no uso", text)
        self.assertIn(str(self.problem.id), text)
        self.assertIn("ninguno", text)

    def test_unverified_identifier_blocks_real_export(self):
        with self.assertRaises(CommandError) as captured:
            self.call_unverified()
        self.assertIn("verificable", str(captured.exception))
        self.assertFalse(self.output_path.exists())
        self.assertTrue(self.constancia_path.exists())

    def test_unverified_identifier_allows_dry_run_and_writes_nothing(self):
        stdout_value = self.call_unverified("--dry-run")
        self.assertIn("Dry-run correcto", stdout_value)
        summary = extract_json(stdout_value)
        self.assertEqual(summary["resumen"]["exportado"], 2)
        self.assertFalse(self.output_path.exists())
        self.assertFalse(self.constancia_path.exists())

    def test_invalid_authorization_file_blocked(self):
        self.write_auth({"sin": "claves"})
        exception = self.call_expect_error()
        self.assertIn("autorización", str(exception))
        self.assertFalse(self.output_path.exists())
        self.assertTrue(self.constancia_path.exists())

    def test_authorization_must_cover_requested_problems(self):
        self.write_auth({"schema_version": "1.0", "authorization": "AUTH-TEST-2026-001", "problems": [99999]})
        exception = self.call_expect_error()
        self.assertIn("no cubre", str(exception))
        self.assertFalse(self.output_path.exists())

    def test_successful_export_is_anonymized_valid_and_read_only(self):
        before = self.snapshot()
        self.call_with_output()
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.output_path.exists())
        text = self.output_path.read_text(encoding="utf-8")
        self.assertNotIn("estudiante_uno", text)
        self.assertNotIn("192.0.2.7", text)
        payload = json.loads(text)
        manifest, records = payload["manifest"], payload["records"]
        self.assertEqual(manifest["authorization"], "AUTH-TEST-2026-001")
        self.assertEqual(manifest["authorization_verification"], "archivo-documentado")
        self.assertEqual(manifest["actor"], "docente-a")
        counts = manifest["counts"]
        self.assertEqual(counts["total_evaluado"], 5)
        self.assertEqual(counts["exportado"], 2)
        self.assertEqual(counts["rechazado_por_veredicto"], {"0": 1, "6": 1})
        self.assertEqual(counts["rechazado_por_lenguaje"], {"Rust": 1})
        self.assertEqual(counts["rechazado_por_problema"], {"inexistente": [], "no-visible": [], "de-concurso": []})
        for record in records:
            validator = TutorExampleSerializer(data=record)
            self.assertTrue(validator.is_valid(), validator.errors)
            self.assertEqual(record["provenance"]["kind"], "historical")
            self.assertEqual(record["provenance"]["authorization"], "AUTH-TEST-2026-001")
        self.assertFalse(any(path.name.endswith(".tmp") for path in self.out.iterdir()))

    def test_forbidden_fields_abort_without_partial_files(self):
        self.create_submission(-2, "C", code="# soporte: soporte@univalle.edu\n")
        exception = self.call_expect_error()
        self.assertIn("información prohibida", str(exception))
        self.assertFalse(self.output_path.exists())
        self.assertFalse(any(path.name.endswith(".tmp") for path in self.out.iterdir()))
        text = self.constancia_path.read_text(encoding="utf-8")
        self.assertIn("información prohibida", text)
        self.assertNotIn("soporte@univalle.edu", text)

    def test_dry_run_writes_nothing_and_counts_are_reproducible(self):
        first = extract_json(self.call_with_output("--dry-run"))
        self.assertFalse(self.output_path.exists())
        self.assertEqual(first["escritura"], "ninguna (dry-run)")
        second = extract_json(self.call_with_output("--dry-run"))
        self.assertEqual(first["resumen"]["exportado"], second["resumen"]["exportado"])
        self.assertEqual(first["resumen"]["total_evaluado"], second["resumen"]["total_evaluado"])
        self.assertEqual(first["resumen"]["rechazado_por_veredicto"], second["resumen"]["rechazado_por_veredicto"])

    def test_contest_submission_is_never_exported(self):
        contest = Contest.objects.create(title="Contest", description="x", real_time_rank=True, rule_type="ACM",
                                         start_time=timezone.now() - timedelta(days=1),
                                         end_time=timezone.now() + timedelta(days=1), created_by=self.admin)
        self.create_submission(-2, "C", contest=contest)
        summary = extract_json(self.call_with_output("--dry-run"))["resumen"]
        self.assertEqual(summary["total_evaluado"], 5)
        self.assertEqual(summary["exportado"], 2)

    def test_contest_problem_request_counts_as_rejected(self):
        contest = Contest.objects.create(title="Contest", description="x", real_time_rank=True, rule_type="ACM",
                                         start_time=timezone.now() - timedelta(days=1),
                                         end_time=timezone.now() + timedelta(days=1), created_by=self.admin)
        self.problem.contest_id = contest.id
        self.problem.save()
        counts = extract_json(self.call_with_output("--dry-run"))["resumen"]
        self.assertEqual(counts["rechazado_por_problema"]["de-concurso"], [self.problem.id])
        self.assertEqual(counts["total_evaluado"], 0)


def extract_json(stdout_value):
    return json.loads(stdout_value.split("\n}\n", 1)[0] + "\n}\n")
