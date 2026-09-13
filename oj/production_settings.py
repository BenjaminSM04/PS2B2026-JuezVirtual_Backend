import os

from utils.shortcuts import get_env

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "HOST": get_env("POSTGRES_HOST", "oj-postgres"),
        "PORT": get_env("POSTGRES_PORT", "5432"),
        "NAME": get_env("POSTGRES_DB", "onlinejudge"),
        "USER": get_env("POSTGRES_USER", "onlinejudge"),
        "PASSWORD": get_env("POSTGRES_PASSWORD"),
        "OPTIONS": {"connect_timeout": 3},
    }
}
REDIS_CONF = {
    "host": get_env("REDIS_HOST", "oj-redis"),
    "port": get_env("REDIS_PORT", "6379"),
}
DEBUG = False
ALLOWED_HOSTS = [host.strip() for host in get_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]
DATA_DIR = os.environ.get("OJ_DATA_DIR", "/data")
# Solo los proxies privados del Compose pueden suministrar esta cabecera.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = get_env("COOKIE_SECURE", "true").lower() == "true"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"
