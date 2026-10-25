import importlib.util
from pathlib import Path
from unittest.mock import Mock
from django.test import SimpleTestCase


class ExportProvenanceTests(SimpleTestCase):
    def test_remote_export_pins_both_weights_and_tokenizer(self):
        path = Path(__file__).parents[2] / "scripts/export_technical_model.py"
        spec = importlib.util.spec_from_file_location("export_model_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        model, tokenizer = Mock(), Mock()
        source = {"model_id": "fixture/base", "revision": "a"*40}
        module.load_export_base(source, model, tokenizer, "fixture-dtype")
        for loader in (model, tokenizer):
            self.assertEqual(loader.from_pretrained.call_args.kwargs["revision"], source["revision"])
            self.assertFalse(loader.from_pretrained.call_args.kwargs["trust_remote_code"])
        self.assertTrue(model.from_pretrained.call_args.kwargs["use_safetensors"])
