import copy
import json
from pathlib import Path

from django.utils import timezone

from ai_tutor.models import TutorProblemConfigVersion


def initial_configs():
    path = Path(__file__).parents[2] / "docs/ai-tutor/configuracion-inicial.json"
    return json.loads(path.read_text(encoding="utf-8"))


def config_content(index=0):
    return copy.deepcopy(initial_configs()["versions"][index])


def create_active_config(problem, author, **changes):
    content = config_content()
    content.update(changes)
    version = TutorProblemConfigVersion.objects.create(problem=problem, version=1, created_by=author, **content)
    TutorProblemConfigVersion.objects.filter(pk=version.pk).update(status="active", activated_at=timezone.now())
    version.refresh_from_db()
    return version
