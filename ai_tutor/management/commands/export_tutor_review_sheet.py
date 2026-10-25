import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ai_tutor.dataset.review import HUMAN_COLUMNS, SHEET_COLUMNS, is_closed, sheet_content
from ai_tutor.dataset.schema import TutorExampleSerializer


class Command(BaseCommand):
    help = ("Exporta a CSV (UTF-8 con BOM, para Excel) los ejemplos con decisión pendiente. "
            "Las columnas decision, reviewer y notes quedan vacías para la persona que revisa; no se aprueba nada.")

    def add_arguments(self, parser):
        parser.add_argument("source", type=Path)
        parser.add_argument("sheet", type=Path)
        parser.add_argument("--delimiter", choices=[",", ";"], default=",",
                            help="Separador de columnas; use ';' si su Excel está en español y abre todo en una columna.")

    def handle(self, *args, **options):
        try:
            records = json.loads(options["source"].read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CommandError(f"No se pudo leer el origen: {exc}")
        if not isinstance(records, list) or not records:
            raise CommandError("Se requiere una lista no vacía de ejemplos.")
        failures, identifiers = [], set()
        for index, record in enumerate(records, start=1):
            serializer = TutorExampleSerializer(data=record)
            if not serializer.is_valid():
                failures.append(f"Registro {index}: {serializer.errors}")
                continue
            if record["example_id"] in identifiers:
                failures.append(f"Registro {index}: example_id duplicado.")
            identifiers.add(record["example_id"])
        if failures:
            raise CommandError("El origen no es válido (use validate_tutor_examples):\n" + "\n".join(failures))
        pending = [item for item in records if not is_closed(item)]
        if not pending:
            raise CommandError("No hay ejemplos con decisión pendiente; las decisiones cerradas se conservan.")
        try:
            with options["sheet"].open("x", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=SHEET_COLUMNS, delimiter=options["delimiter"])
                writer.writeheader()
                for item in pending:
                    writer.writerow({**sheet_content(item), **{column: "" for column in HUMAN_COLUMNS}})
        except FileExistsError:
            raise CommandError("La planilla ya existe; no se sobrescribe. Elija otro nombre.")
        self.stdout.write(f"{len(pending)} ejemplos exportados ({len(records) - len(pending)} cerrados omitidos). "
                          "Complete decision (approved/rejected/review), reviewer y notes; el contenido es solo lectura.")
