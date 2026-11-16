import os

from django.core.management.base import BaseCommand, CommandError

from options.options import SysOptions


class Command(BaseCommand):
    help = "Configura el token del juez desde el entorno después de migrar."

    def handle(self, *args, **options):
        token = os.environ.get("JUDGE_SERVER_TOKEN", "")
        if len(token) < 32 or token == "CHANGE_THIS":
            raise CommandError("JUDGE_SERVER_TOKEN debe contener al menos 32 caracteres.")
        SysOptions.judge_server_token = token
        self.stdout.write("Configuración del juez actualizada.")
