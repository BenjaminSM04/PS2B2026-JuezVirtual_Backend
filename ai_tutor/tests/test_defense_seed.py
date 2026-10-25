import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from account.models import User
from ai_tutor.models import TutorProblemConfigVersion
from problem.models import Problem


class DefenseSeedTests(TestCase):
    credentials = {"teacher_password": "SoloFixtureDocente2026!", "student_password": "SoloFixtureAlumno2026!"}

    def seed(self):
        with patch("sys.stdin", io.StringIO(json.dumps(self.credentials))):
            call_command("seed_defense_demo", stdout=io.StringIO())

    def test_requires_verification_environment_and_preserves_foreign_users(self):
        with patch.dict(os.environ, {"OJ_VERIFICATION_ONLY": "0"}), self.assertRaises(CommandError):
            self.seed()
        User.objects.create(username="usuario-ajeno")
        with patch.dict(os.environ, {"OJ_VERIFICATION_ONLY": "1"}), self.assertRaises(CommandError):
            self.seed()
        self.assertEqual(list(User.objects.values_list("username", flat=True)), ["usuario-ajeno"])

    def test_seed_is_repeatable_and_does_not_reset_modified_passwords(self):
        with TemporaryDirectory() as directory, self.settings(DATA_DIR=directory), patch.dict(os.environ, {"OJ_VERIFICATION_ONLY": "1"}):
            self.seed()
            self.seed()
            self.assertEqual(User.objects.count(), 2)
            self.assertEqual(Problem.objects.count(), 6)
            self.assertEqual(TutorProblemConfigVersion.objects.count(), 6)
            problem = Problem.objects.get(_id="DEF-SUMA")
            self.assertTrue((Path(directory) / "test_case" / problem.test_case_id / "info").is_file())
            user = User.objects.get(username="estudiante-demo")
            user.set_password("ContraseñaModificadaPorUsuario2026!")
            user.save()
            with self.assertRaises(CommandError):
                self.seed()
            user.refresh_from_db()
            self.assertTrue(user.check_password("ContraseñaModificadaPorUsuario2026!"))
