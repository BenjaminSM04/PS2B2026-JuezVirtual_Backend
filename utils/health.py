import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@csrf_exempt
@never_cache
@require_http_methods(["GET", "HEAD"])
def healthz(request):
    """Healthcheck liviano para orquestadores: BD y caché, solo lectura.

    No expone detalles de error (se registran en el log del servidor).
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        cache.get("healthz:ping")
    except Exception:
        logger.exception("Healthcheck fallido")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
