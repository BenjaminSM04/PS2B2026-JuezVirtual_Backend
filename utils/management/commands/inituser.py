import getpass
import sys

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from account.models import AdminType, ProblemPermission, User, UserProfile


class Command(BaseCommand):
    help = "Crea un administrador o restablece una contraseña mediante una operación explícita."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", help="Compatibilidad con scripts; prefiera el ingreso interactivo.")
        parser.add_argument("--action", required=True, choices=["create_super_admin", "reset"])

    def handle(self, *args, **options):
        username = options["username"]
        existing = User.objects.filter(username__iexact=username).first()
        if options["action"] == "create_super_admin" and existing:
            raise CommandError("El usuario ya existe; no se modifica su contraseña ni sus permisos.")
        if options["action"] == "reset" and not existing:
            raise CommandError("El usuario no existe.")
        password = options["password"]
        if not password:
            if not sys.stdin.isatty():
                raise CommandError("Se requiere una terminal interactiva para ingresar la contraseña.")
            password = getpass.getpass("Contraseña: ")
            if password != getpass.getpass("Repita la contraseña: "):
                raise CommandError("Las contraseñas no coinciden.")
        user = existing or User(username=username, admin_type=AdminType.SUPER_ADMIN,
                                problem_permission=ProblemPermission.ALL)
        if len(password) < 12:
            raise CommandError("La contraseña administrativa debe tener al menos 12 caracteres.")
        try:
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error
        with transaction.atomic():
            user.set_password(password)
            user.save()
            if not existing:
                UserProfile.objects.create(user=user)
        self.stdout.write(self.style.SUCCESS("Usuario actualizado." if existing else "Administrador creado."))
