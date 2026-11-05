#!/usr/bin/env bash
# Arranca motor y modelo en una red interna efímera y exige readiness y una respuesta acotada.
set -euo pipefail
engine_image=$1
model_image=$2
id="tutor-smoke-${GITHUB_RUN_ID:-local}"
cleanup() {
  docker logs "$id-modelo" 2>&1 | tail -5 || true
  docker rm -f "$id-motor" "$id-modelo" "$id-cliente" > /dev/null 2>&1 || true
  docker network rm "$id" > /dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create --internal "$id" > /dev/null
docker run -d --name "$id-modelo" --network "$id" --network-alias oj-model "$model_image" \
  -m /models/model.gguf --host 0.0.0.0 --port 8080 -c 4096 -np 1 --threads 2 > /dev/null
docker run -d --name "$id-motor" --network "$id" --read-only --cap-drop ALL \
  -e MODEL_URL=http://oj-model:8080 -e MODEL_TIMEOUT_S=30 "$engine_image" > /dev/null

for _ in $(seq 1 90); do
  if docker exec "$id-motor" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)" 2> /dev/null; then
    ready=1
    break
  fi
  sleep 2
done
if [ "${ready:-0}" != 1 ]; then
  docker logs "$id-motor"
  echo "ERROR: el motor no quedó listo con los artefactos aprobados" >&2
  exit 1
fi

docker exec -i "$id-motor" python - <<'EOF'
import json, time, urllib.error, urllib.request
context = {"schema_version": "1.0", "action": "explain", "level": 0, "concept": "",
           "problem": {"title": "Suma", "description": "Lee A y B (hasta 10^18) y muestra su suma.",
                       "input_description": "A y B.", "output_description": "La suma."},
           "code": "#include <stdio.h>\nint main(){int a,b;scanf(\"%d %d\",&a,&b);printf(\"%d\\n\",a+b);}",
           "language": "C", "diagnostic": {"category": "unknown", "verdict": -1, "evidence": ""},
           "concepts": ["Tipos y rangos"], "history": [], "config_version": 1}
request = urllib.request.Request("http://127.0.0.1:8080/v1/feedback", json.dumps(context).encode(), {"Content-Type": "application/json"})
started = time.monotonic()
try:
    with urllib.request.urlopen(request, timeout=40) as response:
        status, body = response.status, json.loads(response.read())
except urllib.error.HTTPError as error:
    status, body = error.code, json.loads(error.read())
print("estado", status, "latencia_s", round(time.monotonic() - started, 1), json.dumps(body, ensure_ascii=False))
# 503 es válido: el filtro de calidad descarta y el backend usa el diagnóstico determinista.
assert status in (200, 503), status
EOF
