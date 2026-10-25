"""Demostración sintética explícita: nunca equivale a aprobación humana."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from ai_tutor.dataset.pipeline import build_dataset, load_dataset, train, evaluate


class TechnicalDemoTests(SimpleTestCase):
    def examples(self):
        source = Path(__file__).parents[2] / "docs/ai-tutor/variantes/ejemplos-borrador.json"
        return json.loads(source.read_text(encoding="utf-8"))

    def test_demo_keeps_drafts_and_requires_explicit_loading_training_and_evaluation(self):
        records = self.examples()
        original = copy.deepcopy(records)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = build_dataset(records, root / "dataset", technical_demo=True)
            self.assertEqual(manifest["scope"], "technical-demo")
            self.assertEqual(records, original)
            with self.assertRaises(ValueError):
                load_dataset(root / "dataset")
            parts, _ = load_dataset(root / "dataset", technical_demo=True)
            self.assertEqual(sum(map(len, parts.values())), 36)
            self.assertEqual(len(manifest["excluded_duplicate_code_ids"]), 18)
            self.assertTrue(all(item["review"]["status"] == "draft" for values in parts.values() for item in values))
            with self.assertRaises(ValueError):
                train(root / "dataset", root / "forbidden.json")
            model = train(root / "dataset", root / "classifier.json", technical_demo=True)
            self.assertEqual(model["scope"], "technical-demo")
            with self.assertRaises(ValueError):
                evaluate(root / "dataset", root / "classifier.json")
            result = evaluate(root / "dataset", root / "classifier.json", technical_demo=True)
            self.assertEqual(result["scope"], "technical-demo")
            self.assertIn("macro_f1", result["overall"])

    def test_demo_rejects_historical_data_and_rejected_records(self):
        for historical in (True, False):
            records = self.examples()
            if historical:
                records[0]["provenance"].update(kind="historical", authorization="fixture-no-autorizacion-real")
            else:
                records[0]["review"].update(status="rejected", reviewer="fixture", reviewed_at="2026-10-24T00:00:00Z")
            with self.subTest(historical=historical), TemporaryDirectory() as directory, self.assertRaises(ValueError):
                build_dataset(records, Path(directory) / "dataset", technical_demo=True)
