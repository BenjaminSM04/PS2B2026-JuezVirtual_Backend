import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ai_tutor.dataset.schema import TutorExampleSerializer


class Command(BaseCommand):
    help = "Valida ejemplos pedagógicos sin aprobarlos ni modificar la base de datos."

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path)

    def handle(self, *args, **options):
        try:
            records = json.loads(options["path"].read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CommandError(f"No se pudo leer el archivo: {exc}")
        if not isinstance(records, list) or not records:
            raise CommandError("Se requiere una lista no vacía de ejemplos.")
        failures, identifiers = [], set()
        for index, record in enumerate(records, start=1):
            serializer = TutorExampleSerializer(data=record)
            if not serializer.is_valid():
                failures.append(f"Registro {index}: {serializer.errors}")
                continue
            identifier = serializer.validated_data["example_id"]
            if identifier in identifiers:
                failures.append(f"Registro {index}: example_id duplicado.")
            identifiers.add(identifier)
        if failures:
            raise CommandError("\n".join(failures))
        self.stdout.write(self.style.SUCCESS(f"{len(records)} ejemplos válidos. La revisión pedagógica humana sigue siendo obligatoria."))
