"""Actualiza solo la configuración Go heredada exacta; no reemplaza personalizaciones."""
from copy import deepcopy
import json

from django.core.management.base import BaseCommand
from django.db import transaction
from judge.languages import languages
from options.models import SysOptions


def updated_languages(value):
    result = deepcopy(value)
    current = next(item for item in languages if item["name"] == "Golang")["config"]
    legacy = deepcopy(current)
    legacy["compile"].update(max_cpu_time=3000, max_real_time=5000,
                             compile_command="/usr/bin/go build -o {exe_path} {src_path}")
    changed = 0
    for item in result:
        if item.get("name") == "Golang" and item.get("config") == legacy:
            item["config"] = deepcopy(current)
            changed += 1
    return result, changed


class Command(BaseCommand):
    help = "Propone el presupuesto Go probado con caché fría; escribe únicamente con --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        record = SysOptions.objects.select_for_update().filter(key="languages").first()
        value, changed = updated_languages(record.value) if record else ([], 0)
        if changed and options["apply"]:
            record.value = value
            record.save(update_fields=["value"])
        self.stdout.write(json.dumps({"matching_legacy_entries": changed, "applied": bool(changed and options["apply"]),
                                      "custom_entries_preserved": True}))
