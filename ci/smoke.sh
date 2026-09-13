#!/usr/bin/env bash
set -euo pipefail
project="lizard-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
compose=(docker compose -p "$project" -f ci/compose.test.yml)
trap '"${compose[@]}" down --volumes --remove-orphans' EXIT
"${compose[@]}" run --rm app migrate
"${compose[@]}" up -d app
container=$("${compose[@]}" ps -q app)
for attempt in {1..45}; do
  status=$(docker inspect --format '{{.State.Health.Status}}' "$container")
  if [ "$status" = healthy ]; then
    docker exec "$container" curl --fail --silent http://127.0.0.1:8000/api/version/
    test "$(docker exec "$container" id -u)" = 900
    key_before=$(docker exec "$container" sha256sum /data/config/secret.key)
    docker exec "$container" python manage.py shell -c \
      'from options.options import SysOptions; SysOptions.website_name = "Prueba persistente"'
    # El volumen persiste y una segunda migración debe ser idempotente.
    "${compose[@]}" run --rm app migrate
    test "$key_before" = "$(docker exec "$container" sha256sum /data/config/secret.key)"
    docker exec "$container" python manage.py shell -c \
      'from options.options import SysOptions; assert SysOptions.website_name == "Prueba persistente"'
    exit 0
  fi
  sleep 2
done
"${compose[@]}" logs app
exit 1
