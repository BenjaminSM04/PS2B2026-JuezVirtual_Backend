"""Borradores de conceptos y pistas para el docente: se devuelven sin guardar y los revisa antes de crear una versión."""

from django.core.cache import cache

from account.decorators import ensure_created_by
from ai_tutor.services.access import get_problem
from ai_tutor.services.context import clip, public_text, redact
from ai_tutor.services.engine import suggest
from ai_tutor.services.problem_config import validate_content
from utils.api import APIError
from utils.audit import audit_log

SUGGESTIONS_PER_MINUTE = 6
SAMPLES = 2
SAMPLE_LIMIT = 300


def throttle(user_id):
    key = "tutor:suggest:user:" + str(user_id)
    cache.add(key, 0, timeout=60)
    if cache.incr(key) > SUGGESTIONS_PER_MINUTE:
        raise APIError("Espera un minuto antes de pedir más sugerencias.", err="tutor-rate-limit")


def problem_payload(problem):
    """Solo texto público del enunciado y ejemplos visibles, con la misma redacción y límites que el contexto del tutor."""
    samples = [{key: clip(redact(item.get(key, ""), SAMPLE_LIMIT), SAMPLE_LIMIT) for key in ("input", "output")}
               for item in (problem.samples or [])[:SAMPLES] if isinstance(item, dict)]
    return {**{key: public_text(getattr(problem, key)) for key in ("title", "description", "input_description", "output_description")},
            "samples": samples}


def to_content(suggestion):
    """Misma forma que acepta la creación de versiones: nombres, explicaciones por concepto y pistas de nivel máximo 3."""
    concepts = suggestion["concepts"]
    return {"schema_version": "1.0", "concepts": [item["name"] for item in concepts],
            "concept_explanations": {item["name"]: item["explanation"] for item in concepts},
            "hint_policy": {"max_help_level": 3, "hints": suggestion["hints"]}}


def suggest_content(user, problem_id):
    problem = get_problem(problem_id)
    ensure_created_by(problem, user)
    payload = problem_payload(problem)
    if not payload["title"] and not payload["description"]:
        raise APIError("El problema necesita un título o un enunciado para generar una sugerencia.", err="tutor-suggest-empty")
    throttle(user.id)
    try:
        suggestion = suggest(payload)
        content = validate_content(to_content(suggestion))
    except (APIError, KeyError, TypeError, AttributeError) as error:
        audit_log(user, "tutor_config_suggest_failed", "Problem", problem.id, {"error": getattr(error, "err", None) or type(error).__name__})
        if isinstance(error, APIError) and error.err == "tutor-suggest-unavailable":
            raise
        raise APIError("El asistente devolvió una sugerencia que no cumple el formato. Inténtalo de nuevo o escribe el contenido a mano.",
                       err="tutor-suggest-unavailable") from None
    audit_log(user, "tutor_config_suggested", "Problem", problem.id, {"concepts": len(content["concepts"])})
    return content
