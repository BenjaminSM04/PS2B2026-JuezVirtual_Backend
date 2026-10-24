from .settings import *  # NOQA

# Solo pruebas aisladas; producción conserva los hashers normales y su compatibilidad.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES["default"]["LOCATION"] = f"{REDIS_URL}/9"  # NOQA
DRAMATIQ_BROKER["OPTIONS"]["url"] = f"{REDIS_URL}/10"  # NOQA
DRAMATIQ_RESULT_BACKEND["BACKEND_OPTIONS"]["url"] = f"{REDIS_URL}/10"  # NOQA
