# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

FROM base AS wheels
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/requirements.lock /tmp/requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --require-hashes --no-deps -r /tmp/requirements.lock -w /wheels

FROM base AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 nginx supervisor curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 903 spj && useradd --uid 900 --gid spj --no-create-home server
COPY --from=wheels /wheels /wheels
RUN pip install --no-cache-dir --no-index /wheels/* && rm -rf /wheels
COPY --chown=900:903 . /app
RUN mkdir -p /data/config /data/log /data/test_case /data/public \
    && chown -R 900:903 /data \
    && sed -i 's/\r$//' /app/deploy/entrypoint.sh \
    && chmod 755 /app/deploy/entrypoint.sh
ARG APP_REVISION=desarrollo
ENV OJ_ENV=production APP_REVISION=${APP_REVISION} MAX_WORKER_NUM=2
LABEL org.opencontainers.image.source="https://github.com/incubadoradesarrollo-source/B-LIZARD-JUDGE" \
      org.opencontainers.image.revision="${APP_REVISION}"
USER 900:903
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=8s --start-period=60s --retries=3 \
    CMD ["python", "/app/deploy/health_check.py"]
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
CMD ["serve"]

FROM runtime AS ci
USER root
ENV COVERAGE_FILE=/tmp/.coverage
COPY deploy/requirements-ci.lock /tmp/requirements-ci.lock
# psycopg2 ya está instalado desde las wheels del entorno de producción.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes -r /tmp/requirements-ci.lock
USER 900:903
CMD ["python", "run_test.py"]

# La construcción por defecto siempre entrega producción.
FROM runtime AS production
