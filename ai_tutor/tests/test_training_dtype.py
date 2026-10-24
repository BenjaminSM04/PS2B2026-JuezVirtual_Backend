from types import SimpleNamespace

from django.test import SimpleTestCase

from ai_tutor.ml.training import training_dtype


def fake_torch(available, capability=(0, 0)):
    # is_bf16_supported() devolvería True también en Turing (emulado); no debe consultarse.
    cuda = SimpleNamespace(is_available=lambda: available, get_device_capability=lambda index: capability,
                           is_bf16_supported=lambda: True)
    return SimpleNamespace(cuda=cuda, float32="float32", float16="float16", bfloat16="bfloat16")


class TrainingDtypeTests(SimpleTestCase):
    def test_cpu_usa_float32(self):
        self.assertEqual(training_dtype(fake_torch(False)), "float32")

    def test_turing_usa_fp16_aunque_bf16_se_emule(self):
        self.assertEqual(training_dtype(fake_torch(True, (7, 5))), "float16")

    def test_ampere_o_superior_usa_bf16(self):
        self.assertEqual(training_dtype(fake_torch(True, (8, 0))), "bfloat16")
        self.assertEqual(training_dtype(fake_torch(True, (8, 9))), "bfloat16")
