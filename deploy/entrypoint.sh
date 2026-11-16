#!/bin/sh
set -eu
umask 027

python /app/deploy/prepare.py
case "${1:-serve}" in
    serve)
        python manage.py migrate --check
        exec supervisord -c /app/deploy/supervisord.conf
        ;;
    migrate)
        python manage.py migrate --no-input
        python manage.py reconcile_mascot
        exec python manage.py configure_runtime
        ;;
    *)
        exec "$@"
        ;;
esac
