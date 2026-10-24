from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
from django.utils import timezone
from ai_tutor.models import TutorMetric


class Command(BaseCommand):
    help = "Agrega métricas sin código ni PII; purga vencidas únicamente con --apply."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        from django.core.management.base import CommandError
        import json
        if options["days"] < 1:
            raise CommandError("El periodo debe ser positivo.")
        old = TutorMetric.objects.filter(created_at__lt=timezone.now() - timedelta(days=options["days"]))
        self.stdout.write(json.dumps({"expired": old.count(), "groups": list(TutorMetric.objects.values("category", "level", "source", "outcome").annotate(count=Count("pk"), latency_ms=Avg("latency_ms")))}, ensure_ascii=True))
        if options["apply"]:
            old.delete()
