from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from account.decorators import ensure_created_by
from ai_tutor.models import TutorProblemConfigVersion
from ai_tutor.serializers import ConfigContentSerializer
from ai_tutor.services.access import get_problem
from utils.api import APIError
from utils.audit import audit_log


def validate_content(content):
    serializer = ConfigContentSerializer(data=content)
    if not serializer.is_valid():
        raise APIError(dict(serializer.errors), err="tutor-config-invalid")
    return serializer.validated_data


def get_version(problem, version_id):
    try:
        return TutorProblemConfigVersion.objects.get(pk=version_id, problem=problem)
    except TutorProblemConfigVersion.DoesNotExist:
        raise APIError("La versión no está disponible para este problema.", err="tutor-config-not-found")


@transaction.atomic
def create_draft(user, problem_id, **content):
    problem = get_problem(problem_id, lock=True)
    ensure_created_by(problem, user)
    content = validate_content(content)
    latest = TutorProblemConfigVersion.objects.filter(problem=problem).aggregate(latest=Max("version"))["latest"] or 0
    version = TutorProblemConfigVersion.objects.create(problem=problem, version=latest + 1, created_by=user, **content)
    transaction.on_commit(lambda: audit_log(user, "tutor_config_version_created", "Problem", problem.id, {"version_id": version.id}))
    return version


@transaction.atomic
def activate_version(user, problem_id, version_id):
    # Mismo orden de bloqueo que las sesiones: primero el problema.
    problem = get_problem(problem_id, lock=True)
    ensure_created_by(problem, user)
    version = get_version(problem, version_id)
    if version.status == "active":
        return version
    if version.status != "draft":
        raise APIError("Una versión retirada no puede reactivarse. Cree otro borrador.", err="tutor-config-retired")
    validate_content({key: getattr(version, key) for key in ("schema_version", "concepts", "hint_policy", "concept_explanations")})
    previous = TutorProblemConfigVersion.objects.filter(problem=problem, status="active").first()
    if previous:
        TutorProblemConfigVersion.objects.filter(pk=previous.pk).update(status="retired")
    TutorProblemConfigVersion.objects.filter(pk=version.pk).update(status="active", activated_at=timezone.now())
    version.refresh_from_db()
    transaction.on_commit(lambda: audit_log(user, "tutor_config_version_activated", "Problem", problem.id,
                                            {"version_before": previous.id if previous else None, "version_after": version.id}))
    return version
