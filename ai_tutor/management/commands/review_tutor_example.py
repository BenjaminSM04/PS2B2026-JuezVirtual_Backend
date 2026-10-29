import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from ai_tutor.dataset.review import is_closed, record_decision
from ai_tutor.dataset.schema import TutorExampleSerializer


class Command(BaseCommand):
    help = "Registra una decisión humana explícita; no realiza ni inventa la revisión pedagógica."

    def add_arguments(self, parser):
        parser.add_argument("source", type=Path)
        parser.add_argument("output", type=Path)
        parser.add_argument("--example-id", required=True)
        parser.add_argument("--reviewer", required=True)
        parser.add_argument("--decision", choices=["review", "approved", "rejected"], required=True)
        parser.add_argument("--notes", required=True)

    def handle(self, *args, **options):
        records = json.loads(options["source"].read_text(encoding="utf-8"))
        selected = [item for item in records if item["example_id"] == options["example_id"]]
        if len(selected) != 1:
            raise CommandError("El ejemplo debe existir exactamente una vez.")
        item = selected[0]
        if is_closed(item):
            raise CommandError("Una decisión cerrada se conserva; cree una nueva revisión versionada.")
        record_decision(item, options["reviewer"], options["decision"], options["notes"])
        serializer = TutorExampleSerializer(data=item)
        if not serializer.is_valid():
            raise CommandError("La revisión no cumple el contrato: " + str(serializer.errors))
        with options["output"].open("x", encoding="utf-8") as stream:
            json.dump(records, stream, indent=2, ensure_ascii=True)
        self.stdout.write("Decisión guardada en una versión nueva; el origen se conserva.")
