from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class HealthTests(SimpleTestCase):
    def test_revision_publica(self):
        with patch.dict("os.environ", {"APP_REVISION": "a" * 40}):
            response = self.client.get(reverse("runtime_version"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"revision": "a" * 40})

    @patch("utils.health.get_redis_connection")
    @patch("utils.health.connection")
    def test_dependencias_disponibles(self, database, redis):
        response = self.client.get(reverse("readiness"))
        self.assertEqual(response.status_code, 200)
        database.cursor.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")
        redis.return_value.ping.assert_called_once()

    @patch("utils.health.connection")
    def test_fallo_bd_no_expone_detalles(self, database):
        database.cursor.side_effect = RuntimeError("credencial-interna")
        response = self.client.get(reverse("readiness"))
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "credencial-interna", status_code=503)

    @patch("utils.health.get_redis_connection")
    @patch("utils.health.connection")
    def test_fallo_redis(self, database, redis):
        redis.return_value.ping.side_effect = ConnectionError()
        self.assertEqual(self.client.get(reverse("readiness")).status_code, 503)
