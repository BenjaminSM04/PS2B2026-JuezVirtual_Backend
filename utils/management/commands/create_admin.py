from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from account.models import AdminType, ProblemPermission, User, UserProfile
from account.serializers import validate_password_strength


class Command(BaseCommand):
    help = "Crea un administrador solicitando la contraseña sin mostrarla."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", default="")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"].lower()
        if User.objects.filter(username=username).exists():
            raise CommandError("El usuario ya existe; no se modificó su contraseña.")
        password = getpass("Contraseña: ")
        if password != getpass("Repetir contraseña: "):
            raise CommandError("Las contraseñas no coinciden.")
        user = User(username=username, email=options["email"], admin_type=AdminType.SUPER_ADMIN,
                    problem_permission=ProblemPermission.ALL)
        validate_password(password, user=user)
        validate_password_strength(password)
        user.set_password(password)
        user.save()
        UserProfile.objects.create(user=user)
        self.stdout.write(self.style.SUCCESS("Administrador creado."))
