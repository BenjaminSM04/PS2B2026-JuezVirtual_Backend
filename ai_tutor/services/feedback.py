import hashlib
import json
import time

from django.db import transaction
from django.core.cache import cache

from ai_tutor.models import TutorFeedback, TutorMetric, TutorRating, TutorRequest, TutorSession
from ai_tutor.services.access import authorize
from ai_tutor.services.context import build_context
from ai_tutor.services.engine import generate
from ai_tutor.services.explainers import diagnostic
from ai_tutor.services.output_guard import validate_output, VERSION
from ai_tutor.services.sessions import FINAL_RESULTS
from submission.models import Submission
from utils.api import APIError
from utils.audit import audit_log


def throttle(user_id, session_id):
    for key, limit in (("user:" + str(user_id), 12), ("session:" + str(session_id), 6)):
        key = "tutor:rate:" + key
        cache.add(key, 0, timeout=60)
        if cache.incr(key) > limit:
            raise APIError("Espera un minuto antes de solicitar más ayuda.", err="tutor-rate-limit")


@transaction.atomic
def feedback(user, session_id, request_id, action, level=None, concept=""):
    started = time.monotonic()
    try:
        session = TutorSession.objects.select_for_update(of=("self",)).select_related("problem", "config_version").get(pk=session_id, user=user, state="active")
    except TutorSession.DoesNotExist:
        raise APIError("La sesión no está disponible.", err="tutor-session-unavailable")
    authorize(user, session.problem_id)
    if not session.config_version_id:
        raise APIError("Esta sesión necesita una configuración pedagógica versionada.", err="tutor-config-required")
    request_hash = hashlib.sha256(json.dumps([action, level, concept], ensure_ascii=True).encode()).hexdigest()
    previous = session.feedback.filter(request_id=request_id).first()
    alias = TutorRequest.objects.select_related("feedback").filter(session=session, request_id=request_id).first()
    if alias:
        if alias.request_hash != request_hash:
            raise APIError("El identificador ya se utilizó para otra solicitud.", err="tutor-idempotency-conflict")
        return alias.feedback
    if previous:
        if previous.request_hash != request_hash:
            raise APIError("El identificador ya se utilizó para otra solicitud.", err="tutor-idempotency-conflict")
        return previous
    throttle(user.id, session.id)
    submission = Submission.objects.filter(user_id=user.id, problem_id=session.problem_id, contest__isnull=True,
                                          create_time__gte=session.created_at, result__in=FINAL_RESULTS).order_by("-create_time", "-id").first()
    if action != "concept" and not submission:
        raise APIError("Envía un intento y espera su veredicto antes de pedir ayuda.", err="tutor-attempt-required")
    selected_level = level if action == "hint" else 0
    if action == "hint":
        if level > session.config_version.hint_policy["max_help_level"] or level > session.highest_help_level + 1 or level < session.highest_help_level:
            raise APIError("El nivel solicitado no está disponible.", err="tutor-level-locked")
        last_hint = session.feedback.filter(action="hint").order_by("-created_at").first()
        if level > session.highest_help_level and last_hint and submission.create_time <= last_hint.created_at:
            raise APIError("Para avanzar necesitas un nuevo intento juzgado posterior a la pista.", err="tutor-new-attempt-required")
        # Solicitar de nuevo el mismo nivel conserva la respuesta y no llama al motor.
        same_level = session.feedback.filter(action="hint", level=level).first()
        if same_level:
            TutorRequest.objects.create(session=session, request_id=request_id, request_hash=request_hash, feedback=same_level)
            return same_level
    if action == "concept" and concept not in session.config_version.concepts:
        raise APIError("El concepto no pertenece a esta configuración.", err="tutor-concept-invalid")
    context = build_context(session, submission, action, selected_level, concept)
    context_hash = hashlib.sha256(json.dumps(context, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    generated = generate(context)
    source = "model" if generated else "deterministic"
    diag = diagnostic(submission) if submission else {"category": "concept", "uncertainty": "Explicación configurada por el docente."}
    if not generated:
        content = diag.get("content", "")
        if action == "hint":
            content = session.config_version.hint_policy["hints"][("concept", "location", "strategy")[level - 1]]
            source = "static"
        elif action == "concept":
            content = session.config_version.concept_explanations.get(concept, "")
            source = "static"
        elif diag.get("evidence"):
            content += " " + diag["evidence"]
        if not content:
            raise APIError("No existe una explicación segura configurada para esta solicitud.", err="tutor-unavailable")
        generated = {"content": content, "uncertainty": diag["uncertainty"], "model_version": "fallback-1"}
        try:
            validate_output(generated)
        except ValueError:
            raise APIError("La ayuda configurada requiere revisión del docente.", err="tutor-unavailable")
    result = TutorFeedback.objects.create(session=session, submission=submission if action != "concept" else None,
        request_id=request_id, request_hash=request_hash, action=action, level=selected_level, concept=concept,
        content=generated["content"], source=source, category=diag["category"], uncertainty=generated["uncertainty"],
        model_version=generated["model_version"], context_hash=context_hash, guard_version=VERSION,
        latency_ms=max(0, int((time.monotonic() - started) * 1000)))
    if action == "hint" and level > session.highest_help_level:
        session.highest_help_level = level
        session.save(update_fields=["highest_help_level", "updated_at"])
    TutorMetric.objects.create(feedback=result, category=result.category, level=result.level, source=result.source,
        latency_ms=result.latency_ms, model_version=result.model_version, config_version_id=session.config_version_id, outcome="completed")
    TutorRequest.objects.create(session=session, request_id=request_id, request_hash=request_hash, feedback=result)
    return result


@transaction.atomic
def rate(user, feedback_id, value):
    try:
        item = TutorFeedback.objects.select_for_update().select_related("session").get(pk=feedback_id, session__user=user)
    except TutorFeedback.DoesNotExist:
        raise APIError("La respuesta no está disponible.", err="tutor-feedback-unavailable")
    authorize(user, item.session.problem_id)
    previous = TutorRating.objects.filter(feedback=item).first()
    old = previous.value if previous else None
    if old != value:
        TutorRating.objects.update_or_create(feedback=item, defaults={"value": value})
        transaction.on_commit(lambda: audit_log(user, "tutor_rating_changed", "TutorFeedback", str(item.id), {"before": old, "after": value}))
    return {"feedback_id": str(item.id), "value": value}
