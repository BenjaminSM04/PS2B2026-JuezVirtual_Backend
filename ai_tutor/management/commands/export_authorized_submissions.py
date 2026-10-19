"""Exportación segura y de solo lectura de entregas históricas autorizadas (PB-05).

Autorización:
- `--authorization-file`: JSON documentado con `authorization` y `problems`;
  es la única vía que permite una exportación real (verificación de
  estructura, no de validez institucional, que es humana).
- `--authorization`: identificador suelto; solo habilita `--dry-run`.

El comando nunca escribe en la base de datos, no ejecuta consultas sin
autorización y aborta sin archivos parciales si el detector de información
prohibida encuentra hallazgos.
"""

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from problem.models import Problem
from submission.models import Submission
from utils.audit import audit_log

from ai_tutor.dataset import anonymize
from ai_tutor.dataset.schema import TutorExampleSerializer

AUTH_FILE_KEYS = ("authorization", "problems")
PROBLEM_TYPE_TEXT = {"nonexistent": "inexistente", "no-visible": "no-visible", "contest": "de-concurso"}


def parse_problem_ids(flag_value, file_value):
    """Convierte --problems o --problems-file en una lista no vacía y sin repetidos."""
    if flag_value and file_value:
        raise CommandError("--problems y --problems-file son excluyentes.")
    if flag_value:
        tokens = flag_value.split(",")
    elif file_value:
        path = Path(file_value)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CommandError(f"No se pudo leer el archivo de problemas ({exc.__class__.__name__}).")
        tokens = text.splitlines()
    else:
        raise CommandError("Se requiere un conjunto explícito de problemas: --problems o --problems-file.")
    identifiers = []
    for token in tokens:
        token = token.strip()
        if not token or token.startswith("#"):
            continue
        try:
            value = int(token)
        except ValueError:
            raise CommandError(f"Identificador de problema inválido: '{token}'.")
        if value <= 0:
            raise CommandError(f"Identificador de problema fuera de rango: '{token}'.")
        identifiers.append(value)
    if not identifiers:
        raise CommandError("El conjunto explícito de problemas está vacío.")
    return sorted(set(identifiers))


def load_authorization(string_value, file_value):
    """Devuelve (id, problemas del archivo o None, verificada). Aborta si nada es válido."""
    string_value = (string_value or "").strip()
    if string_value and file_value:
        raise CommandError("--authorization y --authorization-file son excluyentes.")
    if not string_value and not file_value:
        raise CommandError("Se requiere autorización: --authorization o --authorization-file.")
    if string_value:
        # Un identificador suelto no acredita una autorización institucional.
        return string_value, None, False
    path = Path(file_value)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommandError(f"El archivo de autorización no existe o no es JSON válido ({exc.__class__.__name__}).")
    if not isinstance(data, dict) or any(key not in data for key in AUTH_FILE_KEYS):
        keys_text = ", ".join(AUTH_FILE_KEYS)
        raise CommandError(f"El archivo de autorización requiere las claves {keys_text}.")
    identifier = data["authorization"]
    if not isinstance(identifier, str) or not identifier.strip():
        raise CommandError("El archivo de autorización tiene un identificador vacío o inválido.")
    problems = data["problems"]
    if not isinstance(problems, list) or not problems:
        raise CommandError("El archivo de autorización no cubre ningún problema.")
    converted = []
    for item in problems:
        try:
            value = int(item)
        except (TypeError, ValueError):
            raise CommandError("El archivo de autorización contiene un identificador de problema inválido.")
        if value <= 0:
            raise CommandError("El archivo de autorización contiene un identificador de problema no positivo.")
        converted.append(value)
    return identifier.strip(), sorted(set(converted)), True


def write_constancia(path, generated_at, actor, reason, requested_ids):
    """Añade una constancia de no uso; solo fecha, actor, motivo y problemas."""
    path = Path(path)
    actor_text = actor or "no indicado"
    problems_text = ", ".join(map(str, requested_ids)) if requested_ids else "no especificados"
    lines = [
        "=== constancia de no uso ===",
        f"fecha: {generated_at}",
        f"actor: {actor_text}",
        f"motivo: {reason}",
        f"problemas solicitados: {problems_text}",
        "datos exportados: ninguno",
        "",
    ]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    except OSError as exc:
        raise CommandError(f"No se pudo escribir la constancia de no uso ({exc.__class__.__name__}).")


