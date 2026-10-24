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
        deadline = time.monotonic() + min(5, settings.AI_TUTOR_ENGINE_TIMEOUT)
        body = json.dumps(context).encode()
        if len(body) > 64000:
            return None
        response = requests.post(settings.AI_TUTOR_ENGINE_URL + "/v1/feedback", data=body,
                                 headers={"Content-Type": "application/json"},
                                 timeout=(1, 0.5), stream=True)
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
