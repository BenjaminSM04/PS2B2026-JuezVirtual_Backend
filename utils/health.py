"""Endpoints de operación sin información sensible ni escrituras."""
import os

from django.db import connection
from django.http import JsonResponse
from django_redis import get_redis_connection
from django.views.decorators.http import require_GET


@require_GET
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        get_redis_connection("default").ping()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@require_GET
def version(request):
    return JsonResponse({"revision": os.environ.get("APP_REVISION", "desarrollo")})
