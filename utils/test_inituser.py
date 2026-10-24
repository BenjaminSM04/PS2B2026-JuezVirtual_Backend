from io import StringIO
import secrets
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase

from account.models import AdminType, User, UserProfile


class InitUserTests(TestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(32)

    def invoke(self, **options):
        return call_command("inituser", username="admin-ensayo", action="create_super_admin",
                            stdout=StringIO(), **options)

    def test_creates_admin_and_profile_with_valid_password(self):
        self.invoke(password=self.password)
        user = User.objects.get(username="admin-ensayo")
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.admin_type, AdminType.SUPER_ADMIN)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_existing_account_is_never_overwritten(self):
        user = User.objects.create(username="admin-ensayo")
        user.set_password(self.password)
        user.save()
        existing_password = user.password
        with self.assertRaises(CommandError):
            self.invoke(password=secrets.token_urlsafe(32))
        user.refresh_from_db()
        self.assertEqual(user.password, existing_password)
        self.assertEqual(user.admin_type, AdminType.REGULAR_USER)

    def test_rejects_weak_password_without_creating_rows(self):
        with self.assertRaises(CommandError):
            self.invoke(password="rootroot")
        self.assertEqual(User.objects.count(), 0)

    @patch("utils.management.commands.inituser.sys.stdin.isatty", return_value=True)
    @patch("utils.management.commands.inituser.getpass.getpass")
    def test_interactive_password(self, prompt, terminal):
        prompt.return_value = self.password
        self.invoke()
        self.assertEqual(prompt.call_count, 2)
        self.assertEqual(User.objects.count(), 1)

    @patch("utils.management.commands.inituser.sys.stdin.isatty", return_value=False)
    def test_noninteractive_invocation_does_not_prompt_or_create_user(self, terminal):
        with self.assertRaises(CommandError):
            self.invoke()
        self.assertEqual(User.objects.count(), 0)
