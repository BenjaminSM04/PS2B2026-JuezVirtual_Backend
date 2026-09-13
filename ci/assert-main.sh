#!/usr/bin/env bash
# Impide promover o desplegar una revisión antigua, incluso al repetir un workflow.
set -euo pipefail
: "${GH_TOKEN:?}"
: "${GITHUB_REPOSITORY:?}"
: "${GITHUB_SHA:?}"
: "${GITHUB_REF:?}"
test "$GITHUB_REF" = "refs/heads/main"
current=$(gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/main" --jq '.object.sha')
if [ "$current" != "$GITHUB_SHA" ]; then
  echo "La revisión ya no es HEAD de main; no se publicará latest ni se desplegará." >&2
  exit 1
fi
