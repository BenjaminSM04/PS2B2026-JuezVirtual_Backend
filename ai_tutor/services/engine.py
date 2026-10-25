import json
import http.client
from django.conf import settings
from django.core.cache import cache

from ai_tutor.services.output_guard import validate_output, VERSION
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
