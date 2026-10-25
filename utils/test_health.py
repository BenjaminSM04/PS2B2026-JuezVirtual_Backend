from unittest import mock

from django.test import Client, TestCase


class HealthzTests(TestCase):
    def test_ok_sin_autenticacion(self):
        for url in ("/healthz", "/api/healthz"):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), {"status": "ok"})
            self.assertIn("no-cache", resp["Cache-Control"])

    def test_head_permitido(self):
        self.assertEqual(self.client.head("/healthz").status_code, 200)

    def test_no_crea_sesion(self):
        resp = self.client.get("/healthz")
        self.assertNotIn("sessionid", resp.cookies)

    def test_fallo_de_bd_devuelve_503_sin_detalles(self):
        with mock.patch("utils.health.connection") as conexion:
            conexion.cursor.side_effect = RuntimeError("secreto-interno")
            with self.assertLogs("utils.health", level="ERROR"):
                resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json(), {"status": "unavailable"})
        self.assertNotIn("secreto-interno", resp.content.decode())

    def test_fallo_de_cache_devuelve_503(self):
        with mock.patch("utils.health.cache") as cache:
            cache.get.side_effect = ConnectionError("redis caido")
            with self.assertLogs("utils.health", level="ERROR"):
                resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json(), {"status": "unavailable"})

    def test_otros_metodos_405_incluso_con_csrf_activo(self):
        cliente = Client(enforce_csrf_checks=True)
        for metodo in ("post", "put", "patch", "delete"):
            resp = getattr(cliente, metodo)("/healthz")
            self.assertEqual(resp.status_code, 405, metodo)
