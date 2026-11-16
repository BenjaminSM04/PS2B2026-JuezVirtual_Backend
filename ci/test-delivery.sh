#!/usr/bin/env bash
# Pruebas sin red: nunca llaman a GitHub ni a Coolify.
set -euo pipefail
cd "$(dirname "$0")/.."
export COOLIFY_WEBHOOK=https://coolify.invalid/api/v1/deploy?uuid=prueba
export COOLIFY_TOKEN=token-publico-exclusivo-de-pruebas
export MOCK_STATUS=200 MOCK_EXIT=0
export MOCK_BODY='{"deployments":[{"deployment_uuid":"prueba_123"}]}'

curl() {
  local output="" method="" connect="" timeout="" header="" fail=false
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --output) output="$2"; shift 2 ;;
      --request) method="$2"; shift 2 ;;
      --connect-timeout) connect="$2"; shift 2 ;;
      --max-time) timeout="$2"; shift 2 ;;
      --header) header="$2"; shift 2 ;;
      --fail) fail=true; shift ;;
      *) shift ;;
    esac
  done
  [ "$method" = POST ] && [ "$connect" = 10 ] && [ "$timeout" = 30 ] && [ "$fail" = true ] || return 90
  [ "$header" = "Authorization: Bearer $COOLIFY_TOKEN" ] || return 91
  printf '%s' "$MOCK_BODY" > "$output"
  printf '%s' "$MOCK_STATUS"
  return "$MOCK_EXIT"
}
export -f curl
output=$(bash ci/deploy-coolify.sh 2>&1)
[[ "$output" == *"prueba_123"* ]] && [[ "$output" != *"$COOLIFY_TOKEN"* ]]

for status in 301 401 403 422 500; do
  if output=$(MOCK_STATUS="$status" bash ci/deploy-coolify.sh 2>&1); then
    echo "Se aceptó incorrectamente HTTP $status." >&2; exit 1
  fi
  [[ "$output" != *"$COOLIFY_TOKEN"* ]]
done
for body in '{}' '{"deployments":[]}' 'respuesta-invalida'; do
  if MOCK_BODY="$body" bash ci/deploy-coolify.sh > /dev/null 2>&1; then exit 1; fi
done
if MOCK_EXIT=28 bash ci/deploy-coolify.sh > /dev/null 2>&1; then exit 1; fi
if COOLIFY_TOKEN="" bash ci/deploy-coolify.sh > /dev/null 2>&1; then exit 1; fi
if COOLIFY_WEBHOOK=http://coolify.invalid bash ci/deploy-coolify.sh > /dev/null 2>&1; then exit 1; fi

export GH_TOKEN=token-de-pruebas GITHUB_REPOSITORY=ejemplo/pruebas
export GITHUB_REF=refs/heads/main GITHUB_SHA=revision-actual MOCK_SHA=revision-actual
gh() { printf '%s' "$MOCK_SHA"; }
export -f gh
bash ci/assert-main.sh
if MOCK_SHA=otra-revision bash ci/assert-main.sh > /dev/null 2>&1; then exit 1; fi
if GITHUB_REF=refs/heads/otra bash ci/assert-main.sh > /dev/null 2>&1; then exit 1; fi
echo "Protecciones de entrega verificadas sin solicitudes externas."
