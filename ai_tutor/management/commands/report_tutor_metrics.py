import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Aggregate, Avg, Count, Q
from django.utils import timezone

from ai_tutor.models import TutorMetric


class Median(Aggregate):
    function = "PERCENTILE_CONT"
    template = "%(function)s(0.5) WITHIN GROUP (ORDER BY %(expressions)s)"


class P95(Median):
    template = "%(function)s(0.95) WITHIN GROUP (ORDER BY %(expressions)s)"


class Command(BaseCommand):
    help = "Exporta agregados del periodo sin usuarios, código, prompts, correos ni IP."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        days = options["days"]
        if not 1 <= days <= 365:
            raise CommandError("Use un periodo entre 1 y 365 días.")
        end = timezone.now()
        start = end - timedelta(days=days)
        groups = TutorMetric.objects.filter(created_at__gte=start, created_at__lte=end).values(
            "category", "level", "source", "outcome", "model_version", "config_version_id"
        ).annotate(count=Count("pk"), mean_ms=Avg("latency_ms"), p50_ms=Median("latency_ms"), p95_ms=P95("latency_ms"),
                   useful=Count("pk", filter=Q(feedback__rating__value="useful")),
                   incorrect=Count("pk", filter=Q(feedback__rating__value="incorrect"))).order_by("category", "level", "source")
        self.stdout.write(json.dumps({"from": start.isoformat(), "to": end.isoformat(), "groups": list(groups)}, ensure_ascii=True))
