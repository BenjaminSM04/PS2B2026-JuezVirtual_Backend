from django.db import transaction

from ai_tutor.models import TutorAttempt, TutorProblemConfigVersion, TutorSession
from ai_tutor.services.access import authorize
from submission.models import JudgeStatus, Submission
from utils.api import APIError

FINAL_RESULTS = {JudgeStatus.COMPILE_ERROR, JudgeStatus.WRONG_ANSWER, JudgeStatus.ACCEPTED,
                 JudgeStatus.CPU_TIME_LIMIT_EXCEEDED, JudgeStatus.REAL_TIME_LIMIT_EXCEEDED,
                 JudgeStatus.MEMORY_LIMIT_EXCEEDED, JudgeStatus.RUNTIME_ERROR, JudgeStatus.SYSTEM_ERROR,
                 JudgeStatus.PARTIALLY_ACCEPTED}


def _owned_session(user, session_id):
    try:
        return TutorSession.objects.get(pk=session_id, user=user, state="active")
    except TutorSession.DoesNotExist:
        raise APIError("La sesión no está disponible.", err="tutor-session-unavailable")


def _snapshot(session, submission):
    attempt, _ = TutorAttempt.objects.get_or_create(
        session=session, submission=submission,
        defaults={"language": submission.language, "result": submission.result, "help_level": session.highest_help_level})
    return attempt


def read_session(user, problem_id):
    problem = authorize(user, problem_id)
    return TutorSession.objects.filter(user=user, problem=problem, state="active").prefetch_related("attempts").first()


@transaction.atomic
def create_or_recover(user, problem_id):
    # Todas las escrituras toman primero el problema y después la sesión.
    problem = authorize(user, problem_id, lock=True)
    session = TutorSession.objects.filter(user=user, problem=problem, state="active").first()
    if session is None:
        version = TutorProblemConfigVersion.objects.filter(problem=problem, status="active").first()
        if version is None:
            raise APIError("El problema requiere una configuración pedagógica activa.", err="tutor-config-required")
        session = TutorSession.objects.create(user=user, problem=problem, config_version=version)
    session = TutorSession.objects.select_for_update().get(pk=session.pk)
    submissions = Submission.objects.select_for_update().filter(
        user_id=user.id, problem=problem, contest__isnull=True, create_time__gte=session.created_at,
        result__in=FINAL_RESULTS).order_by("create_time", "id")
    for submission in submissions:
        _snapshot(session, submission)
    return session


@transaction.atomic
def register_attempt(user, session_id, submission_id):
    session = _owned_session(user, session_id)
    authorize(user, session.problem_id, lock=True)
    session = TutorSession.objects.select_for_update().get(pk=session.id, user=user, state="active")
    try:
        submission = Submission.objects.select_for_update().get(pk=submission_id, user_id=user.id, problem_id=session.problem_id,
                                                                contest__isnull=True, create_time__gte=session.created_at)
    except Submission.DoesNotExist:
        raise APIError("La entrega debe ser propia, del mismo problema y posterior al inicio.", err="tutor-submission-invalid")
    if submission.result not in FINAL_RESULTS:
        raise APIError("La entrega todavía no tiene un veredicto final.", err="tutor-submission-pending")
    return _snapshot(session, submission)


@transaction.atomic
def advance_help_level(session_id, level):
    """Reservado a servicios internos; ningún endpoint acepta un nivel del cliente."""
    if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= 3:
        raise ValueError("El nivel debe ser un entero entre cero y tres.")
    session = TutorSession.objects.select_for_update().get(pk=session_id, state="active")
    if session.config_version_id and level > session.config_version.hint_policy["max_help_level"]:
        raise ValueError("El nivel supera la política de la versión de esta sesión.")
    if level > session.highest_help_level:
        session.highest_help_level = level
        session.save(update_fields=["highest_help_level", "updated_at"])
    return session
