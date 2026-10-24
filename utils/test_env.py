import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from utils.shortcuts import env_list, get_env_bool

VAR = "OJ_TEST_BOOL"


def _entorno(**valores):
    return mock.patch.dict(os.environ, valores, clear=False)


class GetEnvBoolTests(SimpleTestCase):
    def test_valores_verdaderos(self):
        for valor in ("1", "true", "True", "TRUE", " yes ", "on", "ON", "si", "SI", "sí", "Sí"):
            with _entorno(**{VAR: valor}):
                self.assertIs(get_env_bool(VAR), True, valor)

    def test_valores_falsos(self):
        for valor in ("0", "false", "False", " NO ", "off", "OFF", "", "   "):
            with _entorno(**{VAR: valor}):
                self.assertIs(get_env_bool(VAR, True), False, repr(valor))

    def test_valor_invalido_falla_cerrado(self):
        for valor in ("tru", "2", "enabled", "verdadero", "1.0"):
            with _entorno(**{VAR: valor}):
                with self.assertRaises(ImproperlyConfigured) as ctx:
                    get_env_bool(VAR)
                self.assertIn(VAR, str(ctx.exception))

    def test_ausente_usa_default(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(VAR, None)
            self.assertIs(get_env_bool(VAR), False)
            self.assertIs(get_env_bool(VAR, True), True)


class EnvListTests(SimpleTestCase):
    P, A = "OJ_TEST_PRIMARIA", "OJ_TEST_ALIAS"

    def _resolver(self, default="d1,d2", **valores):
        with mock.patch.dict(os.environ, valores):
            for nombre in (self.P, self.A):
                if nombre not in valores:
                    os.environ.pop(nombre, None)
            return env_list(self.P, self.A, default)

    def test_default_si_ninguna_definida(self):
        self.assertEqual(self._resolver(), ["d1", "d2"])
        self.assertEqual(self._resolver(default=""), [])

    def test_primaria(self):
        self.assertEqual(self._resolver(**{self.P: " a.com, b.com ,,"}), ["a.com", "b.com"])

    def test_alias_si_no_hay_primaria(self):
        self.assertEqual(self._resolver(**{self.A: "x.com"}), ["x.com"])

    def test_ambas_iguales(self):
        self.assertEqual(self._resolver(**{self.P: "a.com,b.com", self.A: "a.com, b.com"}), ["a.com", "b.com"])

    def test_ambas_distintas_es_ambiguo(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._resolver(**{self.P: "a.com", self.A: "b.com"})
        self.assertIn(self.P, str(ctx.exception))
        self.assertIn(self.A, str(ctx.exception))

    def test_vacia_cuenta_como_no_definida(self):
        # Compose suele pasar variables opcionales vacías (${X:-}).
        self.assertEqual(self._resolver(**{self.P: "  "}), ["d1", "d2"])
        self.assertEqual(self._resolver(**{self.P: "", self.A: "x.com"}), ["x.com"])
        self.assertEqual(self._resolver(**{self.P: "a.com", self.A: ""}), ["a.com"])
