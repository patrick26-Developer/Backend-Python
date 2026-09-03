#!/usr/bin/env sh
set -e

# Migrations : pratique en dev/compose (RUN_MIGRATIONS=true).
# EN PRODUCTION : préférer une étape de pipeline séparée AVANT de router le trafic
# (voir 11-deploiement-devops/THEORIE.md §5). N conteneurs qui migrent en même
# temps = courses / deadlocks.
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "→ alembic upgrade head"
    alembic upgrade head
fi

exec "$@"
