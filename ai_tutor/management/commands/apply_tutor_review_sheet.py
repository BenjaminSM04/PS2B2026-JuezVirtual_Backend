import csv
import io
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_tutor.dataset.review import (CONTENT_COLUMNS, DECISIONS, SHEET_COLUMNS, is_closed, normalize_cell,
                                     record_decision, sheet_content)
from ai_tutor.dataset.schema import TutorExampleSerializer


class Command(BaseCommand):
    help = ("Aplica a una versión nueva del JSON las decisiones humanas de una planilla CSV; todo o nada. "
            "Solo registra decisión y notas: no revisa ni modifica contenido pedagógico.")

    def add_arguments(self, parser):
        parser.add_argument("source", type=Path)
        parser.add_argument("sheet", type=Path)
        parser.add_argument("output", type=Path)
        parser.add_argument("--reviewer", required=True, help="Usuario del revisor; debe coincidir con la columna reviewer.")

    def handle(self, *args, **options):
        reviewer = options["reviewer"].strip()
        if not reviewer:
            raise CommandError("--reviewer no puede estar vacío.")
        try:
            records = json.loads(options["source"].read_text(encoding="utf-8"))
            text = options["sheet"].read_text(encoding="utf-8-sig")
        except (OSError, ValueError) as exc:
            raise CommandError(f"No se pudo leer el origen o la planilla: {exc}")
        if not isinstance(records, list):
            raise CommandError("El origen debe ser una lista de ejemplos.")
        # Excel en español guarda con ';'; el encabezado no contiene ninguno de los dos separadores.
        header = text.split("\n", 1)[0]
        delimiter = ";" if header.count(";") > header.count(",") else ","
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
        missing = [column for column in SHEET_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise CommandError("A la planilla le faltan columnas: " + ", ".join(missing))

        now = timezone.now().isoformat()
        errors, seen, applied = [], set(), Counter()
        for number, row in enumerate(reader, start=2):
            if not any(normalize_cell(value) for value in row.values() if isinstance(value, str)):
                continue
            identifier = normalize_cell(row["example_id"])
            if identifier and identifier in seen:
                errors.append(f"Fila {number}: example_id {identifier!r} duplicado en la planilla.")
                continue
            seen.add(identifier)
            decision = normalize_cell(row["decision"]).lower()
            if not decision:
                continue
            problem = self.apply_row(records, row, identifier, decision, reviewer, now)
            if problem:
                errors.append(f"Fila {number} ({identifier or 'sin example_id'}): {problem}")
            else:
                applied[decision] += 1
        if errors:
            raise CommandError("Planilla rechazada completa; no se escribió ninguna salida.\n" + "\n".join(errors))
        if not applied:
            raise CommandError("La planilla no contiene decisiones; no hay nada que aplicar.")
        # Se serializa antes de abrir el archivo para no dejar una salida parcial.
        content = json.dumps(records, indent=2, ensure_ascii=True)
        try:
            with options["output"].open("x", encoding="utf-8") as stream:
                stream.write(content)
        except FileExistsError:
            raise CommandError("La salida ya existe; no se sobrescribe. Elija otro nombre.")
        self.stdout.write("Decisiones guardadas en una versión nueva; el origen se conserva. "
                          f"approved={applied['approved']} rejected={applied['rejected']} review={applied['review']}")

    def apply_row(self, records, row, identifier, decision, reviewer, now):
        """Aplica una fila con decisión; devuelve el motivo del rechazo o None."""
        selected = [item for item in records if isinstance(item, dict) and item.get("example_id") == identifier]
        if len(selected) != 1:
            return "el ejemplo debe existir exactamente una vez en el origen."
        item = selected[0]
        if is_closed(item):
            return "decisión cerrada; se conserva, cree una nueva revisión versionada."
        if decision not in DECISIONS:
            return f"decision {decision!r} no válida (use {', '.join(DECISIONS)})."
        row_reviewer = normalize_cell(row["reviewer"])
        if row_reviewer != reviewer:
            return f"la columna reviewer ({row_reviewer!r}) no coincide con --reviewer ({reviewer!r}); una planilla = un revisor."
        if row_reviewer.casefold() == item["review"]["author"].casefold():
            return "el revisor debe ser distinto del autor."
        notes = normalize_cell(row["notes"])
        if not notes:
            return "las notas son obligatorias cuando hay decisión."
        expected = sheet_content(item)
        changed = [column for column in CONTENT_COLUMNS
                   if normalize_cell(row[column]) != normalize_cell(expected[column])]
        if changed:
            return ("el contenido difiere del origen (" + ", ".join(changed) + "). La planilla solo aplica decisión "
                    "y notas; las correcciones se hacen en el JSON de origen y se vuelve a exportar la planilla.")
        record_decision(item, reviewer, decision, notes, now)
        serializer = TutorExampleSerializer(data=item)
        if not serializer.is_valid():
            return "la revisión no cumple el contrato: " + str(serializer.errors)
        return None
