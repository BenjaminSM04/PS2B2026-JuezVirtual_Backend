import copy
import csv
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from ai_tutor.dataset.review import SHEET_COLUMNS
from ai_tutor.dataset.schema import TutorExampleSerializer

REVIEWER = "revisor-prueba"


class ReviewSheetTests(SimpleTestCase):
    """Las identidades son de prueba: ninguna decisión aquí es una revisión pedagógica real."""

    def setUp(self):
        path = Path(__file__).parents[2] / "docs/ai-tutor/ejemplos-positivos.json"
        self.records = json.loads(path.read_text(encoding="utf-8"))[:4]
        self.ids = [record["example_id"] for record in self.records]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.source = self.write_source(self.records)

    def write_source(self, records, name="origen.json"):
        path = self.dir / name
        path.write_text(json.dumps(records, indent=2, ensure_ascii=True), encoding="utf-8")
        return path

    def export(self, source=None, name="planilla.csv", **options):
        sheet = self.dir / name
        call_command("export_tutor_review_sheet", str(source or self.source), str(sheet), stdout=StringIO(), **options)
        return sheet

    def read_sheet(self, sheet):
        with sheet.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def write_sheet(self, rows, name="llena.csv", delimiter=","):
        path = self.dir / name
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SHEET_COLUMNS, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def filled(self, count=2, **changes):
        self.exports = getattr(self, "exports", 0) + 1
        rows = self.read_sheet(self.export(name=f"planilla-{self.exports}.csv"))
        for row in rows[:count]:
            row.update({"decision": "approved", "reviewer": REVIEWER, "notes": "Revisión de prueba, no aprobación real.", **changes})
        return rows

    def apply(self, rows, reviewer=REVIEWER, source=None, delimiter=","):
        output = self.dir / "salida.json"
        out = StringIO()
        call_command("apply_tutor_review_sheet", str(source or self.source), str(self.write_sheet(rows, delimiter=delimiter)),
                     str(output), reviewer=reviewer, stdout=out)
        return output, out.getvalue()

    def assert_rejected(self, rows, text, **kwargs):
        with self.assertRaises(CommandError) as raised:
            self.apply(rows, **kwargs)
        self.assertIn(text, str(raised.exception))
        self.assertFalse((self.dir / "salida.json").exists())

    def test_export_has_bom_columns_and_only_open_examples(self):
        self.records[0]["review"].update(reviewer="otro-revisor", reviewed_at="2026-10-01T10:00:00Z",
                                         status="rejected", notes="Cerrado de prueba.")
        source = self.write_source(self.records, "cerrado.json")
        sheet = self.export(source=source, name="abiertos.csv")
        self.assertEqual(sheet.read_bytes()[:3], b"\xef\xbb\xbf")
        rows = self.read_sheet(sheet)
        self.assertEqual([row["example_id"] for row in rows], self.ids[1:])
        self.assertEqual(list(rows[0]), list(SHEET_COLUMNS))
        self.assertEqual(rows[0]["faulty_code"], self.records[1]["faulty_code"])
        self.assertTrue(all(not row[column] for row in rows for column in ("decision", "reviewer", "notes")))
        with self.assertRaises(CommandError):
            self.export(source=source, name="abiertos.csv")

    def test_export_refuses_invalid_source_and_no_pending(self):
        broken = copy.deepcopy(self.records)
        broken[0]["verdict"] = 0
        with self.assertRaises(CommandError):
            self.export(source=self.write_source(broken, "roto.json"), name="a.csv")
        for record in self.records:
            record["review"].update(reviewer="otro-revisor", reviewed_at="2026-10-01T10:00:00Z",
                                    status="rejected", notes="Cerrado de prueba.")
        with self.assertRaises(CommandError):
            self.export(source=self.write_source(self.records, "todos.json"), name="b.csv")

    def test_roundtrip_applies_decisions_and_keeps_the_rest(self):
        rows = self.filled(count=3)
        rows[1].update(decision="rejected", notes="Pistas repetidas, prueba.")
        rows[2].update(decision="review", notes="Dudas sobre la categoría, prueba.")
        output, message = self.apply(rows)
        self.assertIn("approved=1 rejected=1 review=1", message)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual([r["review"]["status"] for r in result], ["approved", "rejected", "review", "review"])
        first = result[0]["review"]
        self.assertEqual((first["reviewer"], first["notes"]), (REVIEWER, "Revisión de prueba, no aprobación real."))
        self.assertTrue(first["reviewed_at"] and first["approved_at"])
        self.assertIsNone(result[1]["review"]["approved_at"])
        self.assertEqual(result[3], self.records[3])
        for record in result:
            self.assertTrue(TutorExampleSerializer(data=record).is_valid())
        self.assertEqual(json.loads(self.source.read_text(encoding="utf-8")), self.records)

    def test_semicolon_delimiter_and_windows_newlines_are_tolerated(self):
        rows = self.filled(count=1)
        rows[0]["faulty_code"] = rows[0]["faulty_code"].replace("\n", "\r\n")
        output, _ = self.apply(rows, delimiter=";")
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))[0]["faulty_code"], self.records[0]["faulty_code"])

    def test_rejects_reviewer_equal_to_author(self):
        rows = self.filled(count=1, reviewer=self.records[0]["review"]["author"])
        self.assert_rejected(rows, "distinto del autor", reviewer=self.records[0]["review"]["author"])
        rows[0]["reviewer"] = rows[0]["reviewer"].upper()
        self.assert_rejected(rows, "distinto del autor", reviewer=rows[0]["reviewer"])

    def test_rejects_reviewer_different_from_option(self):
        self.assert_rejected(self.filled(count=2, reviewer="otra-persona"), "no coincide con --reviewer")
        self.assert_rejected(self.filled(count=1, reviewer=""), "no coincide con --reviewer")

    def test_rejects_empty_notes(self):
        self.assert_rejected(self.filled(count=1, notes="  "), "notas son obligatorias")

    def test_rejects_invalid_decision(self):
        self.assert_rejected(self.filled(count=1, decision="aprobado"), "no válida")

    def test_rejects_duplicate_rows(self):
        rows = self.filled(count=1)
        self.assert_rejected(rows + [dict(rows[0])], "duplicado")

    def test_rejects_unknown_id(self):
        self.assert_rejected(self.filled(count=1, example_id="no-existe"), "exactamente una vez")

    def test_rejects_ambiguous_id_in_source(self):
        source = self.write_source(self.records + [copy.deepcopy(self.records[0])], "dup.json")
        self.assert_rejected(self.filled(count=1), "exactamente una vez", source=source)

    def test_closed_decisions_are_preserved(self):
        rows = self.filled(count=1)
        self.records[0]["review"].update(reviewer="otro-revisor", reviewed_at="2026-10-01T10:00:00Z",
                                         status="rejected", notes="Cerrado de prueba.")
        source = self.write_source(self.records, "cerrado.json")
        self.assert_rejected(rows, "decisión cerrada", source=source)

    def test_rejects_altered_pedagogical_content(self):
        for column in ("explanation", "hint_strategy", "category", "faulty_code", "author"):
            rows = self.filled(count=1)
            rows[0][column] += " alterado"
            self.assert_rejected(rows, "se vuelve a exportar la planilla")

    def test_altered_content_without_decision_is_ignored(self):
        rows = self.filled(count=1)
        rows[1]["explanation"] = "cambiado sin decisión"
        output, message = self.apply(rows)
        self.assertIn("approved=1", message)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))[1], self.records[1])

    def test_is_all_or_nothing(self):
        rows = self.filled(count=3)
        rows[2]["notes"] = ""
        self.assert_rejected(rows, "Fila 4")

    def test_empty_rows_and_rows_without_decision_are_ignored(self):
        rows = self.filled(count=1)
        blank = dict.fromkeys(SHEET_COLUMNS, "")
        output, message = self.apply([blank, rows[0], blank] + rows[1:])
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("approved=1 rejected=0 review=0", message)
        self.assertEqual([r["review"]["status"] for r in result], ["approved", "review", "review", "review"])

    def test_sheet_without_decisions_missing_columns_and_existing_output_fail(self):
        self.assert_rejected(self.filled(count=0), "no contiene decisiones")
        rows = self.filled(count=1)
        sheet = self.dir / "sin-columna.csv"
        sheet.write_text("example_id,decision\nx,approved\n", encoding="utf-8")
        with self.assertRaises(CommandError):
            call_command("apply_tutor_review_sheet", str(self.source), str(sheet), str(self.dir / "s2.json"), reviewer=REVIEWER)
        (self.dir / "salida.json").write_text("[]", encoding="utf-8")
        with self.assertRaises(CommandError):
            self.apply(rows)
        self.assertEqual((self.dir / "salida.json").read_text(encoding="utf-8"), "[]")
