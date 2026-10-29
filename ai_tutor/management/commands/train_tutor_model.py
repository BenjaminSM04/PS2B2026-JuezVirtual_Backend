from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from ai_tutor.ml.training import train_model


class Command(BaseCommand):
    help = "Entrena un adaptador únicamente con datos aprobados y un modelo seleccionado mediante evidencia."

    def add_arguments(self, parser):
        parser.add_argument("dataset", type=Path)
        parser.add_argument("selection", type=Path)
        parser.add_argument("output", type=Path)
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--no-quantization", action="store_true")
        parser.add_argument("--technical-demo", action="store_true", help="Solo sintéticos; produce artefactos experimentales sin aprobación humana.")

    def handle(self, *args, **options):
        try:
            train_model(options["dataset"], options["selection"], options["output"], options["resume"], not options["no_quantization"], technical_demo=options["technical_demo"])
        except (OSError, ValueError, ImportError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write("Entrenamiento finalizado; la integración sigue requiriendo evaluación humana y adversarial.")
