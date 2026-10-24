import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import SimpleTestCase
from ai_tutor.dataset.pipeline import build_dataset, check_partitions, train, evaluate, load_dataset


class PipelineTests(SimpleTestCase):
    def examples(self):
        source = Path(__file__).parents[2] / "docs/ai-tutor/ejemplos-positivos.json"
        base = json.loads(source.read_text(encoding="utf-8"))[0]
        items = []
        for index in range(12):
            item = copy.deepcopy(base)
            item.update(example_id="fixture-" + str(index), problem="Problema sintético de prueba " + str(index), faulty_code="int prueba_" + str(index) + ";")
            # Identidades exclusivamente ficticias de esta prueba; no es un dataset aprobado real.
            item["review"].update(author="autor-ficticio-test", reviewer="revisor-ficticio-test", status="approved",
                authored_at="2026-01-01T00:00:00Z", reviewed_at="2026-01-02T00:00:00Z", approved_at="2026-01-02T00:00:00Z")
            items.append(item)
        return items

    def test_reproducible_build_train_and_held_out_evaluation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            first = build_dataset(self.examples(), path / "v1")
            second = build_dataset(self.examples(), path / "v2")
            self.assertEqual(first, second)
            train(path / "v1", path / "model.json")
            result = evaluate(path / "v1", path / "model.json")
            self.assertIn("macro_f1", result["overall"])
            self.assertEqual(result["dataset_version"], first["version"])

    def test_unreviewed_records_and_contamination_rejected(self):
        items = self.examples()
        with self.assertRaises(ValueError):
            check_partitions({"train": items[:1], "test": items[:1]})
        items[0]["review"].update(status="review", approved_at=None)
        with TemporaryDirectory() as directory, self.assertRaises(ValueError):
            build_dataset(items, Path(directory) / "v1")

    def test_modified_partition_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "dataset"
            build_dataset(self.examples(), path)
            with (path / "test.jsonl").open("a") as stream:
                stream.write("{}\n")
            with self.assertRaises(ValueError):
                load_dataset(path)
