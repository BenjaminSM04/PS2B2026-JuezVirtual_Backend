# Motor del tutor: valida artefactos aprobados y consulta al servidor del modelo.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
ARG APP_REVISION=desarrollo
LABEL org.opencontainers.image.source="https://github.com/incubadoradesarrollo-source/B-LIZARD-JUDGE" \
      org.opencontainers.image.revision="${APP_REVISION}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service
COPY tutor_engine/server.py ./
COPY ai_tutor/services/output_guard.py ./guard.py
COPY ai_tutor/ml/runtime.py ./classifier_runtime.py
COPY utils/bounded_http.py ./
COPY ai_tutor/ml/prompt.py ./tutor_prompt.py
# El motor comprueba el SHA-256 de cada artefacto contra el manifiesto al arrancar.
COPY tutor_engine/modelo/manifest.json tutor_engine/modelo/classifier.json tutor_engine/modelo/model.gguf /models/
USER 65534:65534
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]
CMD ["python", "server.py"]
