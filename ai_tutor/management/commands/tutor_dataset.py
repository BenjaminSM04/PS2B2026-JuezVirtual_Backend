import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from ai_tutor.dataset.pipeline import build_dataset, train, evaluate


class Command(BaseCommand):
    help = "Versiona, entrena y evalúa exclusivamente ejemplos con aprobación humana válida."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["build", "train", "evaluate"])
        parser.add_argument("source", type=Path)
        parser.add_argument("output", type=Path)
        parser.add_argument("--model", type=Path)
        parser.add_argument("--seed", type=int, default=2026)

    def handle(self, *args, **options):
        try:
            action = options["action"]
            if action == "build":
                result = build_dataset(json.loads(options["source"].read_text(encoding="utf-8")), options["output"], options["seed"])
            elif action == "train":
                result = train(options["source"], options["output"])
            else:
                if not options["model"]:
                    raise ValueError("Se requiere --model para evaluar.")
                result = evaluate(options["source"], options["model"])
                with options["output"].open("x", encoding="utf-8") as stream:
                    json.dump(result, stream, indent=2, ensure_ascii=True)
            self.stdout.write("Operación completada con validación de procedencia y particiones.")
        except (OSError, ValueError) as error:
            raise CommandError(str(error)) from error
