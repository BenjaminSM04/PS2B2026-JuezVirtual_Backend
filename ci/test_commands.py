from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from account.models import AdminType, User


class AdministratorTests(TestCase):
    @patch("utils.management.commands.create_admin.getpass", side_effect=["PruebaSegura123!", "PruebaSegura123!"])
    def test_creacion_interactiva_sin_imprimir_clave(self, prompt):
        output = StringIO()
        call_command("create_admin", username="Administrador", email="admin@example.invalid", stdout=output)
        user = User.objects.get(username="administrador")
        self.assertEqual(user.admin_type, AdminType.SUPER_ADMIN)
        self.assertTrue(user.check_password("PruebaSegura123!"))
        self.assertNotIn("PruebaSegura123!", output.getvalue())

    @patch("utils.management.commands.create_admin.getpass")
    def test_no_sobrescribe_usuario_existente(self, prompt):
        User.objects.create(username="existente", password="conservar")
        with self.assertRaises(CommandError):
            call_command("create_admin", username="existente")
        prompt.assert_not_called()
        self.assertEqual(User.objects.get(username="existente").password, "conservar")

    @patch("utils.management.commands.create_admin.getpass", side_effect=["primera", "distinta"])
    def test_confirmacion_fallida_no_crea_usuario(self, prompt):
        with self.assertRaises(CommandError):
            call_command("create_admin", username="nuevo")
        self.assertFalse(User.objects.exists())
