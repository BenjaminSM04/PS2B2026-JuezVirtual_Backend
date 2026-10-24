import json
from io import StringIO
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ai_tutor.models import TutorMetric


class MetricReportTests(TestCase):
    def test_report_counts_period_and_percentiles_without_identity(self):
        for latency in (10, 20, 30):
            TutorMetric.objects.create(category="unknown", level=0, source="deterministic", latency_ms=latency,
                                       model_version="fallback-1", outcome="completed")
        old = TutorMetric.objects.create(category="unknown", level=0, source="unavailable", latency_ms=99,
                                        model_version="", outcome="denied")
        TutorMetric.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=91))
        output = StringIO()
        call_command("report_tutor_metrics", days=30, stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(len(report["groups"]), 1)
        self.assertEqual(report["groups"][0]["count"], 3)
        self.assertEqual(report["groups"][0]["p50_ms"], 20)
        self.assertAlmostEqual(report["groups"][0]["p95_ms"], 29)
        self.assertFalse({"user", "code", "prompt", "ip", "email"} & set(report["groups"][0]))
