from django.core.management.base import BaseCommand
from django.db import transaction

from problem.models import Problem
from problem.utils import difficulty_levels_from_tags


class Command(BaseCommand):
    help = "Repara por etiquetas el lote BLZ2-046 a BLZ2-145 fuera de concursos; simula salvo con --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe los cambios en una única transacción.")

    def handle(self, *args, **options):
        apply = options["apply"]
        self.stdout.write("APLICACIÓN" if apply else "SIMULACIÓN: no se escribirán cambios. Use --apply para aplicarlos.")
        messages = []
        changed = 0
        with transaction.atomic():
            for number in range(46, 146):
                display_id = f"BLZ2-{number:03d}"
                queryset = Problem.objects.filter(_id=display_id, contest__isnull=True)
                if apply:
                    queryset = queryset.select_for_update()
                problems = list(queryset.prefetch_related("tags"))
                if len(problems) != 1:
                    reason = "ausente fuera de concursos" if not problems else "duplicados fuera de concursos"
                    messages.append(f"{display_id}: omitido ({reason}).")
                    continue
                problem = problems[0]
                levels = difficulty_levels_from_tags(tag.name for tag in problem.tags.all())
                if len(levels) != 1:
                    reason = "sin etiqueta reconocida" if not levels else "etiquetas contradictorias"
                    messages.append(f"{display_id}: omitido ({reason}).")
                    continue
                difficulty = levels.pop()
                if problem.difficulty == difficulty:
                    messages.append(f"{display_id}: sin cambios ({difficulty}).")
                    continue
                messages.append(f"{display_id}: {problem.difficulty} -> {difficulty}.")
                if apply:
                    Problem.objects.filter(pk=problem.pk).update(difficulty=difficulty)
                changed += 1
        for message in messages:
            self.stdout.write(message)
        action = "aplicados" if apply else "propuestos"
        self.stdout.write(f"Cambios {action}: {changed}.")
