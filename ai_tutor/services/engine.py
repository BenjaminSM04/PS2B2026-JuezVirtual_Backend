import json
import requests
import time
from django.conf import settings
from django.core.cache import cache

from ai_tutor.services.output_guard import validate_output, VERSION
from utils.audit import audit_log


def generate(context):
    if not getattr(settings, "AI_TUTOR_MODEL_ENABLED", False) or cache.get("tutor:engine-open"):
        return None
    try:
        deadline = time.monotonic() + min(30, settings.AI_TUTOR_ENGINE_TIMEOUT)
        body = json.dumps(context).encode()
        if len(body) > 64000:
            return None
        # El motor responde solo al terminar de generar: el read timeout es el
        # presupuesto restante, no una espera corta por byte.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("deadline")
        response = requests.post(settings.AI_TUTOR_ENGINE_URL + "/v1/feedback", data=body,
                                 headers={"Content-Type": "application/json"},
                                 timeout=(1, remaining), stream=True)
        with response:
            response.raise_for_status()
            raw = b""
            for chunk in response.iter_content(1):
                if time.monotonic() > deadline:
                    raise ValueError("deadline")
                raw += chunk
                if len(raw) > 16000:
                    raise ValueError("size")
            return validate_output(json.loads(raw))
    except (requests.RequestException, ValueError):
        cache.set("tutor:engine-open", True, timeout=30)
        audit_log(None, "tutor_engine_fallback", "Engine", None, {"guard_version": VERSION})
        return None
