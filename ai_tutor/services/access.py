from django.db import transaction

from account.decorators import ensure_created_by
from ai_tutor.models import TutorProblemConfig
from problem.models import Problem
from utils.api import APIError
from utils.audit import audit_log


def get_problem(problem_id, *, lock=False, visible=False):
    queryset = Problem.objects.select_for_update() if lock else Problem.objects.all()
    if visible:
        queryset = queryset.filter(visible=True)
    try:
        problem = queryset.get(pk=problem_id)
    except Problem.DoesNotExist:
        raise APIError("El problema no está disponible.", err="tutor-unavailable")
    if problem.contest_id is not None:
        raise APIError("El entrenamiento no está disponible en concursos.", err="tutor-contest-blocked")
    return problem


def can_use_tutor(user, problem):
    return bool(user.is_authenticated and not user.is_disabled and problem.visible and
                problem.contest_id is None and TutorProblemConfig.objects.filter(problem=problem, enabled=True).exists())


def authorize(user, problem_id, *, lock=False):
    problem = get_problem(problem_id, lock=lock, visible=True)
    if not can_use_tutor(user, problem):
        raise APIError("El entrenamiento requiere una cuenta habilitada y una actividad activa.", err="tutor-forbidden")
    return problem


def config_data(problem):
    config = TutorProblemConfig.objects.filter(problem=problem).first()
    return {"problem_id": problem.id, "enabled": bool(config and config.enabled),
            "created_by": config.created_by_id if config else None, "updated_by": config.updated_by_id if config else None,
            "created_at": config.created_at.isoformat() if config else None,
            "updated_at": config.updated_at.isoformat() if config else None}


@transaction.atomic
def set_config(user, problem_id, enabled):
    # Bloquear el problema serializa la primera configuración y las sesiones.
    problem = get_problem(problem_id, lock=True)
    ensure_created_by(problem, user)
    config = TutorProblemConfig.objects.filter(problem=problem).first()
    previous = bool(config and config.enabled)
    if previous != enabled:
        if config is None:
            config = TutorProblemConfig(problem=problem, created_by=user)
        config.enabled = enabled
        config.updated_by = user
        config.save()
        transaction.on_commit(lambda: audit_log(user, "tutor_config_changed", "Problem", problem.id,
                                                {"enabled_before": previous, "enabled_after": enabled}))
    return config_data(problem)
