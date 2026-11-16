import json
import http.client
from django.conf import settings
from django.core.cache import cache

from ai_tutor.services.output_guard import validate_output, VERSION
from utils.api import APIError
from utils.audit import audit_log
from utils.bounded_http import post_json


def generate(context):
    if not getattr(settings, "AI_TUTOR_MODEL_ENABLED", False) or cache.get("tutor:engine-open"):
        return None
    try:
        body = json.dumps(context).encode()
        if len(body) > 64000:
            return None
        generated = post_json(settings.AI_TUTOR_ENGINE_URL + "/v1/feedback", body,
                              timeout=min(30, settings.AI_TUTOR_ENGINE_TIMEOUT))
        return validate_output(generated)
    except (OSError, http.client.HTTPException, ValueError):
        cache.set("tutor:engine-open", True, timeout=30)
        audit_log(None, "tutor_engine_fallback", "Engine", None, {"guard_version": VERSION})
        return None


def suggest(problem):
    """Borrador de conceptos y pistas para el docente; es texto sin validar, nunca se entrega a un estudiante."""
    if not getattr(settings, "AI_TUTOR_MODEL_ENABLED", False):
        raise APIError("Las sugerencias con IA no están activadas en este servidor. Escribe el contenido a mano.", err="tutor-suggest-unavailable")
    try:
        body = json.dumps({"problem": problem}).encode()
        # No usa el circuito de generate: una sugerencia rechazada no debe apagar las observaciones a estudiantes.
        # Plazo propio: el borrador tarda decenas de segundos en CPU y no comparte el tope de 30 s de las observaciones.
        return post_json(settings.AI_TUTOR_ENGINE_URL + "/suggest", body, timeout=settings.AI_TUTOR_SUGGEST_TIMEOUT, max_bytes=40000)
    except (OSError, http.client.HTTPException, ValueError):
        raise APIError("No se pudo generar una sugerencia ahora. Inténtalo de nuevo en un momento o escribe el contenido a mano.",
                       err="tutor-suggest-unavailable") from None
