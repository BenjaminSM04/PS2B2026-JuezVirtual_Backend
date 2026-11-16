#!/usr/bin/env bash
# POST autenticado, sin redirecciones ni reintentos que dupliquen despliegues.
set -euo pipefail
: "${COOLIFY_WEBHOOK:?Falta el secreto COOLIFY_WEBHOOK}"
: "${COOLIFY_TOKEN:?Falta el secreto COOLIFY_TOKEN}"
case "$COOLIFY_WEBHOOK" in
  https://*) ;;
  *) echo "COOLIFY_WEBHOOK debe utilizar HTTPS." >&2; exit 1 ;;
esac
response=$(mktemp)
trap 'rm -f "$response"' EXIT
status=$(curl --silent --show-error --fail \
  --request POST --connect-timeout 10 --max-time 30 \
  --header "Authorization: Bearer $COOLIFY_TOKEN" \
  --output "$response" --write-out '%{http_code}' "$COOLIFY_WEBHOOK")
case "$status" in
  2??) ;;
  *) echo "Coolify no aceptó la solicitud (HTTP $status)." >&2; exit 1 ;;
esac
# No imprimir el cuerpo completo: extraer solo identificadores conocidos.
jq -e '.deployments | type == "array" and length > 0' "$response" > /dev/null
jq -r '.deployments[] | .deployment_uuid // empty | select(test("^[A-Za-z0-9_-]+$")) |
  "Solicitud de despliegue aceptada: " + .' "$response"
echo "Comprobar el resultado y la salud en Coolify; la aceptación no confirma disponibilidad."
