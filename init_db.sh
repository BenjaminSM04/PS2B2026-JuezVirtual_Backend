#! /bin/bash
set -eu

if [[ ! -f manage.py ]]; then
    echo "No manage.py, wrong location"
    exit 1
fi

# Reutilizar contenedores y volúmenes de desarrollo; nunca borrarlos al inicializar.
if docker container inspect oj-postgres-dev >/dev/null 2>&1; then
    docker start oj-postgres-dev
else
    docker run -d -e POSTGRES_DB=onlinejudge -e POSTGRES_USER=onlinejudge -e POSTGRES_PASSWORD=onlinejudge \
        -v oj-postgres-dev-data:/var/lib/postgresql/data -p 127.0.0.1:5435:5432 --name oj-postgres-dev postgres:10
fi
if docker container inspect oj-redis-dev >/dev/null 2>&1; then
    docker start oj-redis-dev
else
    docker run -d -v oj-redis-dev-data:/data -p 127.0.0.1:6380:6379 --name oj-redis-dev redis:7-alpine
fi

if [ "${1:-}" = "--migrate" ]; then
    ready=0
    for attempt in {1..30}; do
        if docker exec oj-postgres-dev sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; then
            ready=1
            break
        fi
        sleep 2
    done
    if [ "$ready" -ne 1 ]; then
        echo "PostgreSQL no está disponible; no se ejecutan migraciones." >&2
        exit 1
    fi
    mkdir -p data/config
    if [ ! -f data/config/secret.key ]; then
        (umask 077; python -c 'import secrets; print(secrets.token_urlsafe(64))' > data/config/secret.key)
    fi
    python manage.py migrate
    echo "Si necesita un administrador nuevo, ejecute inituser explícitamente desde una terminal."
fi
