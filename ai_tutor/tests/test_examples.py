import copy
import json
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from ai_tutor.dataset.schema import TutorExampleSerializer


class ExampleValidationTests(SimpleTestCase):
    def setUp(self):
        self.path = Path(__file__).parents[2] / "docs/ai-tutor/ejemplos-positivos.json"
        self.records = json.loads(self.path.read_text(encoding="utf-8"))

    def test_all_configured_languages_and_categories_have_valid_examples(self):
        self.assertEqual({r["language"] for r in self.records}, {"C", "C++", "Java", "Python3", "Golang", "JavaScript"})
        self.assertEqual({r["category"] for r in self.records}, {"compilation", "runtime", "logic", "complexity", "concept", "unknown"})
        for record in self.records:
            serializer = TutorExampleSerializer(data=record)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertNotEqual(record["review"]["status"], "approved")

    def test_unknown_fields_at_every_level_are_rejected(self):
        for field in (None, "review", "provenance", "uncertainty", "hints"):
            record = copy.deepcopy(self.records[0])
            target = record if field is None else record[field]
            target["secret"] = "no permitido"
            self.assertFalse(TutorExampleSerializer(data=record).is_valid(), field)

    def test_rejects_self_review_and_missing_approval_evidence(self):
        for reviewer, date in (("BenjaminSM04", "2026-09-30T12:00:00Z"), ("otro-revisor", None)):
            record = copy.deepcopy(self.records[0])
            record["review"].update(status="approved", reviewer=reviewer, reviewed_at=date, approved_at=date)
            self.assertFalse(TutorExampleSerializer(data=record).is_valid())
        record["review"].update(reviewer="otro-revisor", reviewed_at="2026-09-30T12:00:00Z",
                                approved_at="2026-09-30T12:00:00Z", notes="Revisión de prueba, no aprobación real.")
        self.assertTrue(TutorExampleSerializer(data=record).is_valid())

    def test_inconsistent_category_verdict_and_levels_are_rejected(self):
        for change in ({"verdict": 0}, {"category": "runtime"}, {"language": "Rust"},
                       {"hints": {"concept": "una pista", "location": "otra pista"}},
                       {"uncertainty": {"confidence": 1.2, "alternatives": [], "reason": "sin prueba"}}):
            record = copy.deepcopy(self.records[0])
            record.update(change)
            self.assertFalse(TutorExampleSerializer(data=record).is_valid(), change)

    def test_command_accepts_positive_and_ambiguous_but_rejects_negative(self):
        call_command("validate_tutor_examples", str(self.path))
        call_command("validate_tutor_examples", str(self.path.with_name("ejemplos-ambiguos.json")))
        with self.assertRaises(CommandError):
            call_command("validate_tutor_examples", str(self.path.with_name("ejemplos-negativos.json")))

    def test_historical_provenance_requires_authorization(self):
        record = copy.deepcopy(self.records[0])
        record["provenance"].update(kind="historical", authorization=None)
        self.assertFalse(TutorExampleSerializer(data=record).is_valid())
