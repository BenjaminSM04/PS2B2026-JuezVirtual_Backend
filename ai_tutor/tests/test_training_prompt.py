import json
import subprocess
import sys
from django.test import SimpleTestCase


class TrainingPromptTests(SimpleTestCase):
    def test_dataset_schema_does_not_load_application_models(self):
        code = "from django.conf import settings; settings.configure(USE_I18N=False,INSTALLED_APPS=[]); import django; django.setup(); from ai_tutor.dataset.schema import TutorExampleSerializer; import sys; assert 'problem.models' not in sys.modules"
        result = subprocess.run([sys.executable, "-c", code], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_training_uses_the_runtime_context_without_leaking_targets(self):
        from ai_tutor.ml.prompt import training_messages, SYSTEM_PROMPT
        item = {"problem": "Problema público", "faulty_code": "fragmento", "language": "Python3", "verdict": -1,
                "concept": "Acumulador", "category": "logic", "evidence": ["observación pública"],
                "hints": {"concept": "OBJETIVO_NO_INCLUIR_EN_PROMPT"}}
        for level in (1, 2, 3):
            messages = training_messages(item, level)
            self.assertEqual(messages[0], {"role": "system", "content": SYSTEM_PROMPT})
            data = json.loads(messages[1]["content"])
            self.assertEqual(data["context"]["level"], level)
            self.assertEqual(data["context"]["action"], "hint")
            self.assertEqual(data["context"]["problem"]["description"], item["problem"])
            self.assertEqual(data["context"]["code"], item["faulty_code"])
            self.assertNotIn("OBJETIVO_NO_INCLUIR_EN_PROMPT", messages[1]["content"])
