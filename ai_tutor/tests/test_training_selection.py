"""Las selecciones aquí son fixtures: nunca autorizan un entrenamiento real."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from ai_tutor.dataset.pipeline import sha
from ai_tutor.ml.training import train_model, training_source


class TrainingSelectionTests(SimpleTestCase):
    def test_explicit_trainable_source_matches_reviewed_benchmark(self):
        source = {"model_id": "fixture/base", "revision": "b" * 40, "license": "fixture", "provenance": "Referencia de prueba."}
        selection = {"model_id": "fixture/base-GGUF", "training_model": source}
        self.assertEqual(training_source(selection, {"training_model": dict(source)}), source)

    def test_trainable_source_cannot_drift_from_reviewed_benchmark(self):
        source = {"model_id": "fixture/base", "revision": "b" * 40, "license": "fixture", "provenance": "Referencia de prueba."}
        for candidate in ({}, {"training_model": {**source, "revision": "c" * 40}}):
            with self.subTest(candidate=candidate), self.assertRaisesRegex(ValueError, "benchmark"):
                training_source({"model_id": "fixture/base-GGUF", "training_model": source}, candidate)

    def test_rejects_non_trainable_or_unpinned_source(self):
        source = {"model_id": "fixture/base", "revision": "b" * 40, "license": "fixture", "provenance": "Referencia de prueba."}
        for changed in ({"model_id": "fixture/base-GGUF"}, {"revision": "main"}, {"provenance": ""}, {"license": None}):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "training_model"):
                training_source({"training_model": {**source, **changed}}, {})

    def test_original_safetensors_identity_remains_supported(self):
        source = {"model_id": "fixture/base", "revision": "b" * 40, "license": "fixture"}
        self.assertEqual(training_source(source, dict(source)), source)

    def test_gguf_without_trainable_source_is_rejected_before_heavy_imports(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = {"model_id": "fixture/model-GGUF", "revision": "a" * 40, "license": "fixture"}
            reports = [{"candidate": candidate, "responses": [{"human_review": "approved"}]},
                       {"candidate": {"model_id": "fixture/other", "revision": "b" * 40}}]
            benchmark = root / "benchmark.json"
            benchmark.write_text(json.dumps({"reports": reports}))
            selection = {**candidate, "decision": "selected", "reviewer": "fixture-reviewer",
                         "benchmark_file": benchmark.name, "benchmark_sha256": sha(benchmark), "rubric_version": "fixture"}
            source = root / "selection.json"
            source.write_text(json.dumps(selection))
            original_import = __import__

            def guarded_import(name, *args, **kwargs):
                if name == "torch":
                    raise AssertionError("Se intentó cargar un GGUF con el entrenador safetensors.")
                return original_import(name, *args, **kwargs)

            with patch("ai_tutor.ml.training.load_dataset", return_value=({}, {"version": "fixture"})), \
                    patch("builtins.__import__", side_effect=guarded_import), \
                    self.assertRaisesRegex(ValueError, "training_model"):
                train_model(root, source, root / "output")
