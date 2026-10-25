from pathlib import Path
import tempfile
from unittest import mock

from django.test import SimpleTestCase
from utils.releases import release_notes


class RepositoryReleaseTests(SimpleTestCase):
    def test_notes_come_from_checkout_and_pin_source_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "VERSION").write_text("2.0.0\n", encoding="utf-8")
            text = "## [Unreleased]\n- No publicar todavía\n## [2.0.0] - 2026-10-25\n### Correo\n- Primer cambio\n"
            (root / "CHANGELOG.md").write_text(text, encoding="utf-8")
            with mock.patch.dict("os.environ", {"APP_REVISION": "a" * 40}):
                result = release_notes(root)
            self.assertEqual(result["local_version"], "2.0.0")
            self.assertEqual(result["update"][0]["details"], ["Correo: Primer cambio"])
            self.assertTrue(result["update"][0]["is_current"])
            self.assertIn("/blob/" + "a" * 40 + "/CHANGELOG.md", result["source_url"])
            (root / "CHANGELOG.md").write_text(text.replace("Primer cambio", "Cambio editado"), encoding="utf-8")
            self.assertEqual(release_notes(root)["update"][0]["details"], ["Correo: Cambio editado"])

    def test_invalid_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "VERSION").write_text("../../otra-ruta", encoding="utf-8")
            with self.assertRaises(ValueError):
                release_notes(root)