def atomic_write_json(path, payload):
    """Escritura segura: archivo temporal + reemplazo atómico; nunca deja parciales."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


class Command(BaseCommand):
    help = "Exporta entregas históricas autorizadas, anonimizadas y validadas contra el contrato PB-04. Solo lectura."

    def add_arguments(self, parser):
        parser.add_argument("--authorization", help="Identificador de autorización no documentado (solo --dry-run).")
        parser.add_argument("--authorization-file", help="JSON documentado con authorization y problems.")
        parser.add_argument("--problems", help="Lista explícita separada por comas, p. ej. 1,2,3.")
        parser.add_argument("--problems-file", help="Archivo con un identificador de problema por línea.")
        parser.add_argument("--output", default="docs/ai-tutor/export.json", help="Archivo de destino.")
        parser.add_argument("--constancia", default="docs/ai-tutor/constancia-no-uso.txt",
                            help="Archivo de constancia de no uso.")
        parser.add_argument("--dry-run", action="store_true", help="Valida y resume sin escribir la exportación.")
        parser.add_argument("--actor", help="Responsable que ejecuta la exportación.")
        parser.add_argument("--notes", default="", help="Nota libre para el manifiesto (máximo 300 caracteres).")

    def handle(self, *args, **options):
        try:
            self._export(options)
        except CommandError as exc:
            write_constancia(options["constancia"], anonymize.generated_now(), options.get("actor") or "",
                             str(exc), self._last_requested_ids([]))
            audit_log(None, "tutor_export_blocked", "Dataset",
                      extra={"actor": options.get("actor") or None, "reason": str(exc)[:300]})
            raise

    def _last_requested_ids(self, default):
        return getattr(self, "_requested_ids", default)

    def _export(self, options):
        dry_run = options["dry_run"]
        actor = (options.get("actor") or "").strip()
        requested_ids = self._requested_ids = parse_problem_ids(options.get("problems"), options.get("problems_file"))
        authorization, file_problems, verified = load_authorization(options.get("authorization"),
                                                                    options.get("authorization_file"))
        if verified and set(requested_ids) - set(file_problems):
            raise CommandError("El archivo de autorización no cubre todos los problemas solicitados: "
                               f"{sorted(set(requested_ids) - set(file_problems))}.")
        if not verified and not dry_run:
            raise CommandError("La autorización por identificador no es verificable: para exportar de verdad se "
                               "requiere --authorization-file con la documentación institucional estructurada.")

        generated_at = anonymize.generated_now()
        records, counts = self._collect(requested_ids, authorization, generated_at, actor)
        findings = self._validate_records(records)
        if findings:
            raise CommandError("Detección de información prohibida; exportación abortada por completo. "
                               "Hallazgos: " + "; ".join(findings))

        manifest = {
            "schema_version": anonymize.SCHEMA_VERSION,
            "generated_at": generated_at,
            "authorization": authorization,
            "authorization_verification": "archivo-documentado" if verified else "identificador-no-verificado",
            "problems": self._valid_ids,
            "actor": actor or None,
            "counts": counts,
            "notes": (options.get("notes") or "")[:300],
        }
        audit_log(None, "tutor_export_dry_run" if dry_run else "tutor_export_completed", "Dataset",
                  extra={"actor": actor or None, "authorization": authorization, "problems": self._valid_ids,
                         "exported": len(records)})
        if dry_run:
            self.stdout.write(json.dumps({"resumen": counts, "escritura": "ninguna (dry-run)"},
                                         ensure_ascii=False, indent=2))
            self.stdout.write(self.style.SUCCESS("Dry-run correcto: no se escribió archivo alguno."))
            return
        output = Path(options["output"])
        try:
            atomic_write_json(output, {"manifest": manifest, "records": records})
        except OSError as exc:
            raise CommandError(f"No se pudo escribir la exportación ({exc.__class__.__name__}).")
        self.stdout.write(self.style.SUCCESS(f"Exportación completada en {output} con {len(records)} "
                                             "registro(s); pendiente de revisión humana (PB-07)."))

    def _collect(self, requested_ids, authorization, generated_at, actor):
        existing = {problem.id: problem for problem in Problem.objects.filter(id__in=requested_ids)}
        rejected_problem = {key: [] for key in PROBLEM_TYPE_TEXT}
        valid_ids = []
        for problem_id in requested_ids:
            problem = existing.get(problem_id)
            if problem is None:
                rejected_problem["nonexistent"].append(problem_id)
            elif problem.contest_id is not None:
                rejected_problem["contest"].append(problem_id)
            elif not problem.visible:
                rejected_problem["no-visible"].append(problem_id)
            else:
                valid_ids.append(problem_id)
        self._valid_ids = valid_ids
        rows = list(Submission.objects.filter(problem_id__in=valid_ids, contest__isnull=True)
                    .order_by("problem_id", "create_time", "id")
                    .only("id", "problem_id", "code", "language", "result", "statistic_info", "username", "ip"))
        identities = set()
        for row in rows:
            username = (row.username or "").strip().casefold()
            if len(username) >= 3:
                identities.add(username)
            if row.ip:
                identities.add(row.ip.strip().casefold())
        identities.discard((actor or "").strip().casefold())
        self._identities = identities
        rejected_verdict, rejected_language = {}, {}
        records, exported_language, empty_code = [], {}, 0
        for row in rows:
            if row.result not in anonymize.EXPORTABLE_RESULTS:
                rejected_verdict[str(row.result)] = rejected_verdict.get(str(row.result), 0) + 1
            elif row.language not in anonymize.SUPPORTED_LANGUAGES:
                rejected_language[row.language] = rejected_language.get(row.language, 0) + 1
            elif not (row.code or "").strip():
                empty_code += 1
            else:
                record = anonymize.build_record(row, existing[row.problem_id], authorization, generated_at, actor)
                records.append(record)
                exported_language[record["language"]] = exported_language.get(record["language"], 0) + 1
        counts = {
            "total_evaluado": len(rows),
            "exportado": len(records),
            "exportado_por_lenguaje": exported_language,
            "rechazado_por_veredicto": rejected_verdict,
            "rechazado_por_lenguaje": rejected_language,
            "rechazado_por_codigo_vacio": empty_code,
            "rechazado_por_problema": {PROBLEM_TYPE_TEXT[kind]: ids for kind, ids in rejected_problem.items()},
        }
        return records, counts

    def _validate_records(self, records):
        findings, failures = [], []
        identities = self._identities
        for index, record in enumerate(records, start=1):
            validator = TutorExampleSerializer(data=record)
            if not validator.is_valid():
                failures.append(f"Registro {index}: {validator.errors}")
                continue
            hits = anonymize.scan_record(record, identities)
            findings.extend(f"Registro {index}: {finding}" for finding in hits)
        if failures:
            raise CommandError("Registros que no cumplen el contrato PB-04 (exportación abortada): "
                               + " | ".join(failures))
        return findings
