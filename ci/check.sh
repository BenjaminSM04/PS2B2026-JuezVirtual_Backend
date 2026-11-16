#!/usr/bin/env bash
set -euo pipefail
project="lizard-ci-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
compose=(docker compose -p "$project" -f ci/compose.test.yml)
# Solo se retiran recursos del proyecto efímero de este proceso.
trap '"${compose[@]}" down --volumes --remove-orphans' EXIT
bash -n ci/*.sh
"${compose[@]}" run --rm tests
