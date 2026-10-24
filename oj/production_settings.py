from utils.shortcuts import env_list, get_env, get_env_bool

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': get_env("POSTGRES_HOST", "oj-postgres"),
        'PORT': get_env("POSTGRES_PORT", "5432"),
        'NAME': get_env("POSTGRES_DB"),
        'USER': get_env("POSTGRES_USER"),
        'PASSWORD': get_env("POSTGRES_PASSWORD")
    }
}

REDIS_CONF = {
    "host": get_env("REDIS_HOST", "oj-redis"),
    "port": get_env("REDIS_PORT", "6379")
}

DEBUG = False

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,oj-backend,testserver")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "DJANGO_CSRF_TRUSTED_ORIGINS")
SESSION_COOKIE_SECURE = get_env_bool("COOKIE_SECURE")
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
if get_env_bool("TRUST_PROXY_HTTPS"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATA_DIR = "/data"
