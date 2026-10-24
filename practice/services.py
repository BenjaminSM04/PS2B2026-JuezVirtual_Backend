import logging
from django.db import transaction
from django.db.models import Count

from practice.models import Achievement, MascotPreference
from submission.models import Submission, JudgeStatus
from utils.api import APIError

logger = logging.getLogger(__name__)


def record_accepted(submission):
    if submission.result != JudgeStatus.ACCEPTED or submission.contest_id is not None or submission.problem.contest_id is not None:
        return
    Achievement.objects.get_or_create(user_id=submission.user_id, original_problem_id=submission.problem_id,
        defaults={"first_submission_id": submission.id, "earned_at": submission.create_time})


def on_submission_saved(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    # Un fallo del logro no revierte ni interrumpe el procesamiento del juez.
    try:
        with transaction.atomic():
            record_accepted(instance)
    except Exception:
        logger.error("No se registró un logro; ejecute reconcile_mascot para recuperarlo.")


def reconcile():
    accepted = Submission.objects.filter(result=JudgeStatus.ACCEPTED, contest__isnull=True,
        problem__contest__isnull=True).select_related("problem").only(
        "id", "user_id", "problem_id", "contest_id", "create_time", "result", "problem__contest_id"
    ).order_by("user_id", "problem_id", "create_time", "id").distinct("user_id", "problem_id")
    for submission in accepted.iterator(chunk_size=500):
        record_accepted(submission)


def mascot(user):
    count = Achievement.objects.filter(user=user).count()
    preference = MascotPreference.objects.filter(user=user).first()
    colors, accessories = ["green"], ["none"]
    for threshold, color, accessory in ((5, "blue", "scarf"), (15, "amber", "glasses"), (30, "violet", "backpack")):
        if count >= threshold:
            colors.append(color)
            accessories.append(accessory)
    stage, next_at = ("egg", 1) if count == 0 else (("baby", 10) if count < 10 else (("juvenile", 30) if count < 30 else ("adult", None)))
    return {"solved_count": count, "stage": stage, "next_stage_at": next_at,
        "unlocked_colors": colors, "unlocked_accessories": accessories,
        "appearance": {"color": preference.color if preference else "green", "accessory": preference.accessory if preference else "none"},
        "preferences": {"visible": preference.visible if preference else True,
                        "animations_enabled": preference.animations_enabled if preference else True}}


@transaction.atomic
def update_mascot(user, data):
    # Bloquear al usuario serializa también la creación inicial de preferencias.
    from account.models import User
    User.objects.select_for_update().get(pk=user.id)
    state = mascot(user)
    if data.get("color", "green") not in state["unlocked_colors"] or data.get("accessory", "none") not in state["unlocked_accessories"]:
        raise APIError("Ese aspecto todavía no está desbloqueado.", err="mascot-locked")
    preference, _ = MascotPreference.objects.get_or_create(user=user)
    for key, value in data.items():
        setattr(preference, key, value)
    preference.save()
    return mascot(user)


def overview(user):
    own = Submission.objects.filter(user_id=user.id, contest__isnull=True, problem__contest__isnull=True, problem__visible=True)
    recent = list(own.order_by("-create_time", "-id").values("id", "problem_id", "problem__title", "result", "language", "create_time")[:10])
    solved_ids = Achievement.objects.filter(user=user).values("original_problem_id")
    pending = own.exclude(problem_id__in=solved_ids).order_by("problem_id", "-create_time").distinct("problem_id")
    pending_ids = list(pending.values_list("problem_id", flat=True)[:10])
    from problem.models import Problem
    problems = list(Problem.objects.filter(pk__in=pending_ids).values("id", "_id", "title"))
    latest = own.exclude(problem_id__in=solved_ids).order_by("-create_time", "-id").first()
    topics = list(Problem.objects.filter(id__in=solved_ids, contest__isnull=True, visible=True).values("tags__name").annotate(solved=Count("id", distinct=True)))
    return {"continue_problem": {"id": latest.problem_id, "_id": latest.problem._id, "title": latest.problem.title} if latest else None,
            "pending_problems": problems, "recent_submissions": recent, "topics": topics,
            "solved_count": Achievement.objects.filter(user=user).count()}
